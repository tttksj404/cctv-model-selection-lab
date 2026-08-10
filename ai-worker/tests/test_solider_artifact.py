import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from qwen_backend.config import Settings
from qwen_backend.main import create_app
from qwen_backend.solider_artifact import inspect_solider_readiness


def _write_asset(path: Path, content: bytes) -> str:
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _manifest(
    checkpoint: Path,
    backbone: Path,
    result: Path,
    checkpoint_sha256: str,
    backbone_sha256: str,
    *,
    location: str = "local_package",
    complete: bool = True,
    status: str = "promoted",
    identity_labels: bool = False,
    track_heldout: bool = False,
) -> dict[str, bool | str | dict[str, bool | str | float]]:
    return {
        "schemaVersion": "solider-server-attribute-candidate-v1",
        "artifactStatus": status,
        "role": "server_attribute_only",
        "modelVersion": "test-solider",
        "checkpointPath": str(checkpoint.relative_to(checkpoint.parents[1])),
        "checkpointSha256": checkpoint_sha256,
        "backboneCheckpointPath": str(backbone.relative_to(backbone.parents[1])),
        "backboneCheckpointSha256": backbone_sha256,
        "resultManifestPath": str(result.relative_to(result.parents[1])),
        "runtime": {
            "artifactLocation": location,
            "completeInferencePackage": complete,
        },
        "evaluation": {
            "identityLabelsAvailable": identity_labels,
            "trackHeldoutMetricsEligible": track_heldout,
            "proxyMetricsReusedAsIdentity": False,
            "cctvIdentityGate": "blocked",
            "pa100kInsF1": 0.87,
            "syntheticProxyAccuracy": 0.94,
        },
    }


def test_remote_candidate_is_not_ready_for_runtime_or_identity(tmp_path: Path) -> None:
    manifest_path = Path("training/solider_server_attribute_candidate.json").resolve()

    readiness = inspect_solider_readiness(manifest_path, Path.cwd())

    assert readiness.server_attribute_ready is False
    assert readiness.final_identity_eligible is False
    assert "artifact_remote_only" in readiness.reasons
    assert "project_identity_labels_unavailable" in readiness.reasons


def test_complete_local_package_can_be_server_attribute_only(tmp_path: Path) -> None:
    checkpoint = tmp_path / "models" / "head.pt"
    backbone = tmp_path / "models" / "backbone.pth"
    result = tmp_path / "results" / "result.json"
    checkpoint.parent.mkdir()
    result.parent.mkdir()
    checkpoint_sha256 = _write_asset(checkpoint, b"head")
    backbone_sha256 = _write_asset(backbone, b"backbone")
    result.write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            _manifest(
                checkpoint,
                backbone,
                result,
                checkpoint_sha256,
                backbone_sha256,
            )
        ),
        encoding="utf-8",
    )

    readiness = inspect_solider_readiness(manifest_path, tmp_path)

    assert readiness.server_attribute_ready is True
    assert readiness.final_identity_eligible is False
    assert "project_identity_labels_unavailable" in readiness.reasons
    assert "artifact_not_promoted" not in readiness.reasons


def test_health_exposes_blocked_server_attribute_candidate(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            provider="mock",
            image_root=tmp_path,
            server_attribute_enabled=True,
            server_attribute_manifest_path=tmp_path / "missing.json",
            server_attribute_workspace=tmp_path,
        )
    )

    with TestClient(app) as client:
        response = client.get("/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "degraded"
    assert payload["serverAttributeEnabled"] is True
    assert payload["serverAttributeReady"] is False
    assert payload["serverAttributeReasons"] == ["invalid_manifest:FileNotFoundError"]

