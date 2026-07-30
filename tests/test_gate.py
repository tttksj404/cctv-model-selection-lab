from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cctv_eval_harness.gate import evaluate


POLICY = {
    "thresholds": {
        "attributeMacroF1": 0.85,
        "identityRank1": 0.85,
        "identityRecallAt5": 0.95,
        "falseMatchRateMaximum": 0.05,
    }
}


class PromotionGateTests(unittest.TestCase):
    def _approved_payload(self, workspace: Path) -> dict[str, object]:
        manifest = workspace / "manifest.json"
        evidence = workspace / "evaluation.json"
        manifest.write_text(json.dumps({"kind": "synthetic manifest"}), encoding="utf-8")
        evidence.write_text(json.dumps({"kind": "synthetic sealed result"}), encoding="utf-8")
        return {
            "schemaVersion": "cctv-candidate-evaluation-v1",
            "candidate": "synthetic-candidate",
            "measurementScope": "sealed_identity_track_heldout",
            "identityLabelsAvailable": True,
            "trackHeldoutEligible": True,
            "humanReviewComplete": True,
            "artifactRefs": [
                {"path": manifest.name, "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()},
                {"path": evidence.name, "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()},
            ],
            "metrics": {
                "attributeMacroF1": 0.90,
                "identityRank1": 0.90,
                "identityRecallAt5": 0.97,
                "falseMatchRate": 0.02,
            },
        }

    def test_approves_complete_synthetic_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            report = evaluate(self._approved_payload(workspace), POLICY, workspace)
        self.assertEqual(report["status"], "APPROVED")
        self.assertEqual(report["reasons"], [])

    def test_blocks_proxy_metrics_without_identity_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            payload = self._approved_payload(workspace)
            payload.update(
                {
                    "measurementScope": "proxy_attribute_benchmark",
                    "identityLabelsAvailable": False,
                    "trackHeldoutEligible": False,
                    "humanReviewComplete": False,
                    "artifactRefs": [],
                }
            )
            report = evaluate(payload, POLICY, workspace)
        self.assertEqual(report["status"], "NOT_APPROVED")
        self.assertIn("independent identity labels are unavailable", report["reasons"])

    def test_blocks_artifact_path_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            payload = self._approved_payload(workspace)
            payload["artifactRefs"] = [{"path": "../outside.json", "sha256": "0" * 64}]
            report = evaluate(payload, POLICY, workspace)
        self.assertEqual(report["status"], "NOT_APPROVED")
        self.assertIn("artifact path escapes workspace: ../outside.json", report["reasons"])


if __name__ == "__main__":
    unittest.main()

