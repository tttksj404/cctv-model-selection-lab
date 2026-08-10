from __future__ import annotations

import hashlib
import string
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.type_adapter import TypeAdapter

BoundedScore = Annotated[float, Field(ge=0.0, le=1.0)]


class PromotionValidationError(ValueError):
    pass


_JSON_OBJECT = TypeAdapter(dict[str, object])


class PromotionGateConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    attribute_macro_f1_overall: BoundedScore = Field(alias="attributeMacroF1Overall")
    attribute_macro_f1_per_condition: BoundedScore = Field(alias="attributeMacroF1PerCondition")
    identity_rank1: BoundedScore = Field(alias="identityRank1")
    identity_recall_at5: BoundedScore = Field(alias="identityRecallAt5")
    false_match_rate: BoundedScore = Field(alias="falseMatchRate", le=1.0)
    attribute_ins_f1: BoundedScore = Field(default=0.90, alias="attributeInsF1")
    false_reject_rate: BoundedScore = Field(default=0.10, alias="falseRejectRate")
    review_rate: BoundedScore = Field(default=0.30, alias="reviewRate")
    minimum_identity_count: int = Field(default=10, alias="minimumIdentityCount", ge=1)


class SplitPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    local_video_conditions_are_test_only: Mapping[str, str] = Field(
        alias="localVideoConditionsAreTestOnly"
    )


class TrainingPromotionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    split_policy: SplitPolicy = Field(alias="splitPolicy")
    promotion_gate: PromotionGateConfig = Field(alias="promotionGate")


class CCTVPromotionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["cctv-promotion-metrics-v1"] = Field(alias="schemaVersion")
    status: Literal["valid", "blocked"]
    manifest_path: str = Field(alias="manifestPath", min_length=1)
    manifest_sha256: str = Field(alias="manifestSha256", min_length=64, max_length=64)
    evaluation_evidence_path: str = Field(alias="evaluationEvidencePath", min_length=1)
    evaluation_evidence_sha256: str = Field(
        alias="evaluationEvidenceSha256", min_length=64, max_length=64
    )
    reviewed_identity_tracks: int = Field(alias="reviewedIdentityTracks", ge=0)
    reviewed_identity_count: int = Field(alias="reviewedIdentityCount", ge=0)
    track_heldout_metrics_eligible: bool = Field(alias="trackHeldoutMetricsEligible")
    attribute_macro_f1_overall: BoundedScore = Field(alias="attributeMacroF1Overall")
    attribute_macro_f1_per_condition: Mapping[str, BoundedScore] = Field(
        alias="attributeMacroF1PerCondition"
    )
    identity_rank1: BoundedScore = Field(alias="identityRank1")
    identity_recall_at5: BoundedScore = Field(alias="identityRecallAt5")
    false_match_rate: BoundedScore = Field(alias="falseMatchRate")
    attribute_ins_f1: BoundedScore = Field(alias="attributeInsF1")
    false_reject_rate: BoundedScore = Field(alias="falseRejectRate")
    review_rate: BoundedScore = Field(alias="reviewRate")
    ci_lower_bounds: Mapping[str, BoundedScore] = Field(alias="ciLowerBounds")


class CCTVPromotionReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cctv-promotion-report-v1"]
    status: Literal["valid", "blocked"]
    passed: bool
    reasons: tuple[str, ...]


def validate_promotion_metrics(
    metrics: CCTVPromotionMetrics,
    thresholds: PromotionGateConfig,
    expected_conditions: Mapping[str, str] | None = None,
    workspace: Path | None = None,
) -> CCTVPromotionReport:
    reasons: list[str] = []
    if metrics.status != "valid":
        reasons.append("metric status is not valid")
    if not _is_sha256(metrics.manifest_sha256):
        reasons.append("manifest hash is invalid")
    if not _is_sha256(metrics.evaluation_evidence_sha256):
        reasons.append("evaluation evidence hash is invalid")
    if workspace is None:
        reasons.append("workspace is required to verify promotion evidence")
    else:
        _validate_artifact(
            metrics.manifest_path,
            metrics.manifest_sha256,
            "manifest",
            workspace,
            reasons,
        )
        _validate_artifact(
            metrics.evaluation_evidence_path,
            metrics.evaluation_evidence_sha256,
            "evaluation evidence",
            workspace,
            reasons,
        )
        _validate_promotion_artifacts(metrics, workspace, reasons)
    if metrics.reviewed_identity_tracks <= 0:
        reasons.append("reviewed identity tracks are missing")
    if metrics.reviewed_identity_count < thresholds.minimum_identity_count:
        reasons.append("reviewed identity count is below minimum")
    if not metrics.track_heldout_metrics_eligible:
        reasons.append("track-heldout metrics are not eligible")
    if metrics.attribute_macro_f1_overall < thresholds.attribute_macro_f1_overall:
        reasons.append("overall attribute macro-F1 is below threshold")
    if metrics.identity_rank1 < thresholds.identity_rank1:
        reasons.append("identity Rank-1 is below threshold")
    if metrics.identity_recall_at5 < thresholds.identity_recall_at5:
        reasons.append("identity Recall@5 is below threshold")
    if metrics.false_match_rate > thresholds.false_match_rate:
        reasons.append("false-match rate is above threshold")
    if metrics.attribute_ins_f1 < thresholds.attribute_ins_f1:
        reasons.append("attribute InsF1 is below threshold")
    if metrics.false_reject_rate > thresholds.false_reject_rate:
        reasons.append("false-reject rate is above threshold")
    if metrics.review_rate > thresholds.review_rate:
        reasons.append("review rate is above threshold")
    for metric_label, metric_name, threshold in (
        (
            "overall attribute macro-F1",
            "attributeMacroF1Overall",
            thresholds.attribute_macro_f1_overall,
        ),
        ("attribute InsF1", "attributeInsF1", thresholds.attribute_ins_f1),
        ("identity Rank-1", "identityRank1", thresholds.identity_rank1),
        ("identity Recall@5", "identityRecallAt5", thresholds.identity_recall_at5),
    ):
        lower_bound = metrics.ci_lower_bounds.get(metric_name)
        if lower_bound is None:
            reasons.append(f"{metric_label} CI lower bound is missing")
        elif lower_bound < threshold:
            reasons.append(f"{metric_label} CI lower bound is below threshold")
    conditions = set(expected_conditions or metrics.attribute_macro_f1_per_condition)
    conditions.update(metrics.attribute_macro_f1_per_condition)
    for condition in sorted(conditions):
        score = metrics.attribute_macro_f1_per_condition.get(condition)
        if score is None:
            reasons.append(f"attribute macro-F1 is missing for {condition}")
            continue
        if score < thresholds.attribute_macro_f1_per_condition:
            reasons.append(f"attribute macro-F1 is below threshold for {condition}")
    if not metrics.attribute_macro_f1_per_condition:
        reasons.append("per-condition attribute macro-F1 is missing")
    passed = not reasons
    return CCTVPromotionReport(
        schema_version="cctv-promotion-report-v1",
        status="valid" if passed else "blocked",
        passed=passed,
        reasons=tuple(reasons),
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in string.hexdigits for char in value)


def _validate_artifact(
    path_value: str,
    expected_sha256: str,
    label: str,
    workspace: Path,
    reasons: list[str],
) -> None:
    candidate = Path(path_value)
    if candidate.is_absolute() or ".." in candidate.parts:
        reasons.append(f"{label} path must stay relative to workspace")
        return
    try:
        workspace_path = workspace.resolve(strict=True)
        resolved = (workspace_path / candidate).resolve(strict=True)
    except OSError:
        reasons.append(f"{label} file is missing")
        return
    if resolved == workspace_path or workspace_path not in resolved.parents:
        reasons.append(f"{label} path escapes workspace")
        return
    try:
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    except OSError:
        reasons.append(f"{label} file cannot be hashed")
        return
    if digest != expected_sha256.lower():
        reasons.append(f"{label} hash does not match content")


def _validate_promotion_artifacts(
    metrics: CCTVPromotionMetrics,
    workspace: Path,
    reasons: list[str],
) -> None:
    manifest = _resolve_artifact(metrics.manifest_path, workspace)
    if manifest is not None:
        rows = _read_jsonl_objects(manifest)
        if rows is None:
            reasons.append("manifest is not valid JSONL")
        else:
            track_ids = _distinct_strings(rows, "trackId", "sourceTrackId")
            identity_ids = _distinct_strings(rows, "identityGroupId")
            if len(track_ids) < metrics.reviewed_identity_tracks:
                reasons.append("manifest has fewer reviewed identity tracks than reported")
            if len(identity_ids) < metrics.reviewed_identity_count:
                reasons.append("manifest has fewer reviewed identities than reported")

    evidence = _resolve_artifact(metrics.evaluation_evidence_path, workspace)
    if evidence is not None:
        payload = _read_json_object(evidence)
        if payload is None:
            reasons.append("evaluation evidence is not a JSON object")
            return
        if payload.get("measurementStatus") != "identity_measured_sealed_test":
            reasons.append("evaluation evidence is not a sealed identity result")
        eligibility = _object_mapping(payload.get("evaluationEligibility"))
        if eligibility is None:
            reasons.append("evaluation evidence eligibility is missing")
        else:
            if eligibility.get("identityLabelsAvailable") is not True:
                reasons.append("evaluation evidence identity labels are unavailable")
            if eligibility.get("trackHeldoutMetricsEligible") is not True:
                reasons.append("evaluation evidence is not track-heldout eligible")
            if eligibility.get("proxyMetricsReusedAsIdentity") is not False:
                reasons.append("evaluation evidence reuses proxy metrics as identity")
        identity_report = _object_mapping(payload.get("identityReport"))
        if identity_report is None:
            reasons.append("evaluation evidence identity report is missing")
        else:
            if identity_report.get("status") != "valid":
                reasons.append("evaluation evidence identity report is not valid")
            gallery_track_count = identity_report.get("galleryTrackCount")
            if not isinstance(gallery_track_count, int) or isinstance(gallery_track_count, bool):
                reasons.append("evaluation evidence gallery track count is missing")
            elif gallery_track_count <= 0:
                reasons.append("evaluation evidence gallery tracks are missing")


def _resolve_artifact(path_value: str, workspace: Path) -> Path | None:
    candidate = Path(path_value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        workspace_path = workspace.resolve(strict=True)
        resolved = (workspace_path / candidate).resolve(strict=True)
    except OSError:
        return None
    if resolved == workspace_path or workspace_path not in resolved.parents:
        return None
    return resolved


def _read_jsonl_objects(path: Path) -> tuple[dict[str, object], ...] | None:
    try:
        rows = tuple(
            _JSON_OBJECT.validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    except (OSError, ValueError):
        return None
    return rows


def _read_json_object(path: Path) -> dict[str, object] | None:
    try:
        return _JSON_OBJECT.validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _object_mapping(value: object) -> dict[str, object] | None:
    try:
        return _JSON_OBJECT.validate_python(value)
    except ValueError:
        return None


def _distinct_strings(rows: tuple[dict[str, object], ...], *keys: str) -> set[str]:
    values: set[str] = set()
    for row in rows:
        for key in keys:
            value = row.get(key)
            if isinstance(value, str) and value:
                values.add(value)
                break
    return values

