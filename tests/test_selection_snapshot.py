from __future__ import annotations

import json
import unittest
from pathlib import Path


class ModelSelectionSnapshotTests(unittest.TestCase):
    def test_snapshot_separates_model_roles(self) -> None:
        snapshot_path = Path(__file__).parents[1] / "configs" / "model_selection_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual(snapshot["schemaVersion"], "cctv-model-selection-snapshot-v1")
        self.assertEqual(snapshot["roles"]["embeddedCandidate"]["candidate"], "student_CLIP_hard")
        self.assertEqual(snapshot["roles"]["serverAttribute"]["candidate"], "SOLIDER Swin-B + PAR")
        self.assertEqual(snapshot["roles"]["reid"]["candidateFamily"], "SOLIDER or TransReID family")
        self.assertEqual(snapshot["roles"]["reid"]["mode"], "top_k_retrieval_only")
        self.assertEqual(snapshot["roles"]["generativeReview"]["mode"], "conflict_and_low_confidence_review")

    def test_snapshot_keeps_automatic_identity_match_blocked(self) -> None:
        snapshot_path = Path(__file__).parents[1] / "configs" / "model_selection_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual(snapshot["strictReidDecision"]["automaticIdentityMatch"], "BLOCKED")
        self.assertTrue(snapshot["strictReidDecision"]["candidateRetrieverEnabled"])
        self.assertEqual(snapshot["promotion"]["status"], "NOT_APPROVED")

    def test_snapshot_preserves_runtime_and_ground_truth_limits(self) -> None:
        snapshot_path = Path(__file__).parents[1] / "configs" / "model_selection_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual(snapshot["runtimePolicy"]["status"], "provisional")
        self.assertFalse(snapshot["runtimePolicy"]["productionApproved"])
        self.assertTrue(snapshot["runtimePolicy"]["retrievalOnlyEnforced"])
        self.assertFalse(snapshot["groundTruthLimits"]["crossCameraIdentityAvailable"])
        self.assertEqual(snapshot["currentAttributeProxy"]["metric"], "per_field_top1_mean")
        self.assertEqual(
            snapshot["historicalAttributeProxyComparison"]["status"],
            "historical_proxy_not_current_selection_criterion",
        )


if __name__ == "__main__":
    unittest.main()
