import json
from pathlib import Path

from qwen_backend.candidate_model_selection import select_candidate_model


def _comparison() -> dict[str, object]:
    return {
        "schema_version": "solider-ft-sonnet-comparison-v1",
        "arms": {
            "same_run_sonnet_ablation": {
                "requested_79_checkpoint_replay": {
                    "cctv_proxy_group_heldout_mean": {
                        "baseline": 0.856410,
                        "sonnet": 0.830769,
                        "delta": -0.025641,
                    }
                }
            }
        },
        "promotion_gate": {"passed": False},
        "project_cctv_gate": {"passed": False},
    }


def test_existing_sonnet_ablation_keeps_baseline_attribute_head() -> None:
    decision = select_candidate_model(_comparison())

    assert decision.selected_attribute_head == "baseline"
    assert decision.sonnet_promoted is False
    assert decision.observed_delta == -0.025641


def test_sonnet_is_selected_only_when_same_protocol_and_project_gates_improve() -> None:
    comparison = _comparison()
    replay = comparison["arms"]["same_run_sonnet_ablation"]["requested_79_checkpoint_replay"]
    replay["cctv_proxy_group_heldout_mean"] = {
        "baseline": 0.856410,
        "sonnet": 0.876410,
        "delta": 0.02,
    }
    comparison["promotion_gate"] = {"passed": True}
    comparison["project_cctv_gate"] = {"passed": True}

    decision = select_candidate_model(comparison)

    assert decision.selected_attribute_head == "sonnet"
    assert decision.sonnet_promoted is True


def test_repository_comparison_does_not_promote_sonnet() -> None:
    source = Path("experiments/results/solider_ft_sonnet_comparison_20260724.json")
    comparison = json.loads(source.read_text(encoding="utf-8"))

    decision = select_candidate_model(comparison)

    assert decision.selected_attribute_head == "baseline"
    assert decision.sonnet_promoted is False

