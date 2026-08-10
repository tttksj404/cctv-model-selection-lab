from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from scripts.build_zone_region_dataset import FEATURE_NAMES, write_dataset
from scripts.train_zone_region_models import (
    load_route_dataset,
    prediction_sha256,
    run_model_suite,
    run_named_model,
    write_commitment_and_read_verified_sealed,
)
from scripts.zone_region_metrics import (
    conditional_zone_probabilities,
    evaluate_zone_predictions,
    wilson_interval,
)


def _raise_import_error(
    name: str,
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    output_dir: Path,
) -> dict[str, Any]:
    del train_x, train_y, test_x, test_y, output_dir
    raise ImportError(name)


def test_conditional_zone_probabilities_sum_to_one_and_preserve_argmax() -> None:
    conditional = conditional_zone_probabilities((0.08, 0.16, 0.04, 0.12))

    assert all(
        math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)
        for actual, expected in zip(conditional, (0.20, 0.40, 0.10, 0.30), strict=True)
    )
    assert math.isclose(sum(conditional), 1.0, rel_tol=0.0, abs_tol=1e-12)
    assert max(range(4), key=conditional.__getitem__) == 1


def test_conditional_zone_probabilities_reject_zero_mass() -> None:
    with pytest.raises(ValueError, match="positive"):
        conditional_zone_probabilities((0.0, 0.0, 0.0, 0.0))


def test_wilson_interval_matches_known_sealed_lower_bound() -> None:
    lower, upper = wilson_interval(successes=4055, total=4481)

    assert math.isclose(lower, 0.895994, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(upper, 0.913176, rel_tol=0.0, abs_tol=1e-6)


def test_prediction_metrics_require_95_percent_lower_bound_for_gate() -> None:
    metrics = evaluate_zone_predictions(
        targets=(1, 2, 3, 4) * 25,
        predictions=(1, 2, 3, 4) * 22 + (2, 3, 4, 1) * 3,
        gate=0.85,
    )

    assert metrics.total == 100
    assert metrics.correct == 88
    assert math.isclose(metrics.accuracy, 0.88, rel_tol=0.0, abs_tol=1e-12)
    assert metrics.wilson95_lower < 0.85
    assert metrics.passed is False


def test_zone_model_features_exclude_labels_and_replay_identity() -> None:
    forbidden_fragments = ("target", "seed", "episode", "cohort")

    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))
    assert not any(
        fragment in feature.lower()
        for feature in FEATURE_NAMES
        for fragment in forbidden_fragments
    )


def test_dataset_manifest_hashes_exact_written_bytes(tmp_path: Path) -> None:
    output = tmp_path / "selection.jsonl"
    metadata = write_dataset(
        output,
        [{"cohort": "selection", "route": "expected_bayes_8", "targetZone": 1}],
    )

    payload = output.read_bytes()
    assert b"\r\n" not in payload
    assert metadata["bytes"] == len(payload)
    assert metadata["sha256"] == hashlib.sha256(payload).hexdigest()


def test_commitment_is_written_before_the_sealed_dataset_is_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commitment_path = tmp_path / "selection_commitment.json"
    sealed_path = tmp_path / "sealed.jsonl"
    sealed_payload = b'{"cohort":"sealed_test"}\n'
    sealed_path.write_bytes(sealed_payload)
    expected_sha256 = hashlib.sha256(sealed_payload).hexdigest()
    events: list[str] = []
    original_write_bytes = Path.write_bytes
    original_read_bytes = Path.read_bytes

    def tracked_write_bytes(path: Path, payload: bytes) -> int:
        if path == commitment_path:
            events.append("commitment_written")
        return original_write_bytes(path, payload)

    def tracked_read_bytes(path: Path) -> bytes:
        if path == sealed_path:
            events.append("sealed_read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "write_bytes", tracked_write_bytes)
    monkeypatch.setattr(Path, "read_bytes", tracked_read_bytes)

    commitment_payload, observed_sealed_payload = (
        write_commitment_and_read_verified_sealed(
            commitment_path=commitment_path,
            commitment={"model": "logistic", "route": "expected_bayes_8"},
            sealed_path=sealed_path,
            expected_sealed_sha256=expected_sha256,
        )
    )

    assert events == ["commitment_written", "sealed_read"]
    assert commitment_path.read_bytes() == commitment_payload
    assert observed_sealed_payload == sealed_payload


def test_sealed_dataset_replacement_is_rejected_after_commitment(tmp_path: Path) -> None:
    commitment_path = tmp_path / "selection_commitment.json"
    sealed_path = tmp_path / "sealed.jsonl"
    sealed_path.write_bytes(b"tampered sealed payload\n")

    with pytest.raises(ValueError, match="precommitted dataset manifest"):
        write_commitment_and_read_verified_sealed(
            commitment_path=commitment_path,
            commitment={"model": "logistic", "route": "expected_bayes_8"},
            sealed_path=sealed_path,
            expected_sealed_sha256=hashlib.sha256(b"original payload\n").hexdigest(),
        )

    assert commitment_path.is_file()


def test_posterior_argmax_emits_a_replayable_artifact(tmp_path: Path) -> None:
    feature_count = len(FEATURE_NAMES)
    train_x = np.zeros((4, feature_count), dtype=np.float32)
    train_y = np.arange(4, dtype=np.int64)
    test_x = np.zeros((4, feature_count), dtype=np.float32)
    test_y = np.arange(4, dtype=np.int64)
    for zone_index in range(4):
        feature_index = FEATURE_NAMES.index(f"final_zone_{zone_index + 1}")
        test_x[zone_index, feature_index] = 1.0

    metrics = run_named_model(
        "posterior_argmax",
        train_x,
        train_y,
        test_x,
        test_y,
        tmp_path,
    )

    artifact_path = tmp_path / metrics["artifact"]
    assert metrics["accuracy"] == 1.0
    assert artifact_path.is_file()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["model"] == "posterior_argmax"
    assert len(artifact["featureIndices"]) == 4


def test_model_suite_propagates_dependency_import_errors(tmp_path: Path) -> None:
    feature_count = len(FEATURE_NAMES)
    values = np.zeros((4, feature_count), dtype=np.float32)
    targets = np.arange(4, dtype=np.int64)

    with pytest.raises(ImportError, match="gpu_catboost"):
        run_model_suite(
            ("gpu_catboost",),
            values,
            targets,
            values,
            targets,
            tmp_path,
            runner=_raise_import_error,
        )


def test_logistic_safe_artifact_matches_in_memory_prediction_digest(tmp_path: Path) -> None:
    feature_count = len(FEATURE_NAMES)
    values = np.zeros((16, feature_count), dtype=np.float32)
    targets = np.asarray(tuple(range(4)) * 4, dtype=np.int64)
    for row_index, target in enumerate(targets):
        values[row_index, FEATURE_NAMES.index(f"final_zone_{target + 1}")] = 1.0

    metrics = run_named_model(
        "logistic",
        values,
        targets,
        values,
        targets,
        tmp_path,
    )
    artifact = tmp_path / str(metrics["artifact"])
    safe_artifact = tmp_path / str(metrics["safeArtifact"])
    safe_model = json.loads(safe_artifact.read_text(encoding="utf-8"))
    coefficients = np.asarray(safe_model["coefficients"], dtype=np.float32)
    intercepts = np.asarray(safe_model["intercepts"], dtype=np.float32)
    classes = np.asarray(safe_model["classes"], dtype=np.int64)
    safe_predictions = classes[np.argmax(values @ coefficients.T + intercepts, axis=1)]

    assert safe_model["sourceArtifactSha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert safe_model["predictionCount"] == len(safe_predictions) == len(targets)
    assert safe_model["predictionSha256"] == metrics["predictionSha256"]
    assert safe_model["predictionSha256"] == prediction_sha256(safe_predictions)
    assert metrics["correct"] == int((safe_predictions == targets).sum())


def test_sealed_result_matches_dataset_manifest_and_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    result = json.loads(
        (root / "experiments/results/zone_region_model_comparison_20260802.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (
            root
            / "experiments/results/evidence/zone_region_dataset_manifest_20260802.json"
        ).read_text(encoding="utf-8")
    )
    selected = result["selected"]
    sealed = selected["sealedMetrics"]

    assert result["schemaVersion"] == "eyesonu-zone-region-model-comparison-v3"
    assert manifest["schemaVersion"] == "eyesonu-zone-region-dataset-v2"
    assert result["selectionDatasetSha256"] == manifest["datasets"]["selection"]["sha256"]
    assert result["sealedDatasetSha256"] == manifest["datasets"]["sealed_test"]["sha256"]
    assert result["datasetManifestSha256"] == hashlib.sha256(
        (
            root
            / "experiments/results/evidence/zone_region_dataset_manifest_20260802.json"
        ).read_bytes()
    ).hexdigest()
    assert result["featureSchemaSha256"] == manifest["featureSchemaSha256"]
    assert result["sealedUsage"] == (
        "sealed file loaded only after the selection commitment was written; "
        "evaluated once for that committed winner"
    )
    assert selected["route"] == "expected_bayes_8"
    assert selected["model"] == "logistic"
    assert selected["sealedMetrics"]["artifactUri"] == (
        "artifacts/models_v6/sealed_selected/expected_bayes_8/logistic/logistic.joblib"
    )
    assert result["activationStatus"] == "experiment_selected_not_integrated"
    assert result["scope"] == {
        "backendContractIntegrated": False,
        "jetsonIntegrated": False,
        "projectCctvEvidence": False,
        "status": "prototype_not_in_official_two_zone_mvp",
        "zoneCount": 4,
    }
    assert result["automaticRecommendationPolicy"] == {
        "minimumJurisdictionMass": 0.5,
        "operationallyApproved": False,
        "policyId": "dashboard_mock_jurisdiction_mass_v1",
        "scope": "dashboard_mock_safety_heuristic",
    }
    assert result["promotionDecision"]["accepted"] is False
    gates = result["promotionDecision"]["gates"]
    assert set(gates) == {
        "calibrationEcePassed",
        "candidateTprAtFarPassed",
        "falseZoneSwitchPassed",
        "officialFourZoneRequirementPresent",
        "projectCctvIdentityTrackHeldoutPassed",
        "runtimeImplementationPresent",
        "sealedPairedRuntimeImprovementPassed",
        "selectionPairedRuntimeImprovementPassed",
        "syntheticProxyWilson85Passed",
    }
    assert gates["syntheticProxyWilson85Passed"] is True
    assert not any(
        passed
        for name, passed in gates.items()
        if name != "syntheticProxyWilson85Passed"
    )
    assert selected["sealedMetrics"]["artifactSha256"] == (
        "75cd8bcaa07f6312a39fe5422f7bf2c49a58bada89be607d16e63b717d55e11f"
    )
    assert sealed["correct"] == sum(
        row[index] for index, row in enumerate(sealed["confusionMatrix"])
    )
    assert sealed["total"] == sum(sum(row) for row in sealed["confusionMatrix"])
    assert sealed["wilson95_lower"] >= sealed["gate"]
    assert sealed["passed"] is True


def test_gpu_evidence_bundle_matches_recorded_hashes() -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = json.loads(
        (
            root
            / "experiments/results/evidence/zone_region_evidence_bundle_20260802.json"
        ).read_text(encoding="utf-8")
    )
    assert bundle["schemaVersion"] == "eyesonu-zone-region-evidence-bundle-v1"
    artifacts = {artifact["role"]: artifact for artifact in bundle["artifacts"]}
    assert set(artifacts) == {
        "comparison_result",
        "gpu_safe_generation_comparison_result",
        "dataset_manifest",
        "selection_dataset",
        "sealed_dataset",
        "selection_commitment",
        "selected_model",
        "selected_model_safe_replay",
    }
    content_by_role: dict[str, bytes] = {}
    for role, artifact in artifacts.items():
        relative_path = Path(artifact["uri"])
        assert not relative_path.is_absolute()
        assert ".." not in relative_path.parts
        artifact_path = root / relative_path
        assert artifact_path.is_file(), f"missing GPU evidence: {artifact_path}"
        stored_payload = artifact_path.read_bytes()
        if artifact["compression"] == "gzip":
            assert len(stored_payload) == artifact["compressedBytes"]
            assert hashlib.sha256(stored_payload).hexdigest() == artifact["compressedSha256"]
            content = gzip.decompress(stored_payload)
        else:
            assert artifact["compression"] == "none"
            content = stored_payload
        assert len(content) == artifact["contentBytes"]
        assert hashlib.sha256(content).hexdigest() == artifact["contentSha256"]
        if "remoteUri" in artifact:
            assert artifact["remoteUri"].startswith("codex-zone-region-20260802-final/")
        content_by_role[role] = content

    result = json.loads(content_by_role["comparison_result"])
    safe_generation_result = json.loads(
        content_by_role["gpu_safe_generation_comparison_result"]
    )
    manifest = json.loads(content_by_role["dataset_manifest"])
    commitment = json.loads(content_by_role["selection_commitment"])

    assert artifacts["comparison_result"]["contentSha256"] == (
        "cd35d7393cff99e3bedbbc8c05bbd23eabb893f35e813c0a7446e06508fdd178"
    )
    safe_generation_artifact = artifacts["gpu_safe_generation_comparison_result"]
    safe_generation_bytes = content_by_role["gpu_safe_generation_comparison_result"]
    assert safe_generation_artifact["canonicalization"] == (
        "remote_bytes_plus_single_terminal_lf"
    )
    assert safe_generation_bytes.endswith(b"\n")
    assert len(safe_generation_bytes[:-1]) == safe_generation_artifact[
        "remoteContentBytes"
    ]
    assert hashlib.sha256(safe_generation_bytes[:-1]).hexdigest() == (
        safe_generation_artifact["remoteContentSha256"]
    )
    assert safe_generation_artifact["remoteContentSha256"] == (
        "eb7c58134d0b25253e760135feb1a3cdb39876460fc3c889b1f2fd0844d7f5c6"
    )
    assert set(safe_generation_result["selectionValidationResults"]) == {
        "representative_4",
        "deployed_runtime_8",
        "expected_bayes_8",
    }
    expected_models = {
        "posterior_argmax",
        "logistic",
        "extra_trees",
        "hist_gradient_boosting",
        "gpu_mlp",
        "gpu_xgboost",
        "gpu_catboost",
    }
    assert all(
        set(route_results) == expected_models
        for route_results in safe_generation_result["selectionValidationResults"].values()
    )
    assert result["selectionDatasetSha256"] == artifacts["selection_dataset"][
        "contentSha256"
    ]
    assert result["sealedDatasetSha256"] == artifacts["sealed_dataset"][
        "contentSha256"
    ]
    assert result["datasetManifestSha256"] == artifacts["dataset_manifest"][
        "contentSha256"
    ]
    assert result["selectionCommitmentSha256"] == artifacts["selection_commitment"][
        "contentSha256"
    ]
    assert result["selected"]["sealedMetrics"]["artifactSha256"] == artifacts[
        "selected_model"
    ]["contentSha256"]
    safe_model = json.loads(content_by_role["selected_model_safe_replay"])
    assert safe_model["schemaVersion"] == "eyesonu-zone-logistic-safe-v1"
    assert safe_model["sourceArtifactSha256"] == artifacts["selected_model"]["contentSha256"]
    assert artifacts["selected_model_safe_replay"]["derivedFromRole"] == "selected_model"
    assert artifacts["selected_model_safe_replay"]["derivedFromContentSha256"] == artifacts[
        "selected_model"
    ]["contentSha256"]
    attestation = artifacts["selected_model_safe_replay"]["gpuGenerationAttestation"]
    assert attestation["remoteResultUri"].startswith(
        "codex-zone-region-20260802-final/artifacts/"
    )
    assert attestation["remoteResultBytes"] == 23662
    assert attestation["remoteResultSha256"] == (
        "eb7c58134d0b25253e760135feb1a3cdb39876460fc3c889b1f2fd0844d7f5c6"
    )
    assert attestation["remoteResultBytes"] == safe_generation_artifact[
        "remoteContentBytes"
    ]
    assert attestation["remoteResultSha256"] == safe_generation_artifact[
        "remoteContentSha256"
    ]
    assert attestation["sourceArtifactSha256"] == artifacts["selected_model"][
        "contentSha256"
    ]
    assert attestation["safeArtifactSha256"] == artifacts[
        "selected_model_safe_replay"
    ]["contentSha256"]
    assert attestation["sealedCorrect"] == 4120
    assert attestation["sealedTotal"] == 4484
    assert attestation["predictionSha256"] == safe_model["predictionSha256"]
    safe_generation_selected = safe_generation_result["selected"]
    assert safe_generation_selected["route"] == result["selected"]["route"]
    assert safe_generation_selected["model"] == result["selected"]["model"]
    assert safe_generation_result["selectionDatasetSha256"] == artifacts[
        "selection_dataset"
    ]["contentSha256"]
    assert safe_generation_result["sealedDatasetSha256"] == artifacts["sealed_dataset"][
        "contentSha256"
    ]
    safe_generation_sealed = safe_generation_selected["sealedMetrics"]
    assert safe_generation_sealed["artifactSha256"] == artifacts["selected_model"][
        "contentSha256"
    ]
    assert safe_generation_sealed["safeArtifactSha256"] == artifacts[
        "selected_model_safe_replay"
    ]["contentSha256"]
    assert safe_generation_sealed["predictionSha256"] == safe_model["predictionSha256"]
    assert safe_generation_sealed["correct"] == 4120
    assert safe_generation_sealed["total"] == 4484
    assert safe_generation_sealed["confusionMatrix"] == result["selected"][
        "sealedMetrics"
    ]["confusionMatrix"]
    assert manifest["datasets"]["selection"]["bytes"] == len(
        content_by_role["selection_dataset"]
    )
    assert manifest["datasets"]["sealed_test"]["bytes"] == len(
        content_by_role["sealed_dataset"]
    )
    assert commitment["route"] == result["selected"]["route"]
    assert commitment["model"] == result["selected"]["model"]
    assert commitment["selectionDatasetSha256"] == result["selectionDatasetSha256"]
    assert commitment["datasetManifestSha256"] == result["datasetManifestSha256"]
    assert commitment["sealedDatasetExpectedSha256"] == result["sealedDatasetSha256"]

    sealed_x, sealed_y = load_route_dataset(
        content_by_role["sealed_dataset"],
        source=Path("sealed_dataset_from_verified_bundle.jsonl"),
        route="expected_bayes_8",
        expected_cohort="sealed_test",
    )
    assert tuple(safe_model["featureNames"]) == FEATURE_NAMES
    coefficients = np.asarray(safe_model["coefficients"], dtype=np.float32)
    intercepts = np.asarray(safe_model["intercepts"], dtype=np.float32)
    classes = np.asarray(safe_model["classes"], dtype=np.int64)
    predictions = classes[np.argmax(sealed_x @ coefficients.T + intercepts, axis=1)]
    expected_total = int(result["selected"]["sealedMetrics"]["total"])
    assert len(sealed_y) == len(predictions) == expected_total == 4484
    assert safe_model["predictionCount"] == expected_total
    assert safe_model["predictionSha256"] == prediction_sha256(predictions)
    replay_correct = int((predictions == sealed_y).sum())
    assert replay_correct == result["selected"]["sealedMetrics"]["correct"] == 4120
    replay_confusion = [
        [int(((sealed_y == actual) & (predictions == predicted)).sum()) for predicted in range(4)]
        for actual in range(4)
    ]
    assert replay_confusion == result["selected"]["sealedMetrics"]["confusionMatrix"]

