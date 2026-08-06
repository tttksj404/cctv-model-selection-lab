from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx2

from qwen_backend.storage_transfer import (
    StorageTransferError,
    download_to_path,
    read_checked_file,
    upload_file,
)


class ObjectStorageError(RuntimeError):
    """A signed S3/MinIO object transfer could not be completed."""


@dataclass(frozen=True, slots=True)
class S3ObjectStoreConfig:
    endpoint: str
    bucket: str
    region: str
    access_key: str
    secret_key: str
    path_style: bool = True


class S3ObjectStore:
    """Minimal SigV4 client for the worker's private MinIO/S3 bucket.

    The worker receives object keys in the legacy Rabbit event.  Since that
    contract does not provide signed recording URLs, this adapter signs only
    the two required object operations and keeps storage credentials out of
    the central API request headers.
    """

    def __init__(self, config: S3ObjectStoreConfig, client: httpx2.AsyncClient) -> None:
        self._config = _validate_config(config)
        self._client = client

    async def download(
        self,
        object_key: str,
        destination: Path,
        *,
        max_bytes: int,
        chunk_bytes: int,
    ) -> Path:
        url = self._object_url(object_key)
        headers = self._signed_headers("GET", url, payload_hash=_empty_payload_hash())
        try:
            return await download_to_path(
                self._client,
                url,
                destination,
                max_bytes=max_bytes,
                chunk_bytes=chunk_bytes,
                headers=headers,
            )
        except StorageTransferError as exception:
            raise ObjectStorageError(str(exception)) from exception

    async def upload(
        self,
        object_key: str,
        source_path: Path,
        *,
        content_type: str,
        max_bytes: int,
    ) -> None:
        url = self._object_url(object_key)
        content = read_checked_file(source_path, max_bytes)
        payload_hash = hashlib.sha256(content).hexdigest()
        headers = self._signed_headers("PUT", url, payload_hash=payload_hash)
        try:
            await upload_file(
                self._client,
                url,
                source_path,
                content_type=content_type,
                max_bytes=max_bytes,
                headers=headers,
            )
        except StorageTransferError as exception:
            raise ObjectStorageError(str(exception)) from exception

    def _object_url(self, object_key: str) -> str:
        _validate_object_key(object_key)
        endpoint = urlsplit(self._config.endpoint)
        encoded_key = quote(object_key, safe="/-_.~")
        if self._config.path_style:
            path = (
                f"{endpoint.path.rstrip('/')}/{quote(self._config.bucket, safe='')}/{encoded_key}"
            )
            return endpoint._replace(path=path or "/").geturl()
        host = f"{self._config.bucket}.{endpoint.netloc}"
        path = f"{endpoint.path.rstrip('/')}/{encoded_key}"
        return endpoint._replace(netloc=host, path=path or "/").geturl()

    def _signed_headers(self, method: str, url: str, *, payload_hash: str) -> dict[str, str]:
        parsed = urlsplit(url)
        if not parsed.hostname:
            raise ObjectStorageError("storage endpoint has no host")
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        host = parsed.netloc
        canonical_uri = parsed.path or "/"
        canonical_query = parsed.query
        canonical_headers = (
            f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            (
                method,
                canonical_uri,
                canonical_query,
                canonical_headers,
                signed_headers,
                payload_hash,
            )
        )
        credential_scope = f"{date_stamp}/{self._config.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            (
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            )
        )
        signing_key = _signing_key(self._config.secret_key, date_stamp, self._config.region)
        signature = hmac.new(
            signing_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "Host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            "Authorization": (
                f"AWS4-HMAC-SHA256 Credential={self._config.access_key}/{credential_scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
        }


def _validate_config(config: S3ObjectStoreConfig) -> S3ObjectStoreConfig:
    endpoint = config.endpoint.strip().rstrip("/")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("storage endpoint must use http or https")
    if not config.bucket.strip() or "/" in config.bucket:
        raise ValueError("storage bucket must be a non-empty bucket name")
    if not config.region.strip() or not config.access_key.strip() or not config.secret_key.strip():
        raise ValueError("storage region and credentials are required")
    return S3ObjectStoreConfig(
        endpoint=endpoint,
        bucket=config.bucket.strip(),
        region=config.region.strip(),
        access_key=config.access_key.strip(),
        secret_key=config.secret_key.strip(),
        path_style=config.path_style,
    )


def _validate_object_key(object_key: str) -> None:
    if not object_key.strip() or object_key.startswith("/"):
        raise ValueError("storage object key must be relative and non-empty")
    if "\\" in object_key or ".." in object_key or any(ord(char) < 32 for char in object_key):
        raise ValueError("storage object key contains an unsafe segment")


def _empty_payload_hash() -> str:
    return hashlib.sha256(b"").hexdigest()


def _signing_key(secret_key: str, date_stamp: str, region: str) -> bytes:
    date_key = hmac.new(
        ("AWS4" + secret_key).encode("utf-8"),
        date_stamp.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    region_key = hmac.new(date_key, region.encode("utf-8"), hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()
