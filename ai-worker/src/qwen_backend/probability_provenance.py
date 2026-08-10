from __future__ import annotations

import hashlib
import hmac
import json
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .zone_probability_schemas import ProbabilitySignalKind, ZoneProbabilityRequest

Environment = Literal["development", "test", "production"]


class UntrustedProbabilityProvenance(ValueError):
    pass


class ReplayedProbabilityRequest(ValueError):
    pass


class ProbabilityRequestReplayGuard:
    def __init__(
        self,
        *,
        max_age_seconds: int,
        future_skew_seconds: int,
        cache_size: int,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._max_age = timedelta(seconds=max_age_seconds)
        self._future_skew = timedelta(seconds=future_skew_seconds)
        self._cache_size = cache_size
        self._now = now or (lambda: datetime.now(UTC))
        self._seen_request_ids: OrderedDict[UUID, datetime] = OrderedDict()
        self._latest_revision_by_case: dict[str, int] = {}
        self._lock = Lock()

    def consume(self, request: ZoneProbabilityRequest) -> None:
        now = self._now().astimezone(UTC)
        issued_at = request.issued_at.astimezone(UTC)
        if issued_at < now - self._max_age:
            raise ReplayedProbabilityRequest("probability request has expired")
        if issued_at > now + self._future_skew:
            raise ReplayedProbabilityRequest("probability request is from the future")

        with self._lock:
            expiry_cutoff = now - self._max_age
            while self._seen_request_ids:
                _, oldest_issued_at = next(iter(self._seen_request_ids.items()))
                if oldest_issued_at >= expiry_cutoff:
                    break
                self._seen_request_ids.popitem(last=False)

            if request.request_id in self._seen_request_ids:
                raise ReplayedProbabilityRequest("probability request was already consumed")
            latest_revision = self._latest_revision_by_case.get(request.case_id, 0)
            if request.routing_revision <= latest_revision:
                raise ReplayedProbabilityRequest("probability routing revision is stale")

            while len(self._seen_request_ids) >= self._cache_size:
                self._seen_request_ids.popitem(last=False)
            self._seen_request_ids[request.request_id] = issued_at
            self._latest_revision_by_case[request.case_id] = request.routing_revision


class _RegistryModel(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True)


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(item.capitalize() for item in rest)


class TrustedSignal(_RegistryModel):
    signal_kind: ProbabilitySignalKind
    model_id: str
    model_sha256: str
    calibrator_id: str
    calibrator_sha256: str
    calibration_manifest_sha256: str
    calibration_base_rate: float = Field(gt=0.0, lt=1.0)
    maximum_reliability: float = Field(gt=0.0, le=1.0)
    minimum_sample_count: int = Field(ge=20)
    allowed_environments: tuple[Environment, ...]


class TrustedCameraOperatingPoint(_RegistryModel):
    operating_point_id: str
    operating_point_sha256: str
    sensitivity: float = Field(gt=0.0, lt=1.0)
    false_positive_rate: float = Field(gt=0.0, lt=1.0)
    minimum_sample_count: int = Field(ge=20)
    allowed_environments: tuple[Environment, ...]


class ProbabilityTrustRegistry(_RegistryModel):
    schema_version: Literal["eyesonu-probability-trust-v1"]
    registry_id: str
    signals: tuple[TrustedSignal, ...]
    camera_operating_points: tuple[TrustedCameraOperatingPoint, ...]


def load_probability_trust_registry(path: Path) -> ProbabilityTrustRegistry:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        message = f"probability trust registry is unavailable: {path}"
        raise UntrustedProbabilityProvenance(message) from exc
    return ProbabilityTrustRegistry.model_validate(payload)


def sign_probability_request(request: ZoneProbabilityRequest, signing_key: str) -> str:
    canonical_payload = request.model_dump(
        mode="json",
        by_alias=True,
        exclude={"evidence_signature"},
    )
    canonical_json = json.dumps(
        canonical_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hmac.new(
        signing_key.encode("utf-8"),
        canonical_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validate_probability_provenance(
    request: ZoneProbabilityRequest,
    registry: ProbabilityTrustRegistry,
    environment: Environment,
    evidence_signing_key: str | None,
) -> None:
    if evidence_signing_key is None or request.evidence_signature is None:
        raise UntrustedProbabilityProvenance("probability request signature is missing")
    expected_signature = sign_probability_request(request, evidence_signing_key)
    if not hmac.compare_digest(request.evidence_signature, expected_signature):
        raise UntrustedProbabilityProvenance("probability request signature is invalid")

    trusted_signals = {
        (
            item.signal_kind,
            item.model_id,
            item.model_sha256,
            item.calibrator_id,
            item.calibrator_sha256,
            item.calibration_manifest_sha256,
        ): item
        for item in registry.signals
        if environment in item.allowed_environments
    }
    for evidence in request.evidence:
        for signal in evidence.signals:
            key = (
                signal.signal_kind,
                signal.model_id,
                signal.model_sha256,
                signal.calibrator_id,
                signal.calibrator_sha256,
                signal.calibration_manifest_sha256,
            )
            trusted = trusted_signals.get(key)
            if trusted is None:
                raise UntrustedProbabilityProvenance("signal provenance is not trusted")
            if abs(signal.calibration_base_rate - trusted.calibration_base_rate) > 1e-12:
                raise UntrustedProbabilityProvenance("signal calibration base rate is not trusted")
            if signal.reliability > trusted.maximum_reliability:
                raise UntrustedProbabilityProvenance("signal reliability exceeds trusted limit")
            if signal.calibration_sample_count < trusted.minimum_sample_count:
                raise UntrustedProbabilityProvenance("signal calibration sample is too small")

    trusted_operating_points = {
        (item.operating_point_id, item.operating_point_sha256): item
        for item in registry.camera_operating_points
        if environment in item.allowed_environments
    }
    for camera in request.cameras:
        trusted = trusted_operating_points.get(
            (camera.operating_point_id, camera.operating_point_sha256)
        )
        if trusted is None:
            raise UntrustedProbabilityProvenance("camera operating point is not trusted")
        if abs(camera.sensitivity - trusted.sensitivity) > 1e-12:
            raise UntrustedProbabilityProvenance("camera sensitivity is not trusted")
        if abs(camera.false_positive_rate - trusted.false_positive_rate) > 1e-12:
            raise UntrustedProbabilityProvenance("camera false-positive rate is not trusted")
        if camera.validation_sample_count < trusted.minimum_sample_count:
            raise UntrustedProbabilityProvenance("camera validation sample is too small")

