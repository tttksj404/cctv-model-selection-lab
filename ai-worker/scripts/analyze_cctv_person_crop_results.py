# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = PROJECT_ROOT / "experiments" / "results"
CROP_ROOT = PROJECT_ROOT / "experiments" / "data" / "cctv_proxy" / "person_only"
EXPECTED_RUNTIME = "5.14.1"
EXPECTED_LABEL_POLICY = "score every non-empty and non-unknown target field per sample"
EXPECTED_P95_DEFINITION = "sorted latency index max(0, int(n * 0.95) - 1)"
MODELS = {
    "clip-vit-l14": ("clip-vit-l14.original-rerun-v5.json", "clip-vit-l14.person-crop-rerun.json"),
    "clip-vit-b32": ("clip-vit-b32.original-rerun-v5.json", "clip-vit-b32.person-crop-rerun.json"),
    "siglip-base": ("siglip-base.original-rerun-v5.json", "siglip-base.person-crop-rerun.json"),
    "blip-base": ("blip-base.original-rerun-v5.json", "blip-base.person-crop-rerun.json"),
    "qwen3-vl-2b": ("qwen3-vl-2b.original-rerun-v5.json", "qwen3-vl-2b.person-crop-rerun.json"),
}
FIELDS = (
    "gender",
    "age",
    "hair_color",
    "viewpoint",
    "top_color",
    "top_type",
    "bottom_color",
    "bottom_type",
    "footwear",
    "accessory",
)


def _dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _load(name: str) -> dict[str, object]:
    return _dict(json.loads((RESULT_ROOT / name).read_text(encoding="utf-8")))


def _validated_load(name: str, model: str) -> dict[str, object]:
    result = _load(name)
    if result.get("status") != "valid" or result.get("model") != model:
        raise SystemExit(f"invalid result contract for {name}")
    runtime = _dict(result.get("runtime"))
    summary = _dict(result.get("summary"))
    evaluation_contract = _dict(_dict(result.get("provenance")).get("evaluation_contract"))
    predictions = result.get("predictions")
    if runtime.get("transformers") != EXPECTED_RUNTIME:
        raise SystemExit(f"runtime mismatch for {name}: expected transformers {EXPECTED_RUNTIME}")
    if summary.get("examples") != 45 or summary.get("groups") != 33:
        raise SystemExit(f"dataset contract mismatch for {name}")
    if evaluation_contract.get("schema_fields") != list(FIELDS):
        raise SystemExit(f"schema contract mismatch for {name}")
    if evaluation_contract.get("label_policy") != EXPECTED_LABEL_POLICY or evaluation_contract.get("p95_definition") != EXPECTED_P95_DEFINITION:
        raise SystemExit(f"evaluation contract mismatch for {name}")
    if not isinstance(predictions, list) or len(predictions) != 45:
        raise SystemExit(f"prediction count mismatch for {name}")
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_output_path(value: Path) -> Path:
    candidate = (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value.resolve()
    if candidate.parent != RESULT_ROOT or candidate.suffix.lower() != ".json":
        raise SystemExit(f"--output must be a JSON file directly under {RESULT_ROOT}")
    if candidate.name in {name for pair in MODELS.values() for name in pair}:
        raise SystemExit("--output cannot overwrite a model result input")
    return candidate


def _predictions(value: dict[str, object]) -> list[dict[str, object]]:
    return [_dict(item) for item in cast(list[object], value.get("predictions", []))]


def _correctness(result: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in _predictions(result):
        target = _dict(item.get("target"))
        predicted = _dict(item.get("predicted"))
        field_correct = {
            field: bool(target.get(field)) and target.get(field) == predicted.get(field)
            for field in FIELDS
            if target.get(field)
        }
        rows.append(
            {
                "image": f"{item.get('dataset', '')}/{Path(str(item.get('image', '')).replace(chr(92), '/')).name}",
                "dataset": str(item.get("dataset", "")),
                "group": str(item.get("group", "")),
                "target": target,
                "field_correct": field_correct,
            }
        )
    return rows


def _row_key(row: dict[str, object]) -> tuple[str, str]:
    return str(row["dataset"]), str(row["image"])


def _align_rows(
    model: str,
    original: list[dict[str, object]],
    crop: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    def indexed(rows: list[dict[str, object]], label: str) -> dict[tuple[str, str], dict[str, object]]:
        result: dict[tuple[str, str], dict[str, object]] = {}
        for row in rows:
            key = _row_key(row)
            if key in result:
                raise SystemExit(f"duplicate paired key for {model} ({label}): {key}")
            result[key] = row
        return result

    original_by_key = indexed(original, "original")
    crop_by_key = indexed(crop, "person_only_crop")
    if set(original_by_key) != set(crop_by_key):
        raise SystemExit(f"paired image mismatch for {model}")
    keys = sorted(original_by_key)
    for key in keys:
        original_row = original_by_key[key]
        crop_row = crop_by_key[key]
        if original_row["group"] != crop_row["group"]:
            raise SystemExit(f"paired group mismatch for {model}: {key}")
        if original_row["target"] != crop_row["target"]:
            raise SystemExit(f"paired target mismatch for {model}: {key}")
    return [original_by_key[key] for key in keys], [crop_by_key[key] for key in keys]


def _micro_accuracy(rows: list[dict[str, object]]) -> float:
    total = 0
    correct = 0
    for row in rows:
        fields = cast(dict[str, bool], row["field_correct"])
        total += len(fields)
        correct += sum(fields.values())
    return correct / total if total else 0.0


def _field_accuracy(rows: list[dict[str, object]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for field in FIELDS:
        values = [cast(dict[str, bool], row["field_correct"])[field] for row in rows if field in row["field_correct"]]
        result[field] = sum(values) / len(values) if values else 0.0
    return result


def _dataset_accuracy(rows: list[dict[str, object]]) -> dict[str, float]:
    return {
        dataset: _micro_accuracy([row for row in rows if row["dataset"] == dataset])
        for dataset in ("simuletic", "pa100k")
    }


def _bootstrap_delta(original: list[dict[str, object]], crop: list[dict[str, object]], seed: int, draws: int) -> list[float]:
    original_by_group: dict[tuple[str, str], list[dict[str, object]]] = {}
    crop_by_group: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in original:
        original_by_group.setdefault((str(row["dataset"]), str(row["group"])), []).append(row)
    for row in crop:
        crop_by_group.setdefault((str(row["dataset"]), str(row["group"])), []).append(row)
    groups = sorted(original_by_group)
    if groups != sorted(crop_by_group):
        raise SystemExit("paired group mismatch during bootstrap")
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(draws):
        sampled_indexes = rng.integers(0, len(groups), size=len(groups))
        original_sample = [row for index in sampled_indexes for row in original_by_group[groups[int(index)]]]
        crop_sample = [row for index in sampled_indexes for row in crop_by_group[groups[int(index)]]]
        values.append((_micro_accuracy(crop_sample) - _micro_accuracy(original_sample)) * 100)
    return values


def _summary(
    model: str,
    original_name: str,
    crop_name: str,
    original_result: dict[str, object],
    crop_result: dict[str, object],
) -> dict[str, object]:
    original, crop = _align_rows(model, _correctness(original_result), _correctness(crop_result))
    bootstrap = _bootstrap_delta(original, crop, seed=20260723, draws=10000)
    delta = (_micro_accuracy(crop) - _micro_accuracy(original)) * 100
    lower = float(np.percentile(bootstrap, 2.5))
    upper = float(np.percentile(bootstrap, 97.5))
    original_fields = _field_accuracy(original)
    crop_fields = _field_accuracy(crop)
    original_datasets = _dataset_accuracy(original)
    crop_datasets = _dataset_accuracy(crop)
    return {
        "model": model,
        "examples": len(original),
        "original": {
            "attribute_accuracy": _micro_accuracy(original),
            "field_accuracy": original_fields,
            "dataset_accuracy": original_datasets,
            "latency_s_p95": _dict(original_result.get("summary")).get("latency_s_p95"),
            "structured_valid_rate": _dict(original_result.get("summary")).get("structured_valid_rate"),
        },
        "person_only_crop": {
            "attribute_accuracy": _micro_accuracy(crop),
            "field_accuracy": crop_fields,
            "dataset_accuracy": crop_datasets,
            "latency_s_p95": _dict(crop_result.get("summary")).get("latency_s_p95"),
            "structured_valid_rate": _dict(crop_result.get("summary")).get("structured_valid_rate"),
        },
        "delta": {
            "attribute_accuracy_pp": delta,
            "bootstrap_95ci_pp_by_group": [lower, upper],
            "field_accuracy_pp": {field: (crop_fields[field] - original_fields[field]) * 100 for field in FIELDS},
            "dataset_accuracy_pp": {dataset: (crop_datasets[dataset] - original_datasets[dataset]) * 100 for dataset in ("simuletic", "pa100k")},
            "latency_s_p95": float(cast(float, _dict(crop_result.get("summary")).get("latency_s_p95", 0))) - float(cast(float, _dict(original_result.get("summary")).get("latency_s_p95", 0))),
            "structured_valid_rate_pp": (float(cast(float, _dict(crop_result.get("summary")).get("structured_valid_rate", 0))) - float(cast(float, _dict(original_result.get("summary")).get("structured_valid_rate", 0)))) * 100,
        },
        "default_candidate": "person_only_crop" if delta > 0 else "original",
        "ci_excludes_zero": lower > 0 or upper < 0,
        "provenance": {
            "original_result": original_name,
            "crop_result": crop_name,
            "original_result_sha256": _sha256(RESULT_ROOT / original_name),
            "crop_result_sha256": _sha256(RESULT_ROOT / crop_name),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("experiments/results/cctv_person_crop_comparison.json"))
    args = parser.parse_args()
    model_results = [
        _summary(
            model,
            original,
            crop,
            _validated_load(original, model),
            _validated_load(crop, model),
        )
        for model, (original, crop) in MODELS.items()
    ]
    manifest = [_dict(json.loads(raw)) for raw in (CROP_ROOT / "crop_manifest.jsonl").read_text(encoding="utf-8").splitlines() if raw.strip()]
    crop_summary = _dict(json.loads((CROP_ROOT / "summary.json").read_text(encoding="utf-8")))
    score_by_dataset = {
        dataset: [float(row["person_score"]) for row in manifest if row["dataset"] == dataset]
        for dataset in ("simuletic", "pa100k")
    }
    crop_area_by_dataset = {
        dataset: [
            (float(row["crop_size"][0]) * float(row["crop_size"][1]))
            / (float(row["source_size"][0]) * float(row["source_size"][1]))
            for row in manifest
            if row["dataset"] == dataset
        ]
        for dataset in ("simuletic", "pa100k")
    }
    output = {
        "status": "measured_proxy_comparison",
        "contract": {
            "paired_examples": 45,
            "datasets": {"simuletic": 15, "pa100k": 30},
            "metric": "micro attribute accuracy over non-empty target fields",
            "bootstrap": "10000 dataset-group cluster resamples, seed 20260723",
            "runtime": "all original and person-only crop runs use transformers 5.14.1",
        },
        "crop_generation": {
            "detector": crop_summary.get("detector", "fasterrcnn_mobilenet_v3_large_320_fpn"),
            "weights": crop_summary.get("weights", "DEFAULT"),
            "weights_url": crop_summary.get("detector_weights_url"),
            "detector_weights_sha256": crop_summary.get("detector_weights_sha256"),
            "threshold_configured": crop_summary.get("threshold_configured"),
            "margin_fraction": crop_summary.get("margin_fraction", 0.05),
            "person_score": {
                dataset: {
                    "min": min(values),
                    "median": float(np.median(values)),
                    "max": max(values),
                    "below_0_5": sum(value < 0.5 for value in values),
                }
                for dataset, values in score_by_dataset.items()
            },
            "crop_area_fraction": {
                dataset: {
                    "min": min(values),
                    "median": float(np.median(values)),
                    "max": max(values),
                }
                for dataset, values in crop_area_by_dataset.items()
            },
        },
        "provenance": {
            "analysis_script": {
                "path": str(Path(__file__).resolve().relative_to(PROJECT_ROOT)),
                "sha256": _sha256(Path(__file__).resolve()),
            },
            "crop_manifest": {
                "path": str((CROP_ROOT / "crop_manifest.jsonl").relative_to(PROJECT_ROOT)),
                "sha256": _sha256(CROP_ROOT / "crop_manifest.jsonl"),
            },
            "crop_summary": {
                "path": str((CROP_ROOT / "summary.json").relative_to(PROJECT_ROOT)),
                "sha256": _sha256(CROP_ROOT / "summary.json"),
            },
            "build_script": {
                "path": "scripts/build_cctv_person_crop_dataset.py",
                "sha256": _sha256(PROJECT_ROOT / "scripts" / "build_cctv_person_crop_dataset.py"),
            },
        },
        "models": model_results,
        "decision": {
            "global_default": "original",
            "reason": "모델별 크롭 효과가 일관되지 않고 실제 CCTV identity track-heldout 라벨 게이트가 아직 충족되지 않음",
            "clip_vit_l14": "person_only_crop_candidate",
            "qwen3_vl_2b": "original",
            "production_change_allowed": False,
        },
    }
    output_path = _safe_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": output["status"], "models": len(model_results), "output": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

