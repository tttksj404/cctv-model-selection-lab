#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx2[http2,brotli,zstd]",
#   "typer",
# ]
# ///

from __future__ import annotations

import hashlib
import json
import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated

import httpx2
import typer
from chirla_index import (
    CHIRLA_PREFIX,
    ChirlaRemoteFile,
    parse_chirla_index,
    safe_relative_path,
    select_reid_files,
)

DATASET_ID = "2247f442a9784b5c959e7bead89c0313"
INDEX_URL = "https://www.scidb.cn/api/sdb-filetree-service/getAllUrl"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LOGGER = logging.getLogger("fetch_chirla_benchmark")
app = typer.Typer(add_completion=False)


def _client() -> httpx2.Client:
    limits = httpx2.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0)
    timeout = httpx2.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
    transport = httpx2.HTTPTransport(
        http2=True,
        retries=3,
        limits=limits,
        socket_options=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)],
    )
    return httpx2.Client(
        transport=transport,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "qwen3vl-backend-chirla-fetch/1.0"},
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(client: httpx2.Client, item: ChirlaRemoteFile, root: Path) -> dict[str, str | int]:
    local_relative = safe_relative_path(item.relative_path)
    target = root / local_relative
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    was_existing = target.exists()
    if not was_existing:
        for attempt in range(5):
            with client.stream("GET", item.url) as response:
                if response.status_code in {429, 500, 502, 503, 504}:
                    if attempt == 4:
                        response.raise_for_status()
                    retry_after = response.headers.get("retry-after")
                    try:
                        delay = float(retry_after) if retry_after else 2.0**attempt
                    except ValueError:
                        delay = 2.0**attempt
                    time.sleep(min(max(delay, 1.0), 30.0))
                    continue
                response.raise_for_status()
                with partial.open("wb") as stream:
                    for chunk in response.iter_bytes():
                        stream.write(chunk)
            partial.replace(target)
            break
    return {
        "sourcePath": item.relative_path,
        "localPath": local_relative,
        "fileId": item.file_id,
        "sha256": _sha256(target),
        "bytes": target.stat().st_size,
        "status": "existing" if was_existing else "downloaded",
    }


def _download_row(
    client: httpx2.Client, item: ChirlaRemoteFile, root: Path
) -> dict[str, str | int]:
    downloaded = _download(client, item, root)
    downloaded.update(
        {
            "dataset": "CHIRLA",
            "license": LICENSE_URL,
            "sourceIndexUrl": INDEX_URL,
            "datasetPathPrefix": CHIRLA_PREFIX,
            "task": item.task,
            "scenario": item.scenario or "",
            "split": item.split or "",
            "subset": item.subset or "",
            "sequenceId": item.sequence_id or "",
            "cameraId": item.camera_id or "",
            "identityGroupId": item.identity_group_id or "",
            "frameName": item.frame_name or "",
        }
    )
    return downloaded


def _write_jsonl(path: Path, rows: list[dict[str, str | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    path.write_text(content, encoding="utf-8")


@app.command()
def main(
    root: Annotated[Path, typer.Option(help="CHIRLA local root directory.")] = Path(
        "experiments/data/chirla"
    ),
    scenario: Annotated[str, typer.Option(help="CHIRLA ReID scenario.")] = "multi_camera_long_term",
    max_files: Annotated[int, typer.Option(help="0 means all scenario JSON/PNG files.")] = 0,
    workers: Annotated[int, typer.Option(help="Parallel download workers.")] = 16,
) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    LOGGER.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with _client() as client:
        response = client.get(INDEX_URL, params={"dataSetId": DATASET_ID, "version": "V2"})
        response.raise_for_status()
        index_text = response.content.decode("utf-8")
        files = parse_chirla_index(index_text)
        selected = select_reid_files(files, scenario=scenario, max_files=max_files)
        (root / "source_url_index_v2.txt").write_text(index_text, encoding="utf-8")
        rows: list[dict[str, str | int]] = []
        safe_workers = max(1, min(workers, 32))
        with ThreadPoolExecutor(max_workers=safe_workers) as executor:
            futures = {
                executor.submit(_download_row, client, item, root): item for item in selected
            }
            for number, future in enumerate(as_completed(futures), start=1):
                item = futures[future]
                try:
                    rows.append(future.result())
                except (httpx2.HTTPError, OSError) as error:
                    LOGGER.error("failed %s: %s", item.relative_path, error)
                if number % 100 == 0:
                    LOGGER.info("processed %d/%d files", number, len(selected))
        rows.sort(key=lambda row: str(row["sourcePath"]))
    _write_jsonl(root / "download_manifest.jsonl", rows)
    (root / "README.source.md").write_text(
        "# CHIRLA benchmark source\n\n"
        f"- scenario: `{scenario}`\n- selected files: `{len(selected)}`\n"
        f"- downloaded/hash-verified rows: `{len(rows)}`\n"
        f"- license: [CC BY 4.0]({LICENSE_URL})\n"
        f"- dataset DOI: https://doi.org/10.57760/sciencedb.20543\n"
        "\nThe JSON labels and identity IDs are kept as source evidence. "
        "This is a public ReID benchmark, not a substitute for a reviewed "
        "project-specific CCTV test set.\n",
        encoding="utf-8",
    )
    typer.echo(f"saved {len(rows)}/{len(selected)} files under {root}")


if __name__ == "__main__":
    app()

