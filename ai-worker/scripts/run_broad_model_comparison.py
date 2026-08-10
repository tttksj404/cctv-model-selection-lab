from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import cast

import run_cctv_model_comparison as base
import torch
from PIL import Image
from transformers import (
    AutoModelForImageTextToText,
    AutoModelForZeroShotImageClassification,
    AutoProcessor,
    Qwen2_5_VLForConditionalGeneration,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = (PROJECT_ROOT / "experiments" / "models").resolve()

MODEL_SPECS: dict[str, tuple[str, str, bool]] = {
    "siglip2-base-224": ("google/siglip2-base-patch16-224", "encoder", False),
    "siglip2-base-384": ("google/siglip2-base-patch16-384", "encoder", False),
    "qwen2.5-vl-3b": ("Qwen/Qwen2.5-VL-3B-Instruct", "qwen", False),
    "gemma3-4b": ("google/gemma-3-4b-it", "vlm", False),
    "smolvlm2-500m": ("HuggingFaceTB/SmolVLM2-500M-Video-Instruct", "vlm", False),
    "internvl3-2b": ("OpenGVLab/InternVL3-2B", "vlm", True),
    "molmo2-4b": ("allenai/Molmo2-4B", "vlm", True),
    "minicpmv-4.5-int4": ("openbmb/MiniCPM-V-4_5-int4", "vlm", True),
    "phi3.5-vision": ("microsoft/Phi-3.5-vision-instruct", "vlm", True),
}


def _safe_model_path(value: str | None) -> str | None:
    if not value:
        return None
    candidate = Path(value).expanduser().resolve()
    if not candidate.is_dir() or (candidate != MODEL_ROOT and MODEL_ROOT not in candidate.parents):
        raise SystemExit(f"--model-path must point under {MODEL_ROOT}")
    return str(candidate)


class ExtendedRunner:
    def __init__(self, name: str, model_path: str | None, allow_remote_code: bool) -> None:
        checkpoint, kind, requires_remote = MODEL_SPECS[name]
        if requires_remote and not allow_remote_code and model_path is None:
            raise SystemExit(f"{name} requires --allow-remote-code or a local checkpoint")
        self.name = name
        self.kind = kind
        self.model_path = model_path
        self.checkpoint = model_path or checkpoint
        self.resolved_model_commit = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        if kind == "encoder":
            self.model = AutoModelForZeroShotImageClassification.from_pretrained(
                self.checkpoint, torch_dtype=dtype
            ).to(self.device)
            self.processor = AutoProcessor.from_pretrained(self.checkpoint)
        elif kind == "qwen":
            self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                self.checkpoint, torch_dtype=dtype, device_map="auto"
            )
            self.processor = AutoProcessor.from_pretrained(self.checkpoint)
        else:
            self.model = AutoModelForImageTextToText.from_pretrained(
                self.checkpoint,
                torch_dtype=dtype,
                device_map="auto",
                trust_remote_code=allow_remote_code,
            )
            self.processor = AutoProcessor.from_pretrained(
                self.checkpoint, trust_remote_code=allow_remote_code
            )
        model_config = getattr(self.model, "config", None)
        resolved_commit = getattr(model_config, "_commit_hash", None)
        self.resolved_model_commit = resolved_commit if isinstance(resolved_commit, str) else None
        self.model.eval()

    def predict(self, example: base.Example) -> tuple[dict[str, str], str, float, bool]:
        image = Image.open(example.image).convert("RGB")
        started = time.perf_counter()
        if self.kind == "encoder":
            predicted: dict[str, str] = {}
            raw_parts: list[str] = []
            for field, choices in base.CLIP_CHOICES.items():
                prompts = [
                    f"a CCTV photo of a person with {choice} {field.replace('_', ' ')}"
                    for choice in choices
                ]
                inputs = self.processor(
                    text=prompts, images=image, return_tensors="pt", padding=True
                )
                inputs = base._move_inputs(inputs, self.device)
                with torch.inference_mode():
                    logits = self.model(**inputs).logits_per_image[0]
                choice = choices[int(logits.argmax().item())]
                predicted[field] = base._canonical(field, choice)
                raw_parts.append(f"{field}={choice}")
            return predicted, "; ".join(raw_parts), time.perf_counter() - started, True

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": str(example.image)},
                    {"type": "text", "text": base.JSON_PROMPT},
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
        model_device = getattr(self.model, "device", self.device)
        inputs = base._move_inputs(inputs, model_device)
        input_length = inputs.input_ids.shape[1]
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=128, do_sample=False)
        raw = self.processor.batch_decode(output[:, input_length:], skip_special_tokens=True)[0]
        predicted = base._extract_json(raw)
        return predicted, raw, time.perf_counter() - started, bool(predicted)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=tuple(MODEL_SPECS), required=True)
    parser.add_argument("--model-path")
    parser.add_argument("--allow-remote-code", action="store_true")
    parser.add_argument(
        "--simuletic-root", type=Path, default=Path("experiments/data/cctv_proxy/simuletic")
    )
    parser.add_argument("--pa-root", type=Path, default=Path("experiments/data/cctv_proxy/pa100k"))
    parser.add_argument("--simuletic-groups", type=int, default=3)
    parser.add_argument("--pa-limit", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _args()
    args.model_path = _safe_model_path(args.model_path)
    examples = base._simuletic_examples(args.simuletic_root, args.simuletic_groups)
    examples += base._pa_examples(args.pa_root, args.pa_limit)
    base._validate_examples(examples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        runner = ExtendedRunner(args.model, args.model_path, args.allow_remote_code)
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
            "checkpoint": args.model_path or MODEL_SPECS[args.model][0],
            "error_type": type(error).__name__,
            "error": base._safe_error(error),
            "dataset_counts": dict(Counter(example.dataset for example in examples)),
            "summary": {
                "model": args.model,
                "status": "invalid_runtime",
                "examples": len(examples),
                "failed": len(examples),
            },
        }
        args.output.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(f"model initialization failed: {type(error).__name__}") from error

    predictions: list[dict[str, object]] = []
    for index, example in enumerate(examples, start=1):
        try:
            predicted, raw, latency, valid = runner.predict(example)
            error_text: str | None = None
        except (
            AttributeError,
            IndexError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            predicted, raw, latency, valid = {}, "", 0.0, False
            error_text = base._safe_error(error)
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
                "error": error_text,
            }
        )
        print(
            json.dumps(
                {
                    "index": index,
                    "model": args.model,
                    "error": error_text,
                    "latency_s": round(latency, 3),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    error_count = sum(1 for item in predictions if item["error"] is not None)
    provenance = base._provenance(examples, args, cast(base.Runner, runner))
    if error_count:
        summary: dict[str, object] = {
            "model": args.model,
            "status": "invalid_runtime",
            "examples": len(examples),
            "successful": len(predictions) - error_count,
            "failed": error_count,
        }
        status = "invalid_runtime"
    else:
        summary = base._summary(examples, predictions, args.model)
        if float(summary.get("structured_valid_rate", 0.0)) == 0.0:
            status = "invalid_output_contract"
        else:
            status = "valid"
        summary["status"] = status
    artifact = {
        "status": status,
        "hardware": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "torch": torch.__version__,
        "runtime": {"python": sys.version.split()[0]},
        "model": args.model,
        "checkpoint": runner.checkpoint,
        "provenance": provenance,
        "dataset_counts": dict(Counter(example.dataset for example in examples)),
        "summary": summary,
        "predictions": predictions,
    }
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if error_count:
        raise SystemExit(f"comparison invalid: {error_count} inference errors")


if __name__ == "__main__":
    main()

