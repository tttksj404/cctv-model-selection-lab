import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.mark.external_research_artifact
def test_person_crop_manifest_is_fresh_and_paired() -> None:
    manifest_path = ROOT / "experiments/data/cctv_proxy/person_only/crop_manifest.jsonl"
    rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 45
    assert sum(row["dataset"] == "simuletic" for row in rows) == 15
    assert sum(row["dataset"] == "pa100k" for row in rows) == 30
    assert all((ROOT / row["output_image"]).is_file() for row in rows)
    assert len({(row["dataset"], row["image"]) for row in rows}) == 45


@pytest.mark.external_research_artifact
def test_comparison_contains_group_bootstrap_and_provenance() -> None:
    comparison = _json("experiments/results/cctv_person_crop_comparison.json")
    assert (
        comparison["contract"]["runtime"]
        == "all original and person-only crop runs use transformers 5.14.1"
    )
    assert comparison["contract"]["bootstrap"].startswith("10000 dataset-group cluster")
    assert comparison["crop_generation"]["detector_weights_sha256"]
    assert comparison["provenance"]["analysis_script"]["sha256"]
    assert comparison["provenance"]["analysis_script"]["sha256"] == _sha256(
        ROOT / "scripts/analyze_cctv_person_crop_results.py"
    )
    assert comparison["provenance"]["crop_manifest"]["sha256"] == _sha256(
        ROOT / comparison["provenance"]["crop_manifest"]["path"]
    )
    assert comparison["provenance"]["crop_summary"]["sha256"] == _sha256(
        ROOT / comparison["provenance"]["crop_summary"]["path"]
    )
    assert len(comparison["models"]) == 5
    for model in comparison["models"]:
        assert len(model["delta"]["bootstrap_95ci_pp_by_group"]) == 2
        assert model["provenance"]["original_result_sha256"]
        assert model["provenance"]["crop_result_sha256"]


@pytest.mark.external_research_artifact
def test_executed_notebook_has_no_error_outputs_and_declares_dependencies() -> None:
    notebook = _json("experiments/cctv_person_crop_comparison.executed.ipynb")
    assert notebook["metadata"]["dependencies"]["packages"]
    assert any(
        "provenance_freshness" in "".join(cell.get("source", []))
        for cell in notebook["cells"]
    )
    assert all(
        not (cell.get("outputs") or [])
        or all(output.get("output_type") != "error" for output in cell["outputs"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )


def test_analysis_source_enforces_pair_identity_and_group_resampling() -> None:
    source = (ROOT / "scripts/analyze_cctv_person_crop_results.py").read_text(encoding="utf-8")
    assert "paired target mismatch" in source
    assert "paired group mismatch" in source
    assert "dataset-group cluster" in source
    assert "_sha256" in source
    assert "_validated_load" in source
    assert "_safe_output_path" in source


@pytest.mark.external_research_artifact
def test_notebook_source_restricts_output_path_and_keeps_qwen_original_default() -> None:
    source = (ROOT / "experiments/cctv_person_crop_notebook_builder.py").read_text(encoding="utf-8")
    assert "_safe_notebook_output" in source
    assert "원본을 기본 입력으로 유지" in source

