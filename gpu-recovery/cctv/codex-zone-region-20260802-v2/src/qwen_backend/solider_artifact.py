from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ArtifactLocation = Literal["remote_only", "local_package"]
ArtifactStatus = Literal["candidate_not_production", "promoted"]
ArtifactRole = Literal["server_attribute_only"]


class SoliderRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    artifact_location: ArtifactLocation = Field(alias="artifactLocation")
    complete_inference_package: bool = Field(alias="completeInferencePackage")


class SoliderEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    identity_labels_available: bool = Field(alias="identityLabelsAvailable")
    track_heldout_metrics_eligible: bool = Field(alias="trackHeldoutMetricsEligible")
    proxy_metrics_reused_as_identity: bool = Field(alias="proxyMetricsReusedAsIdentity")
    cctv_identity_gate: Literal["blocked", "passed"] = Field(alias="cctvIdentityGate")
    pa100k_ins_f1: float = Field(alias="pa100kInsF1", ge=0.0, le=1.0)
    synthetic_proxy_accuracy: float = Field(alias="syntheticProxyAccuracy", ge=0.0, le=1.0)


class SoliderArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: str = Field(alias="schemaVersion", min_length=1)
    artifact_status: ArtifactStatus = Field(alias="artifactStatus")
    role: ArtifactRole
    model_version: str = Field(alias="modelVersion", min_length=1)
    checkpoint_path: str = Field(alias="checkpointPath", min_length=1)
    checkpoint_sha256: str = Field(alias="checkpointSha256", pattern=r"^[0-9a-fA-F]{64}$")
    backbone_checkpoint_path: str = Field(alias="backboneCheckpointPath", min_length=1)
    backbone_checkpoint_sha256: str = Field(
        alias="backboneCheckpointSha256", pattern=r"^[0-9a-fA-F]{64}$"
    )
    result_manifest_path: str = Field(alias="resultManifestPath", min_length=1)
    runtime: SoliderRuntime
    evaluation: SoliderEvaluation


@dataclass(frozen=True, slots=True)
class SoliderReadiness:
    server_attribute_ready: bool
    final_identity_eligible: bool
    model_version: str | None
    reasons: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_artifact_path(path_value: str, workspace: Path) -> Path:
    path = Path(path_value).expanduser()
    return (path if path.is_absolute() else workspace / path).resolve()


def _verify_local_file(
    path_value: str, expected_sha256: str, workspace: Path, missing_reason: str
) -> str | None:
    path = _resolve_artifact_path(path_value, workspace)
    if workspace not in path.parents:
        return f"{missing_reason}_outside_workspace"
    if not path.is_file():
        return missing_reason
    if _sha256(path).lower() != expected_sha256.lower():
        return f"{missing_reason}_hash_mismatch"
    return None


def inspect_solider_readiness(manifest_path: Path, workspace: Path) -> SoliderReadiness:
    workspace = workspace.expanduser().resolve()
    manifest_file = manifest_path.expanduser()
    manifest_file = (
        manifest_file if manifest_file.is_absolute() else workspace / manifest_file
    ).resolve()
    if workspace not in manifest_file.parents:
        return SoliderReadiness(False, False, None, ("manifest_outside_workspace",))
    reasons: list[str] = []
    try:
        manifest = SoliderArtifactManifest.model_validate_json(
            manifest_file.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        return SoliderReadiness(False, False, None, (f"invalid_manifest:{type(exc).__name__}",))

    if manifest.runtime.artifact_location == "remote_only":
        reasons.append("artifact_remote_only")
    if not manifest.runtime.complete_inference_package:
        reasons.append("inference_package_incomplete")
    for path_value, expected_sha256, missing_reason in (
        (manifest.checkpoint_path, manifest.checkpoint_sha256, "head_checkpoint_unavailable"),
        (
            manifest.backbone_checkpoint_path,
            manifest.backbone_checkpoint_sha256,
            "backbone_checkpoint_unavailable",
        ),
        (manifest.result_manifest_path, "", "result_manifest_unavailable"),
    ):
        if expected_sha256:
            reason = _verify_local_file(path_value, expected_sha256, workspace, missing_reason)
        else:
            path = _resolve_artifact_path(path_value, workspace)
            reason = (
                f"{missing_reason}_outside_workspace"
                if workspace not in path.parents
                else None
                if path.is_file()
                else missing_reason
            )
        if reason is not None:
            reasons.append(reason)

    server_attribute_ready = not reasons
    final_identity_eligible = server_attribute_ready and (
        manifest.artifact_status == "promoted"
        and manifest.evaluation.identity_labels_available
        and manifest.evaluation.track_heldout_metrics_eligible
        and not manifest.evaluation.proxy_metrics_reused_as_identity
        and manifest.evaluation.cctv_identity_gate == "passed"
    )
    if not manifest.evaluation.identity_labels_available:
        reasons.append("project_identity_labels_unavailable")
    if not manifest.evaluation.track_heldout_metrics_eligible:
        reasons.append("track_heldout_metrics_unavailable")
    if manifest.evaluation.proxy_metrics_reused_as_identity:
        reasons.append("proxy_metrics_cannot_authorize_identity")
    if manifest.artifact_status != "promoted":
        reasons.append("artifact_not_promoted")
    return SoliderReadiness(
        server_attribute_ready,
        final_identity_eligible,
        manifest.model_version,
        tuple(dict.fromkeys(reasons)),
    )
