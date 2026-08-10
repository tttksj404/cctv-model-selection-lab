from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal, TypeAlias

PolicyName: TypeAlias = Literal[
    "static_representative",
    "deployed_runtime",
    "pure_information_gain",
    "hybrid_eig_0_25",
    "hybrid_eig_0_50",
    "hybrid_eig_0_75",
    "expected_detection",
    "risk_adjusted_detection_0_5",
    "risk_adjusted_detection_1_0",
    "risk_adjusted_detection_2_0",
    "expected_bayes_accuracy",
    "expected_resolution_0_55",
]

POLICIES: Final[tuple[PolicyName, ...]] = (
    "static_representative",
    "deployed_runtime",
    "pure_information_gain",
    "hybrid_eig_0_25",
    "hybrid_eig_0_50",
    "hybrid_eig_0_75",
    "expected_detection",
    "risk_adjusted_detection_0_5",
    "risk_adjusted_detection_1_0",
    "risk_adjusted_detection_2_0",
    "expected_bayes_accuracy",
    "expected_resolution_0_55",
)

RUNTIME_POLICY_IDS: Final[Mapping[PolicyName, str]] = MappingProxyType(
    {
        "static_representative": "static_representative",
        "deployed_runtime": "lr_hmm_posterior_weighted_coverage_eig_tiebreak",
        "pure_information_gain": "lr_hmm_pure_information_gain",
        "hybrid_eig_0_25": "lr_hmm_hybrid_eig_0_25",
        "hybrid_eig_0_50": "lr_hmm_hybrid_eig_0_50",
        "hybrid_eig_0_75": "lr_hmm_hybrid_eig_0_75",
        "expected_detection": "lr_hmm_expected_detection",
        "risk_adjusted_detection_0_5": "lr_hmm_risk_adjusted_detection_0_5",
        "risk_adjusted_detection_1_0": "lr_hmm_risk_adjusted_detection_1_0",
        "risk_adjusted_detection_2_0": "lr_hmm_risk_adjusted_detection_2_0",
        "expected_bayes_accuracy": "lr_hmm_expected_bayes_accuracy",
        "expected_resolution_0_55": "lr_hmm_expected_resolution_0_55",
    }
)

RUNTIME_POLICY_IMPLEMENTATIONS: Final[Mapping[PolicyName, tuple[str, str]]] = MappingProxyType(
    {"deployed_runtime": ("qwen_backend.zone_probability", "assess_zone_probability")}
)
IMPLEMENTED_RUNTIME_POLICIES: Final[frozenset[PolicyName]] = frozenset(
    RUNTIME_POLICY_IMPLEMENTATIONS
)

EXPECTED_PUBLIC_REID_CANONICAL_SHA256: Final = (
    "1b898f6d4a9bc6fe185e0e38c7cb971a5293df0e997f3b5738681f37b07df152"
)
EXPECTED_PAIRED_EVIDENCE_SHA256: Final = (
    "cb9ab656127bc6d374d7e34f3985722c35f37ba9d235257b16e8993598752f3e"
)
REPLAY_KIND: Final = "deterministic Monte Carlo counterfactual proxy"
EXPECTED_MAX_SCANS: Final = 8
SCENARIOS: Final = (
    "location_certain",
    "location_uncertain",
    "currently_inside",
    "recording_only_or_outside",
)
OPERATING_POINT_VALUES: Final = (
    ("validation_wilson_conservative", 0.84, 0.09, 0.10),
    ("degraded_camera", 0.70, 0.15, 0.20),
    ("occlusion_stress", 0.60, 0.18, 0.25),
)
PROMOTION_REASON: Final = (
    "The public ReID artifact is a proxy and the four-zone topology replay is simulated; "
    "synchronized project-camera counterfactual observations are absent."
)

