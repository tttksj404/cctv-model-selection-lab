import hashlib
import json
from pathlib import Path

from qwen_backend.cctv_promotion_contract import (
    CCTVPromotionMetrics,
    PromotionGateConfig,
    validate_promotion_metrics,
)


def _thresholds() -> PromotionGateConfig:
    return PromotionGateConfig.model_validate(
        {
            "attributeMacroF1Overall": 0.85,
            "attributeMacroF1PerCondition": 0.85,
            "identityRank1": 0.85,
            "identityRecallAt5": 0.95,
            "falseMatchRate": 0.05,
        }
    )


def _metrics(workspace: Path) -> CCTVPromotionMetrics:
    manifest = workspace / "manifest.jsonl"
    evidence = workspace / "evaluation.json"
    manifest.write_text(
        "".join(
            json.dumps(
                {
                    "trackId": f"track-{index}",
                    "identityGroupId": f"person-{index}",
                    "split": "gallery",
                }
            )
            + "\n"
            for index in range(12)
        ),
        encoding="utf-8",
    )
    evidence.write_text(
        json.dumps(
            {
                "measurementStatus": "identity_measured_sealed_test",
                "evaluationEligibility": {
                    "identityLabelsAvailable": True,
                    "trackHeldoutMetricsEligible": True,
                    "proxyMetricsReusedAsIdentity": False,
                },
                "identityReport": {"status": "valid", "galleryTrackCount": 12},
            }
        ),
        encoding="utf-8",
    )
    return CCTVPromotionMetrics.model_validate(
        {
            "schemaVersion": "cctv-promotion-metrics-v1",
            "status": "valid",
            "manifestPath": "manifest.jsonl",
            "manifestSha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "evaluationEvidencePath": "evaluation.json",
            "evaluationEvidenceSha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            "reviewedIdentityTracks": 12,
            "reviewedIdentityCount": 12,
            "trackHeldoutMetricsEligible": True,
            "attributeMacroF1Overall": 0.90,
            "attributeMacroF1PerCondition": {"landscape_room": 0.86},
            "identityRank1": 0.90,
            "identityRecallAt5": 0.97,
            "falseMatchRate": 0.02,
            "attributeInsF1": 0.92,
            "falseRejectRate": 0.05,
            "reviewRate": 0.20,
            "ciLowerBounds": {
                "attributeMacroF1Overall": 0.88,
                "attributeInsF1": 0.91,
                "identityRank1": 0.88,
                "identityRecallAt5": 0.96,
            },
        }
    )


def test_promotion_gate_accepts_all_thresholds(tmp_path: Path) -> None:
    report = validate_promotion_metrics(_metrics(tmp_path), _thresholds(), workspace=tmp_path)

    assert report.status == "valid"
    assert report.passed is True
    assert report.reasons == ()


def test_promotion_gate_blocks_missing_identity_labels(tmp_path: Path) -> None:
    metrics = _metrics(tmp_path).model_copy(
        update={"reviewed_identity_tracks": 0, "track_heldout_metrics_eligible": False}
    )

    report = validate_promotion_metrics(metrics, _thresholds(), workspace=tmp_path)

    assert report.status == "blocked"
    assert report.passed is False
    assert "reviewed identity tracks are missing" in report.reasons


def test_promotion_gate_blocks_condition_below_threshold(tmp_path: Path) -> None:
    metrics = _metrics(tmp_path).model_copy(
        update={"attribute_macro_f1_per_condition": {"landscape_room": 0.84}}
    )

    report = validate_promotion_metrics(metrics, _thresholds(), workspace=tmp_path)

    assert report.status == "blocked"
    assert any("landscape_room" in reason for reason in report.reasons)


def test_promotion_gate_blocks_missing_condition(tmp_path: Path) -> None:
    report = validate_promotion_metrics(
        _metrics(tmp_path),
        _thresholds(),
        {"landscape_room": "test_landscape", "portrait_fisheye": "test_portrait_fisheye"},
        workspace=tmp_path,
    )

    assert report.status == "blocked"
    assert any("portrait_fisheye" in reason for reason in report.reasons)


def test_promotion_gate_checks_extra_condition(tmp_path: Path) -> None:
    metrics = _metrics(tmp_path).model_copy(
        update={"attribute_macro_f1_per_condition": {"landscape_room": 0.86, "night": 0.2}}
    )

    report = validate_promotion_metrics(metrics, _thresholds(), workspace=tmp_path)

    assert report.status == "blocked"
    assert any("night" in reason for reason in report.reasons)


def test_promotion_gate_blocks_operational_metrics_below_threshold(tmp_path: Path) -> None:
    metrics = _metrics(tmp_path).model_copy(
        update={
            "false_reject_rate": 0.20,
            "review_rate": 0.40,
            "attribute_ins_f1": 0.89,
            "ci_lower_bounds": {
                "attributeMacroF1Overall": 0.86,
                "attributeInsF1": 0.89,
                "identityRank1": 0.84,
                "identityRecallAt5": 0.94,
            },
        }
    )

    report = validate_promotion_metrics(metrics, _thresholds(), workspace=tmp_path)

    assert report.status == "blocked"
    assert "false-reject rate is above threshold" in report.reasons
    assert "review rate is above threshold" in report.reasons
    assert "attribute InsF1 is below threshold" in report.reasons
    assert "identity Rank-1 CI lower bound is below threshold" in report.reasons


def test_promotion_gate_blocks_missing_confidence_intervals(tmp_path: Path) -> None:
    metrics = _metrics(tmp_path).model_copy(update={"ci_lower_bounds": {}})

    report = validate_promotion_metrics(metrics, _thresholds(), workspace=tmp_path)

    assert report.status == "blocked"
    assert "identity Rank-1 CI lower bound is missing" in report.reasons


def test_promotion_gate_blocks_changed_manifest(tmp_path: Path) -> None:
    metrics = _metrics(tmp_path)
    (tmp_path / "manifest.jsonl").write_text("changed\n", encoding="utf-8")

    report = validate_promotion_metrics(metrics, _thresholds(), workspace=tmp_path)

    assert report.status == "blocked"
    assert "manifest hash does not match content" in report.reasons
