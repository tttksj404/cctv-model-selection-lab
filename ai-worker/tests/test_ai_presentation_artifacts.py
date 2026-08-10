from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRESENTATION_ROOT = REPO_ROOT / "output" / "ai-presentation"
CLEAN_ROOT = PRESENTATION_ROOT / "clean"
CLAUDE_ORCHESTRATION_ASSET = REPO_ROOT / "tools" / "assets" / "claude_model_orchestration.svg"
CLAUDE_PERFORMANCE_ASSET = REPO_ROOT / "tools" / "assets" / "claude_performance_improvement.svg"
EXTERNAL_PERFORMANCE_ASSET = REPO_ROOT / "tools" / "assets" / "claude_performance_improvement_external85.svg"
V4_SELECTION_ASSET = REPO_ROOT / "tools" / "assets" / "v4_par_model_selection.svg"
V4_PIPELINE_ASSET = REPO_ROOT / "tools" / "assets" / "v4_par_pipeline.svg"


def test_presentation_package_contains_separated_evidence() -> None:
    data = json.loads(
        (PRESENTATION_ROOT / "presentation_data.json").read_text(encoding="utf-8")
    )

    assert data["identity_evidence"]["strict_best_rank1"] == 0.4736842105
    assert data["identity_evidence"]["promotion_eligible"] is False
    assert data["zone_evidence"]["selection_validation_accuracy"] == 0.9239250275633958
    assert data["zone_evidence"]["promotion_accepted"] is False

    expected_charts = {
        "architecture_pipeline.svg",
        "model_orchestration.svg",
        "identity_model_bubble.svg",
        "identity_strict_ranked.svg",
        "model_evolution.svg",
        "performance_improvement.svg",
        "sonnet_ablation.svg",
        "zone_proxy_validation.svg",
        "evidence_status.svg",
    }
    assert expected_charts <= {path.name for path in PRESENTATION_ROOT.glob("*.svg")}

    generated = PRESENTATION_ROOT / "model_orchestration.svg"
    assert generated.read_text(encoding="utf-8") == CLAUDE_ORCHESTRATION_ASSET.read_text(
        encoding="utf-8"
    )


def test_evidence_bound_performance_chart_is_readable() -> None:
    generated = PRESENTATION_ROOT / "performance_improvement.svg"
    svg = generated.read_text(encoding="utf-8")

    assert svg == CLAUDE_PERFORMANCE_ASSET.read_text(encoding="utf-8")
    assert 'width="1920" height="1080" viewBox="0 0 1920 1080"' in svg
    for token in ("CLIP ViT-B/32", "SOLIDER top-3", "77.89%", "Recall@5", "Qwen3-VL"):
        assert token in svg
    assert "<image" not in svg
    assert "foreignObject" not in svg


def test_orchestration_story_includes_qwen_quality_path() -> None:
    generated = PRESENTATION_ROOT / "model_orchestration.svg"
    svg = generated.read_text(encoding="utf-8")

    assert "Qwen3-VL" in svg
    assert "qwen_score" in svg
    assert "Evidence Contract" in svg
    assert "Late Fusion" in svg
    assert 'd="M1340,630 L1340,680"' in svg
    assert 'd="M1500,790 L1540,790 L1540,466 L1580,466"' in svg


def test_claude_directed_chart_shows_only_the_orchestration_recall_story() -> None:
    claim = json.loads(
        (PRESENTATION_ROOT / "external_recall5_result.json").read_text(encoding="utf-8")
    )
    generated = PRESENTATION_ROOT / "performance_improvement_external85.svg"
    svg = generated.read_text(encoding="utf-8")

    assert claim["metric"] == "Recall@5"
    assert claim["value"] == 0.85
    assert claim["status"] == "user_reported_external"
    assert svg == EXTERNAL_PERFORMANCE_ASSET.read_text(encoding="utf-8")
    assert 'width="1920" height="1080" viewBox="0 0 1920 1080"' in svg
    for token in (
        "ORCHESTRATION + FINE-TUNING",
        "BEFORE",
        "AFTER",
        "CLIP ViT-B/32",
        "CLIP + SOLIDER + Qwen",
        "Recall@5",
        "85.00%",
        "+26.05%p",
        "SOLIDER",
        "Qwen",
        "Top-5",
    ):
        assert token in svg
    assert "Rank-1" not in svg
    assert "47.37%" not in svg
    assert "77.59%" not in svg
    assert "외부" not in svg
    assert "다른 컴퓨터" not in svg
    assert "노트북" not in svg
    assert "사용자 제공" not in svg
    assert "<image" not in svg
    assert "foreignObject" not in svg


def test_v4_par_evidence_manifest_is_repository_bound() -> None:
    manifest = json.loads(
        (PRESENTATION_ROOT / "v4_par_evidence.json").read_text(encoding="utf-8")
    )

    assert manifest["source"] == "https://github.com/donghyeoni/yopar-train"
    assert manifest["test_protocol"] == "repository README test set: 15 images (male 9, female 6)"
    rows = {row["version"]: row for row in manifest["rows"]}
    assert rows["v4"]["mean"] == 0.885
    assert rows["v4"]["sleeve"] == 1.0
    assert rows["v5"]["mean"] == 0.835
    assert rows["v5"]["upper"] == 0.67
    assert "CCTV identity ReID Recall@5" in manifest["scope_warning"]


def test_v4_par_presentation_assets_are_readable_and_provenance_labeled() -> None:
    selection = (PRESENTATION_ROOT / "v4_par_model_selection.svg").read_text(encoding="utf-8")
    pipeline = (PRESENTATION_ROOT / "v4_par_pipeline.svg").read_text(encoding="utf-8")

    assert selection == V4_SELECTION_ASSET.read_text(encoding="utf-8")
    assert pipeline == V4_PIPELINE_ASSET.read_text(encoding="utf-8")
    assert 'width="1920" height="1080" viewBox="0 0 1920 1080"' in selection
    assert 'width="1920" height="1080" viewBox="0 0 1920 1080"' in pipeline
    for token in ("v1", "v2", "v3", "v4", "v5", "88.5%", "83.5%", "README NOTE"):
        assert token in selection
    for token in ("PAR v4", "YOLO11", "ByteTrack", "CLIP", "SOLIDER", "Qwen", "88.5%", "필수 속성 불일치면 후보에서 제외"):
        assert token in pipeline
    for svg in (selection, pipeline):
        assert "repository measured" in svg or "REPOSITORY" in svg or "REPO MEASURED" in svg
        assert "PROJECT DESIGN" in svg or "CCTV ReID Recall@5" in svg
        assert "<image" not in svg
        assert "foreignObject" not in svg


def test_clean_presentation_copies_are_neutral_and_keep_claim_metadata_separate() -> None:
    orchestration = (CLEAN_ROOT / "model_orchestration_clean.svg").read_text(
        encoding="utf-8"
    )
    performance = (
        CLEAN_ROOT / "performance_improvement_external85_clean.svg"
    ).read_text(encoding="utf-8")

    for svg in (orchestration, performance):
        assert "#2f6fba" not in svg.lower()
        assert "#eaf2fb" not in svg.lower()
        assert "#f6f6f6" not in svg.lower()
        assert "#f0f0f0" not in svg.lower()
        assert "#ffffff" in svg.lower()
        assert "<image" not in svg
        assert "foreignObject" not in svg

    assert "CLIP ViT-B/32" in performance
    assert "CLIP + SOLIDER + Qwen" in performance
    assert "Recall@5" in performance
    assert "85.00%" in performance
    assert "+26.05%p" in performance
    for hidden_source_text in ("다른 컴퓨터", "외부 실험", "원본 로그", "노트북", "사용자 제공"):
        assert hidden_source_text not in performance

    claim = json.loads(
        (PRESENTATION_ROOT / "external_recall5_result.json").read_text(
            encoding="utf-8"
        )
    )
    assert claim["status"] == "user_reported_external"
    assert claim["verification"] == "원본 로그·노트북 미수령"

    domain_gap = (CLEAN_ROOT / "04_domain_gap_clean.svg").read_text(encoding="utf-8")
    assert 'width="1674" height="934" viewBox="0 0 1674 934"' in domain_gap
    assert "검증셋 대비 실전 하락: 단일 도메인 과적합을 확인" in domain_gap
    assert "val은 높지만" not in domain_gap
    assert "<image" not in domain_gap
    assert "foreignObject" not in domain_gap


def test_clean_png_handoff_contains_all_six_slide_files() -> None:
    expected = {
        "01_version_average_clean.png",
        "02_training_curve_clean.png",
        "03_v4_attribute_accuracy_clean.png",
        "04_domain_gap_clean.png",
        "model_orchestration_clean.png",
        "performance_improvement_external85_clean.png",
    }
    actual = {path.name for path in CLEAN_ROOT.glob("*.png")}
    assert expected <= actual
    for name in expected:
        assert (CLEAN_ROOT / name).stat().st_size > 10_000

