from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.reid_metrics import (
    MetricContractError,
    compute_identity_retrieval_metrics,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "experiments/results/cctv_generalization_method_matrix_20260728.json"


def test_metric_payload_uses_identity_mrr_not_legacy_map() -> None:
    metrics = compute_identity_retrieval_metrics(
        np.asarray([[0.1, 0.9], [0.8, 0.2]], dtype=np.float32),
        ["person-b", "person-a"],
        ["person-a", "person-b"],
    )

    assert metrics["rank1"] == 1.0
    assert metrics["identity_mrr"] == 1.0
    assert "map" not in metrics
    assert "minp" not in metrics


def test_metric_payload_rejects_shape_mismatch() -> None:
    with pytest.raises(MetricContractError, match="scores shape"):
        compute_identity_retrieval_metrics(
            np.asarray([[0.5]], dtype=np.float32),
            ["person-a", "person-b"],
            ["person-a"],
        )


def test_current_matrix_and_consumers_use_identity_mrr_contract() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    strict_rows = [
        row
        for row in matrix["methods"]
        if row.get("metricUnit") == "frame"
        and row.get("protocol") == "strict-cross-camera-sequence"
    ]

    assert len(strict_rows) == 10
    assert all("identityMrr" in row for row in strict_rows)
    assert all("mAP" not in row for row in strict_rows)
    assert matrix["decision"]["bestStrictIdentityMrr"] == pytest.approx(0.6073688008)
    assert "bestStrictMap" not in matrix["decision"]
    for relative_path in (
        "scripts/build_cctv_reid_gpu_notebook.py",
        "scripts/plot_cctv_reid_bubble.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert 'row.get("identityMrr")' in source
        assert 'row.get("mAP")' not in source
