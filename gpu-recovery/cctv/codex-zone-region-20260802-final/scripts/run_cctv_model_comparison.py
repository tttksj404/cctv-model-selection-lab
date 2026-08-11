# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "accelerate>=1.2",
#   "numpy>=2.0",
#   "pillow>=11.0",
#   "torch>=2.1",
#   "torchvision>=0.26",
#   "transformers>=4.57",
# ]
# ///

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import torch
import torchvision
import transformers
from PIL import Image
from transformers import (
    AutoModelForCausalLM,
    AutoModelForZeroShotImageClassification,
    AutoProcessor,
    BlipForConditionalGeneration,
    CLIPModel,
    CLIPProcessor,
    Qwen3VLForConditionalGeneration,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = (PROJECT_ROOT / "experiments" / "models").resolve()

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
EXPECTED_DATASET_COUNTS = {"simuletic": 15, "pa100k": 30}
EXPECTED_GROUP_COUNT = 33
EXPECTED_LABELED_FIELDS = {"simuletic": 9, "pa100k": 5}

CLIP_CHOICES: dict[str, tuple[str, ...]] = {
    "gender": ("female", "male"),
    "age": ("teenager", "young adult", "middle-aged", "elderly"),
    "hair_color": ("black", "brown", "blonde", "red", "gray", "shaved"),
    "viewpoint": ("front view", "side view", "back view"),
    "top_color": (
        "black",
        "white",
        "red",
        "blue",
        "green",
        "yellow",
        "navy blue",
        "gray",
        "brown",
        "beige",
        "khaki",
        "dark grey",
    ),
    "top_type": (
        "t-shirt",
        "shirt",
        "jacket",
        "sweater",
        "hoodie",
        "coat",
        "dress",
        "blouse",
        "leather jacket",
        "knit sweater",
    ),
    "bottom_color": (
        "black",
        "white",
        "red",
        "blue",
        "green",
        "yellow",
        "navy blue",
        "gray",
        "brown",
        "beige",
        "khaki",
        "dark grey",
    ),
    "bottom_type": (
        "jeans",
        "denim jeans",
        "trousers",
        "sweatpants",
        "shorts",
        "skirt",
        "dress",
    ),
    "footwear": ("sneakers", "boots", "dress shoes", "sandals", "heels"),
    "accessory": ("none", "backpack", "handbag", "umbrella", "cap", "sunglasses", "smartphone"),
}

JSON_PROMPT = (
    "You are evaluating one cropped CCTV pedestrian image. Return JSON only, with no markdown. "
    "Use null when a field is not visible. Do not infer identity or protected traits from context. "
    "Allowed keys and values: gender: female|male|null; "
    "age: teenager|young adult|middle-aged|elderly|null; "
    "hair_color: black|brown|blonde|red|gray|shaved|null; viewpoint: front|side|back|null; "
    "top_color and bottom_color: free-form color|null; "
    "top_type and bottom_type: free-form clothing type|null; "
    "footwear: free-form type|null; "
    "accessory: none|backpack|handbag|umbrella|cap|sunglasses|smartphone|null. "
    'JSON schema: {"gender":null,"age":null,"hair_color":null,"viewpoint":null,'
    '"top_color":null,"top_type":null,"bottom_color":null,"bottom_type":null,'
    '"footwear":null,"accessory":null}'
)


@dataclass(frozen=True)
class Example:
    dataset: str
    image: Path
    group: str
    target: dict[str, str]


def _dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_local_model_path(value: str | None, option: str) -> str | None:
    if not value:
        return None
    candidate = Path(value).expanduser().resolve()
    if not candidate.is_dir() or (candidate != MODEL_ROOT and MODEL_ROOT not in candidate.parents):
        raise SystemExit(f"{option} must point to an existing directory under {MODEL_ROOT}")
    return str(candidate)


def _safe_artifact_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


def _safe_error(error: BaseException) -> str:
    text = str(error).splitlines()[-1] if str(error).splitlines() else type(error).__name__
    return text.replace(str(PROJECT_ROOT), "<project>")


def _checkpoint_manifest(checkpoint: str | None) -> list[dict[str, object]]:
    if not checkpoint:
        return []
    root = Path(checkpoint)
    if not root.is_dir() or (root != MODEL_ROOT and MODEL_ROOT not in root.parents):
        return []
    return [
        {
            "path": str(path.relative_to(root)),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _validate_examples(examples: list[Example]) -> None:
    counts = Counter(example.dataset for example in examples)
    if dict(counts) != EXPECTED_DATASET_COUNTS:
        raise SystemExit(
            "comparison contract requires simuletic=15 and pa100k=30 examples; "
            f"got {dict(counts)}"
        )
    unique_images = {example.image.resolve() for example in examples}
    if len(unique_images) != len(examples):
        raise SystemExit("comparison contract requires 45 unique input images")
    unique_groups = {(example.dataset, example.group) for example in examples}
    if len(unique_groups) != EXPECTED_GROUP_COUNT:
        raise SystemExit(
            "comparison contract requires 33 unique dataset groups; "
            f"got {len(unique_groups)}"
        )
    for example in examples:
        expected = EXPECTED_LABELED_FIELDS[example.dataset]
        actual = sum(value not in {"", "unknown"} for value in example.target.values())
        if actual != expected:
            raise SystemExit(
                f"comparison contract requires {expected} labeled fields per "
                f"{example.dataset} example; got {actual} for {example.image.name}"
            )


def _canonical(field: str, value: str) -> str:
    text = value.lower().strip().replace("_", " ")
    if field == "gender":
        if any(token in text for token in ("woman", "female", "girl")):
            return "female"
        if any(token in text for token in ("man", "male", "boy")):
            return "male"
    if field == "viewpoint":
        if "front" in text:
            return "front"
        if "back" in text:
            return "back"
        if "side" in text:
            return "side"
    if field == "accessory":
        if text in {"", "none", "no accessory", "nothing"}:
            return "none"
        for token in ("backpack", "handbag", "umbrella", "sunglasses", "smartphone", "cap"):
            if token in text:
                return token
    return re.sub(r"\s+", " ", text)


def _prediction_value(field: str, value: object) -> str:
    text = _text(value)
    return _canonical(field, text) if text else ""


def _simuletic_examples(root: Path, groups: int) -> list[Example]:
    metadata = root / "metadata.jsonl"
    rows: list[Example] = []
    group_counts: Counter[str] = Counter()
    items = [_dict(json.loads(raw)) for raw in metadata.read_text(encoding="utf-8").splitlines()]
    image_counts = Counter(_text(item.get("image")) for item in items)
    for item in items:
        image_name = _text(item.get("image"))
        image_path = root / image_name
        group = image_name.split("_img", maxsplit=1)[0]
        if image_counts[image_name] != 1 or not image_path.is_file() or group_counts[group] >= 5:
            continue
        attrs = _dict(item.get("attributes"))
        target = {
            "gender": _canonical("gender", _text(attrs.get("gender"))),
            "age": _canonical("age", _text(attrs.get("age"))),
            "hair_color": _canonical("hair_color", _text(attrs.get("hair"))),
            "viewpoint": _canonical("viewpoint", _text(attrs.get("angle"))),
            "top_color": _canonical("top_color", _text(attrs.get("top_color"))),
            "top_type": _canonical("top_type", _text(attrs.get("top_type"))),
            "bottom_color": _canonical("bottom_color", _text(attrs.get("bottom_color"))),
            "bottom_type": _canonical("bottom_type", _text(attrs.get("bottom_type"))),
            "footwear": _canonical("footwear", _text(attrs.get("footwear"))),
            "accessory": _canonical("accessory", _text(attrs.get("accessory"))),
        }
        target = {field: value for field, value in target.items() if value}
        rows.append(Example("simuletic", image_path, group, target))
        group_counts[group] += 1
        if len(group_counts) >= groups and all(count >= 5 for count in group_counts.values()):
            break
    return rows


def _pa_examples(root: Path, limit: int) -> list[Example]:
    rows: list[Example] = []
    for raw in (root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[:limit]:
        item = _dict(json.loads(raw))
        image_name = _text(item.get("image_name"))
        labels = _dict(item.get("labels"))
        image_path = root / image_name
        if not image_path.is_file():
            continue
        accessory_values = [
            name for name in ("HandBag", "ShoulderBag", "Backpack") if int(labels.get(name, 0)) == 1
        ]
        target = {
            "gender": "female" if int(labels.get("Female", 0)) else "male",
            "age": (
                "elderly"
                if int(labels.get("AgeOver60", 0))
                else "teenager"
                if int(labels.get("AgeLess18", 0))
                else "young adult"
            ),
            "viewpoint": (
                "front"
                if int(labels.get("Front", 0))
                else "side"
                if int(labels.get("Side", 0))
                else "back"
            ),
            "accessory": _canonical(
                "accessory", accessory_values[0] if accessory_values else "none"
            ),
            "bottom_type": (
                "trousers"
                if int(labels.get("Trousers", 0))
                else "shorts"
                if int(labels.get("Shorts", 0))
                else "skirt"
                if int(labels.get("SkirtDress", 0))
                else "unknown"
            ),
        }
        rows.append(Example("pa100k", image_path, image_name, target))
    return rows


def _extract_json(text: str) -> dict[str, str]:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match is None:
        return {}
    try:
        parsed = _dict(json.loads(match.group(0)))
    except json.JSONDecodeError:
        return {}
    return {
        field: _canonical(field, _text(parsed.get(field)))
        for field in FIELDS
        if _text(parsed.get(field))
    }


def _caption_to_attributes(text: str) -> dict[str, str]:
    lowered = text.lower()
    result: dict[str, str] = {}
    if any(word in lowered for word in ("woman", "female", "girl")):
        result["gender"] = "female"
    elif any(word in lowered for word in ("man", "male", "boy")):
        result["gender"] = "male"
    for age in ("teenager", "young adult", "middle-aged", "elderly"):
        if age in lowered:
            result["age"] = age
            break
    for viewpoint in ("front", "side", "back"):
        if viewpoint in lowered:
            result["viewpoint"] = viewpoint
            break
    for color in CLIP_CHOICES["hair_color"]:
        if color in lowered and any(token in lowered for token in ("hair", "haired")):
            result["hair_color"] = color
            break
    top_match = re.search(r"wearing (?:a |an )?([a-z ]+?)(?:,| with | and |\.)", lowered)
    if top_match:
        phrase = top_match.group(1).strip()
        result["top_color"] = next((c for c in CLIP_CHOICES["top_color"] if c in phrase), "")
        result["top_type"] = next((t for t in CLIP_CHOICES["top_type"] if t in phrase), "")
    bottom_match = re.search(
        r"(?:with |and |wearing )([a-z ]+?)(?: jeans| pants| trousers| shorts| skirt| "
        r"sweatpants|\.)",
        lowered,
    )
    if bottom_match:
        phrase = bottom_match.group(1).strip()
        result["bottom_color"] = next((c for c in CLIP_CHOICES["bottom_color"] if c in phrase), "")
        result["bottom_type"] = next((t for t in CLIP_CHOICES["bottom_type"] if t in lowered), "")
    result["accessory"] = next(
        (a for a in CLIP_CHOICES["accessory"] if a != "none" and a in lowered), "none"
    )
    return {field: value for field, value in result.items() if value}


def _move_inputs(inputs: object, device: torch.device, dtype: torch.dtype | None = None) -> object:
    if hasattr(inputs, "to"):
        return inputs.to(device, dtype) if dtype is not None else inputs.to(device)
    return inputs


class Runner:
    def __init__(
        self, model_name: str, model_path: str | None, allow_remote_code: bool
    ) -> None:
        self.name = model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_path = model_path
        self.checkpoint = ""
        self.resolved_model_commit: str | None = None
        self.model: object
        self.processor: object
        if model_name == "qwen3-vl-2b":
            checkpoint = model_path or "Qwen/Qwen3-VL-2B-Instruct"
            self.checkpoint = checkpoint
            self.model = Qwen3VLForConditionalGeneration.from_pretrained(
                checkpoint, torch_dtype=torch.float16, device_map="auto"
            )
            self.processor = AutoProcessor.from_pretrained(checkpoint)
        elif model_name in {"florence-2-large", "florence-2-large-ft", "florence-2-base"}:
            if model_path is None and not allow_remote_code:
                raise SystemExit(
                    "Florence requires --florence-path under experiments/models "
                    "or explicit --allow-remote-code"
                )
            checkpoint = model_path or (
                "microsoft/Florence-2-base"
                if model_name == "florence-2-base"
                else "microsoft/Florence-2-large"
            )
            self.checkpoint = checkpoint
            self.model = AutoModelForCausalLM.from_pretrained(
                checkpoint,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=allow_remote_code,
                attn_implementation="eager",
            )
            self.processor = AutoProcessor.from_pretrained(
                checkpoint, trust_remote_code=allow_remote_code
            )
        elif model_name in {"clip-vit-b32", "clip-vit-l14"}:
            checkpoint = model_path or (
                "openai/clip-vit-large-patch14"
                if model_name == "clip-vit-l14"
                else "openai/clip-vit-base-patch32"
            )
            self.checkpoint = checkpoint
            self.model = CLIPModel.from_pretrained(checkpoint, local_files_only=False)
            self.processor = CLIPProcessor.from_pretrained(
                checkpoint, local_files_only=False
            )
            self.model.to(self.device)
        elif model_name == "siglip-base":
            checkpoint = model_path or "google/siglip-base-patch16-224"
            self.checkpoint = checkpoint
            self.model = AutoModelForZeroShotImageClassification.from_pretrained(
                checkpoint, torch_dtype=torch.float16, device_map="auto"
            )
            self.processor = AutoProcessor.from_pretrained(checkpoint)
        elif model_name == "blip-base":
            checkpoint = model_path or "Salesforce/blip-image-captioning-base"
            self.checkpoint = checkpoint
            self.model = BlipForConditionalGeneration.from_pretrained(
                checkpoint, torch_dtype=torch.float16, device_map="auto"
            )
            self.processor = AutoProcessor.from_pretrained(checkpoint)
        else:
            raise ValueError(f"unsupported model: {model_name}")
        config = getattr(self.model, "config", None)
        commit = _text(getattr(config, "_commit_hash", None))
        self.resolved_model_commit = commit or None
        self.model.eval()

    def predict(self, example: Example) -> tuple[dict[str, str], str, float, bool]:
        image = Image.open(example.image).convert("RGB")
        started = time.perf_counter()
        if self.name == "qwen3-vl-2b":
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": str(example.image)},
                        {"type": "text", "text": JSON_PROMPT},
                    ],
                }
            ]
            inputs = self.processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
            )
            inputs = _move_inputs(inputs, self.device)
            input_length = inputs.input_ids.shape[1]
            with torch.inference_mode():
                output = self.model.generate(**inputs, max_new_tokens=128, do_sample=False)
            raw = self.processor.batch_decode(output[:, input_length:], skip_special_tokens=True)[0]
            predicted = _extract_json(raw)
            valid = bool(predicted)
        elif self.name in {
            "florence-2-large",
            "florence-2-large-ft",
            "florence-2-base",
            "blip-base",
        }:
            prompt = "<MORE_DETAILED_CAPTION>" if self.name != "blip-base" else None
            inputs = self.processor(
                text=prompt, images=image, return_tensors="pt"
            ) if prompt is not None else self.processor(images=image, return_tensors="pt")
            inputs = _move_inputs(inputs, self.device, torch.float16)
            with torch.inference_mode():
                output = self.model.generate(
                    **inputs, max_new_tokens=128, do_sample=False, num_beams=1, use_cache=False
                )
            raw = self.processor.batch_decode(output, skip_special_tokens=False)[0]
            predicted = _caption_to_attributes(raw)
            valid = bool(raw.strip())
        else:
            predicted = {}
            raw_parts: list[str] = []
            for field, choices in CLIP_CHOICES.items():
                prompts = [
                    f"a CCTV photo of a person with {choice} {field.replace('_', ' ')}"
                    for choice in choices
                ]
                inputs = self.processor(
                    text=prompts, images=image, return_tensors="pt", padding=True
                )
                inputs = _move_inputs(inputs, self.device)
                with torch.inference_mode():
                    logits = self.model(**inputs).logits_per_image[0]
                choice = choices[int(logits.argmax().item())]
                predicted[field] = _canonical(field, choice)
                raw_parts.append(f"{field}={choice}")
            raw = "; ".join(raw_parts)
            valid = True
        return predicted, raw, time.perf_counter() - started, valid


def _summary(
    examples: list[Example], predictions: list[dict[str, object]], model: str
) -> dict[str, object]:
    field_stats: dict[str, dict[str, float]] = {}
    labeled_counts: dict[str, list[int]] = defaultdict(list)
    all_hits: list[float] = []
    exact_hits: list[float] = []
    for item in predictions:
        if item["error"] is not None:
            continue
        target = cast(dict[str, str], item["target"])
        predicted = cast(dict[str, str], item["predicted"])
        fields = [field for field in target if target[field] != "unknown"]
        labeled_counts[_text(item["dataset"])].append(len(fields))
        hits = [
            float(_prediction_value(field, predicted.get(field)) == target[field])
            for field in fields
        ]
        all_hits.extend(hits)
        exact_hits.append(float(bool(fields) and all(hits)))
        for field, hit in zip(fields, hits, strict=True):
            stats = field_stats.setdefault(field, {"correct": 0.0, "total": 0.0})
            stats["correct"] += hit
            stats["total"] += 1
    track_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in predictions:
        track_groups[_text(item["group"])].append(item)
    track_hits: list[float] = []
    for items in track_groups.values():
        if len(items) < 2:
            continue
        target = cast(dict[str, str], items[0]["target"])
        predicted_items = [cast(dict[str, str], item["predicted"]) for item in items]
        fields = [field for field in target if target[field] != "unknown"]
        field_votes = {
            field: Counter(
                _prediction_value(field, predicted.get(field)) for predicted in predicted_items
            ).most_common(1)[0][0]
            for field in fields
        }
        track_hits.append(
            float(bool(fields) and all(field_votes[field] == target[field] for field in fields))
        )
    latencies = [float(item["latency_s"]) for item in predictions]
    raw_valid = sum(float(bool(item["structured_valid"])) for item in predictions)
    return {
        "model": model,
        "examples": len(examples),
        "groups": len(track_groups),
        "attribute_accuracy": sum(all_hits) / len(all_hits) if all_hits else 0.0,
        "image_exact_match": sum(exact_hits) / len(exact_hits) if exact_hits else 0.0,
        "track_exact_match": sum(track_hits) / len(track_hits) if track_hits else 0.0,
        "track_groups_evaluated": len(track_hits),
        "structured_valid_rate": raw_valid / len(predictions) if predictions else 0.0,
        "labeled_field_count": {
            dataset: {
                "min": min(counts),
                "max": max(counts),
                "mean": sum(counts) / len(counts),
            }
            for dataset, counts in labeled_counts.items()
        },
        "latency_s_p50": statistics.median(latencies) if latencies else 0.0,
        "latency_s_p95": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)]
        if latencies
        else 0.0,
        "field_accuracy": {
            field: stats["correct"] / stats["total"] if stats["total"] else 0.0
            for field, stats in field_stats.items()
        },
    }


def _input_provenance(examples: list[Example], args: argparse.Namespace) -> dict[str, object]:
    dataset_files = {
        _safe_artifact_path(path): _sha256(path)
        for path in (
            Path(args.simuletic_root) / "metadata.jsonl",
            Path(args.pa_root) / "manifest.jsonl",
        )
        if path.is_file()
    }
    image_files = [
        {"path": _safe_artifact_path(example.image), "sha256": _sha256(example.image)}
        for example in examples
    ]
    run_args = {
        key: str(value)
        for key, value in vars(args).items()
        if key not in {"qwen_path", "florence_path", "model_path"}
    }
    return {
        "script_sha256": _sha256(Path(__file__).resolve()),
        "dataset_files": dataset_files,
        "image_files": image_files,
        "run_args": run_args,
        "evaluation_contract": {
            "schema_fields": list(FIELDS),
            "label_policy": "score every non-empty and non-unknown target field per sample",
            "p95_definition": "sorted latency index max(0, int(n * 0.95) - 1)",
        },
    }


def _provenance(
    examples: list[Example], args: argparse.Namespace, runner: Runner
) -> dict[str, object]:
    provenance = _input_provenance(examples, args)
    provenance.update(
        {
            "checkpoint": _safe_artifact_path(Path(runner.checkpoint))
            if Path(runner.checkpoint).is_absolute()
            else runner.checkpoint,
            "resolved_model_commit": runner.resolved_model_commit,
            "checkpoint_manifest": _checkpoint_manifest(runner.model_path),
        }
    )
    return provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        choices=(
            "qwen3-vl-2b",
            "florence-2-large",
            "florence-2-large-ft",
            "florence-2-base",
            "clip-vit-b32",
            "clip-vit-l14",
            "siglip-base",
            "blip-base",
        ),
        required=True,
    )
    parser.add_argument("--qwen-path")
    parser.add_argument("--florence-path")
    parser.add_argument("--model-path")
    parser.add_argument("--allow-remote-code", action="store_true")
    parser.add_argument(
        "--simuletic-root", type=Path, default=Path("experiments/data/cctv_proxy/simuletic")
    )
    parser.add_argument("--pa-root", type=Path, default=Path("experiments/data/cctv_proxy/pa100k"))
    parser.add_argument("--simuletic-groups", type=int, default=3)
    parser.add_argument("--pa-limit", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.qwen_path = _safe_local_model_path(args.qwen_path, "--qwen-path")
    args.florence_path = _safe_local_model_path(args.florence_path, "--florence-path")
    args.model_path = _safe_local_model_path(args.model_path, "--model-path")
    examples = _simuletic_examples(args.simuletic_root, args.simuletic_groups) + _pa_examples(
        args.pa_root, args.pa_limit
    )
    if not examples:
        raise SystemExit("no benchmark examples found")
    _validate_examples(examples)
    model_path = args.model_path
    if args.model == "qwen3-vl-2b":
        model_path = args.qwen_path or model_path
    if args.model.startswith("florence-2"):
        model_path = args.florence_path or model_path
    model_path = _safe_local_model_path(model_path, "--model-path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        runner = Runner(args.model, model_path, args.allow_remote_code)
    except (
        AttributeError,
        ImportError,
        IndexError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        failure = {
            "status": "invalid_runtime",
            "model": args.model,
            "checkpoint": _safe_artifact_path(Path(model_path))
            if model_path
            else args.model,
            "error_type": type(error).__name__,
            "error": _safe_error(error),
            "dataset_counts": dict(Counter(example.dataset for example in examples)),
            "provenance": {
                **_input_provenance(examples, args),
                "checkpoint_manifest": _checkpoint_manifest(model_path),
                "checkpoint": _safe_artifact_path(Path(model_path))
                if model_path
                else args.model,
                "resolved_model_commit": None,
            },
            "summary": {
                "model": args.model,
                "status": "invalid_runtime",
                "examples": len(examples),
                "failed": len(examples),
            },
        }
        args.output.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(failure["summary"], ensure_ascii=False), flush=True)
        raise SystemExit(f"model initialization failed: {type(error).__name__}") from error
    predictions: list[dict[str, object]] = []
    for index, example in enumerate(examples, start=1):
        try:
            predicted, raw, latency, valid = runner.predict(example)
            predictions.append(
                {
                    "index": index,
                    "dataset": example.dataset,
                    "image": str(example.image),
                    "group": example.group,
                    "target": example.target,
                    "predicted": predicted,
                    "raw": raw,
                    "latency_s": latency,
                    "structured_valid": valid,
                    "error": None,
                }
            )
            print(
                json.dumps(
                    {
                        "index": index,
                        "dataset": example.dataset,
                        "latency_s": round(latency, 3),
                        "predicted": predicted,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        except (
            AttributeError,
            IndexError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            predictions.append(
                {
                    "index": index,
                    "dataset": example.dataset,
                    "image": str(example.image),
                    "group": example.group,
                    "target": example.target,
                    "predicted": {},
                    "raw": "",
                    "latency_s": 0.0,
                    "structured_valid": False,
                    "error": _safe_error(error),
                }
            )
            print(
                json.dumps(
                    {"index": index, "dataset": example.dataset, "error": _safe_error(error)},
                    ensure_ascii=False,
                ),
                flush=True,
            )
    error_count = sum(1 for item in predictions if item["error"] is not None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    provenance = _provenance(examples, args, runner)
    if error_count:
        summary: dict[str, object] = {
            "model": args.model,
            "status": "invalid_runtime",
            "examples": len(examples),
            "successful": len(predictions) - error_count,
            "failed": error_count,
        }
        artifact = {
            "status": "invalid_runtime",
            "hardware": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
            "torch": torch.__version__,
            "runtime": {
                "python": sys.version.split()[0],
                "transformers": transformers.__version__,
                "torchvision": torchvision.__version__,
                "cuda": torch.version.cuda,
            },
            "model": args.model,
            "checkpoint": runner.checkpoint,
            "provenance": provenance,
            "dataset_counts": dict(Counter(example.dataset for example in examples)),
            "summary": summary,
            "predictions": predictions,
        }
        args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        raise SystemExit(f"comparison invalid: {error_count} inference errors")
    summary = _summary(examples, predictions, args.model)
    summary["status"] = "valid"
    artifact = {
        "status": "valid",
        "hardware": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "torch": torch.__version__,
        "runtime": {
            "python": sys.version.split()[0],
            "transformers": transformers.__version__,
            "torchvision": torchvision.__version__,
            "cuda": torch.version.cuda,
        },
        "model": args.model,
        "checkpoint": runner.checkpoint,
        "provenance": provenance,
        "dataset_counts": dict(Counter(example.dataset for example in examples)),
        "summary": summary,
        "predictions": predictions,
    }
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
