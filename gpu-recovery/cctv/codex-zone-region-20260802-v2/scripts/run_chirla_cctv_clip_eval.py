from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from qwen_backend.cctv_identity_evaluation import (
    TrackReference,
    TrackRetrievalPrediction,
    evaluate_identity_predictions,
)


class ManifestRow(TypedDict):
    trackId: str
    split: str
    targetRole: str
    identityGroupId: str
    framePath: str


ATTRIBUTE_LABELS = {
    "upper_color": (
        "black",
        "navy",
        "blue",
        "white",
        "gray",
        "beige",
        "brown",
        "red",
        "green",
        "pink",
        "multicolor",
        "unknown",
    ),
    "lower_color": (
        "black",
        "navy",
        "blue",
        "white",
        "gray",
        "beige",
        "brown",
        "red",
        "green",
        "pink",
        "multicolor",
        "unknown",
    ),
    "pattern": ("solid", "patterned", "unknown"),
    "carrying": ("none", "handbag", "backpack", "other bag", "unknown"),
    "headwear": ("none", "hat", "unknown"),
    "visibility": ("full body visible", "partial body crop", "not sufficiently visible"),
}


def _read_manifest(path: Path) -> tuple[ManifestRow, ...]:
    rows: list[ManifestRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("manifest row must be an object")
            rows.append(payload)
    return tuple(rows)


def _features(
    model: CLIPModel,
    processor: CLIPProcessor,
    paths: list[Path],
    device: torch.device,
    batch_size: int,
) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    with torch.inference_mode():
        for start in range(0, len(paths), batch_size):
            images: list[Image.Image] = []
            for path in paths[start : start + batch_size]:
                with Image.open(path) as source:
                    images.append(source.convert("RGB"))
            inputs = processor(images=images, return_tensors="pt")
            pixels = inputs["pixel_values"].to(device)
            output = model.get_image_features(pixel_values=pixels)
            if not isinstance(output, torch.Tensor):
                raise TypeError("CLIP image encoder did not return a tensor")
            chunks.append(torch.nn.functional.normalize(output, dim=-1).cpu())
            for image in images:
                image.close()
    return torch.cat(chunks, dim=0)


def _text_features(
    model: CLIPModel, processor: CLIPProcessor, prompts: list[str], device: torch.device
) -> torch.Tensor:
    inputs = processor(text=prompts, return_tensors="pt", padding=True).to(device)
    with torch.inference_mode():
        output = model.get_text_features(**inputs)
    if not isinstance(output, torch.Tensor):
        raise TypeError("CLIP text encoder did not return a tensor")
    return torch.nn.functional.normalize(output, dim=-1).cpu()


def _attribute_prompts(field: str, labels: tuple[str, ...]) -> list[str]:
    templates = {
        "upper_color": "a CCTV person wearing a {label} upper garment",
        "lower_color": "a CCTV person wearing {label} lower clothing",
        "pattern": "a CCTV person wearing {label} clothing",
        "carrying": "a CCTV person carrying {label}",
        "headwear": "a CCTV person with {label}",
        "visibility": "a CCTV image where the person is {label}",
    }
    return [templates[field].format(label=label) for label in labels]


def _track_vectors(
    rows: tuple[ManifestRow, ...], frame_features: torch.Tensor
) -> tuple[dict[str, torch.Tensor], dict[str, ManifestRow]]:
    indices: dict[str, list[int]] = defaultdict(list)
    first: dict[str, ManifestRow] = {}
    for index, row in enumerate(rows):
        indices[row["trackId"]].append(index)
        first.setdefault(row["trackId"], row)
    vectors = {
        track_id: torch.nn.functional.normalize(frame_features[indexes].mean(dim=0), dim=0)
        for track_id, indexes in indices.items()
    }
    return vectors, first


def _identity_predictions(
    rows: tuple[ManifestRow, ...],
    vectors: dict[str, torch.Tensor],
    first: dict[str, ManifestRow],
    threshold: float,
) -> tuple[tuple[TrackReference, ...], tuple[TrackRetrievalPrediction, ...], dict[str, float]]:
    gallery = {
        track_id: vector
        for track_id, vector in vectors.items()
        if first[track_id]["split"] == "gallery"
    }
    gallery_ids = sorted({first[track_id]["identityGroupId"] for track_id in gallery})
    prototypes = {
        identity: torch.nn.functional.normalize(
            torch.stack(
                [
                    gallery[track_id]
                    for track_id in gallery
                    if first[track_id]["identityGroupId"] == identity
                ]
            ).mean(dim=0),
            dim=0,
        )
        for identity in gallery_ids
    }
    references: list[TrackReference] = []
    predictions: list[TrackRetrievalPrediction] = []
    score_by_track: dict[str, float] = {}
    for track_id, row in first.items():
        references.append(
            TrackReference.model_validate(
                {
                    "caseId": "cctv-external-chirla-20260727",
                    "videoId": row["trackId"],
                    "cameraId": "chirla",
                    "conditionGroupId": "chirla-multi-camera-long-term",
                    "trackId": track_id,
                    "split": row["split"],
                    "targetRole": row["targetRole"],
                    "identityGroupId": row["identityGroupId"],
                    "frameCount": sum(item["trackId"] == track_id for item in rows),
                }
            )
        )
        if row["split"] == "gallery":
            continue
        scored = sorted(
            (
                (identity, float(torch.dot(vectors[track_id], prototype)))
                for identity, prototype in prototypes.items()
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        score_by_track[track_id] = scored[0][1]
        candidates = tuple(
            {"identityGroupId": identity, "score": score} for identity, score in scored
        )
        decision = "match" if scored[0][1] >= threshold else "reject"
        predictions.append(
            TrackRetrievalPrediction.model_validate(
                {"queryTrackId": track_id, "candidates": candidates, "decision": decision}
            )
        )
    return tuple(references), tuple(predictions), score_by_track


def _attribute_predictions(
    rows: tuple[ManifestRow, ...],
    vectors: dict[str, torch.Tensor],
    model: CLIPModel,
    processor: CLIPProcessor,
    device: torch.device,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for track_id, vector in vectors.items():
        attributes: dict[str, dict[str, str | float]] = {}
        for field, labels in ATTRIBUTE_LABELS.items():
            text = _text_features(model, processor, _attribute_prompts(field, labels), device)
            logits = vector @ text.T
            probabilities = torch.softmax(logits * 100, dim=0)
            best = int(probabilities.argmax())
            attributes[field] = {"label": labels[best], "confidence": float(probabilities[best])}
        row = next(item for item in rows if item["trackId"] == track_id)
        output.append(
            {
                "trackId": track_id,
                "identityGroupId": row["identityGroupId"],
                "targetRole": row["targetRole"],
                "frameCount": sum(item["trackId"] == track_id for item in rows),
                "model": "CLIP ViT-L/14 zero-shot",
                "attributes": attributes,
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("experiments/data/chirla"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", default="openai/clip-vit-large-patch14")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--threshold", type=float, default=0.7)
    args = parser.parse_args()
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    rows = _read_manifest(args.manifest)
    paths = [(args.root / row["framePath"]).resolve() for row in rows]
    if any(args.root.resolve() not in path.parents or not path.is_file() for path in paths):
        raise ValueError("manifest contains missing or out-of-root frame")
    processor = CLIPProcessor.from_pretrained(args.checkpoint, local_files_only=True)
    model = CLIPModel.from_pretrained(args.checkpoint, local_files_only=True).to(device).eval()
    frame_features = _features(model, processor, paths, device, args.batch_size)
    vectors, first = _track_vectors(rows, frame_features)
    references, predictions, score_by_track = _identity_predictions(
        rows, vectors, first, args.threshold
    )
    report = evaluate_identity_predictions(
        references, predictions, model_name="clip-vit-l14-zero-shot"
    )
    threshold_sweep = []
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9):
        sweep_references, sweep_predictions, _ = _identity_predictions(
            rows, vectors, first, threshold
        )
        sweep_report = evaluate_identity_predictions(
            sweep_references, sweep_predictions, model_name="clip-vit-l14-zero-shot"
        )
        threshold_sweep.append({"threshold": threshold, **sweep_report.model_dump(by_alias=True)})
    attribute_predictions = _attribute_predictions(rows, vectors, model, processor, device)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "identity_predictions.jsonl").write_text(
        "".join(prediction.model_dump_json(by_alias=True) + "\n" for prediction in predictions),
        encoding="utf-8",
    )
    (args.output_dir / "attribute_predictions.jsonl").write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in attribute_predictions
        ),
        encoding="utf-8",
    )
    result = {
        "schemaVersion": "cctv-chirla-clip-evaluation-v1",
        "model": "CLIP ViT-L/14 zero-shot",
        "checkpoint": args.checkpoint,
        "device": str(device),
        "threshold": args.threshold,
        "galleryIdentityCount": len(
            {row["identityGroupId"] for row in rows if row["split"] == "gallery"}
        ),
        "targetQueryCount": sum(
            row["targetRole"] == "target" and row["split"] != "gallery" for row in first.values()
        ),
        "distractorQueryCount": sum(row["targetRole"] == "distractor" for row in first.values()),
        "identityReport": report.model_dump(by_alias=True),
        "thresholdSweep": threshold_sweep,
        "topScoreByQuery": score_by_track,
    }
    (args.output_dir / "identity_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report.status,
                "rank1": report.rank1,
                "recallAt5": report.recall_at_5,
                "falseMatchRate": report.false_match_rate,
                "falseRejectRate": report.false_reject_rate,
                "output": str(args.output_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
