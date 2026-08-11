from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from qwen_backend.candidate_runtime import (
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    RuntimeBoundingBox,
    RuntimeCandidate,
)
from qwen_backend.video_tracks import TrackFrame, detect_person_tracks


@dataclass(frozen=True, slots=True)
class EngineConfig:
    model_key: str
    device: str
    yolo_weights: str
    tracker: str
    reid_checkpoint: Path | None
    solider_root: Path | None
    clip_checkpoint: str
    top_k: int
    max_crops_per_track: int

    @classmethod
    def from_environment(cls) -> EngineConfig:
        checkpoint_value = os.environ.get("QWEN_CANDIDATE_REID_CHECKPOINT")
        root_value = os.environ.get("SOLIDER_REID_ROOT")
        return cls(
            model_key=os.environ.get(
                "QWEN_CANDIDATE_MODEL_KEY",
                "hybrid-solider-clip-v1",
            ),
            device=os.environ.get("QWEN_CANDIDATE_DEVICE", "cuda"),
            yolo_weights=os.environ.get("QWEN_CANDIDATE_YOLO_WEIGHTS", "yolo11s.pt"),
            tracker=os.environ.get("QWEN_CANDIDATE_TRACKER", "bytetrack.yaml"),
            reid_checkpoint=Path(checkpoint_value) if checkpoint_value else None,
            solider_root=Path(root_value) if root_value else None,
            clip_checkpoint=os.environ.get(
                "QWEN_CANDIDATE_CLIP_CHECKPOINT",
                "openai/clip-vit-large-patch14",
            ),
            top_k=int(os.environ.get("QWEN_CANDIDATE_TOP_K", "20")),
            max_crops_per_track=int(
                os.environ.get("QWEN_CANDIDATE_MAX_CROPS_PER_TRACK", "12")
            ),
        )


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_unit_interval(scores):
    import numpy as np

    return np.clip((scores + 1.0) / 2.0, 0.0, 1.0)


def _solider_scores(
    frames: Sequence[TrackFrame],
    reference_path: Path,
    config: EngineConfig,
):
    import torch

    from scripts.benchmark_chirla_reid import ImageEncoder, Record

    if config.reid_checkpoint is None or config.solider_root is None:
        raise RuntimeError("SOLIDER checkpoint and repository must be configured")
    encoder = ImageEncoder(
        "solider-reid-swin-base-msmt17",
        torch.device(config.device),
        checkpoint_override=str(config.reid_checkpoint),
        solider_root=config.solider_root,
        tta="hflip",
    )
    records = [
        Record(
            path=frame.crop_path,
            identity=str(frame.track_id),
            role="query",
            camera="runtime",
            sequence="runtime",
            sha256=_sha256(frame.crop_path),
        )
        for frame in frames
    ]
    reference = Record(
        path=reference_path,
        identity="reference",
        role="gallery",
        camera="reference",
        sequence="reference",
        sha256=_sha256(reference_path),
    )
    frame_features = encoder.encode(records, batch_size=32)
    reference_feature = encoder.encode([reference], batch_size=1)[0]
    return _to_unit_interval(frame_features @ reference_feature)


def _clip_scores(frames: Sequence[TrackFrame], prompt: str, checkpoint: str, device: str):
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor

    processor = CLIPProcessor.from_pretrained(checkpoint)
    model = CLIPModel.from_pretrained(checkpoint).to(device).eval()
    images = []
    try:
        for frame in frames:
            with Image.open(frame.crop_path) as image:
                images.append(image.convert("RGB"))
        inputs = processor(text=[prompt], images=images, return_tensors="pt", padding=True)
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.inference_mode():
            image_features = model.get_image_features(pixel_values=inputs["pixel_values"])
            text_features = model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
            )
            image_features = torch.nn.functional.normalize(image_features, dim=-1)
            text_features = torch.nn.functional.normalize(text_features, dim=-1)
            scores = image_features @ text_features.T
        return _to_unit_interval(scores[:, 0].float().cpu().numpy())
    finally:
        for image in images:
            image.close()


class SoliderClipCandidateEngine:
    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self.model_key = config.model_key

    def analyze(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        frames = detect_person_tracks(
            request.video_path,
            request.output_dir,
            weights=self._config.yolo_weights,
            tracker=self._config.tracker,
            device=self._config.device,
            confidence=0.25,
            stride=3,
            sample_every_seconds=0.75,
            max_crops_per_track=self._config.max_crops_per_track,
            margin=0.05,
        )
        if not frames:
            return CandidateRuntimeResponse(modelKey=self.model_key, candidates=())
        if request.reference_path is None and not request.prompt.strip():
            raise ValueError("reference image or appearance prompt is required")

        reid_scores = (
            _solider_scores(frames, request.reference_path, self._config)
            if request.reference_path is not None
            else None
        )
        clip_scores = (
            _clip_scores(
                frames,
                request.prompt,
                self._config.clip_checkpoint,
                self._config.device,
            )
            if request.prompt.strip()
            else None
        )
        combined = (
            0.75 * reid_scores + 0.25 * clip_scores
            if reid_scores is not None and clip_scores is not None
            else reid_scores
            if reid_scores is not None
            else clip_scores
        )
        if combined is None:
            raise RuntimeError("candidate scoring did not produce scores")
        scoring_mode = (
            "SOLIDER+CLIP"
            if reid_scores is not None and clip_scores is not None
            else "SOLIDER"
            if reid_scores is not None
            else "CLIP"
        )
        return CandidateRuntimeResponse(
            modelKey=self.model_key,
            candidates=self._aggregate_tracks(frames, combined, scoring_mode),
        )

    def _aggregate_tracks(
        self,
        frames: Sequence[TrackFrame],
        scores,
        scoring_mode: str,
    ) -> tuple[RuntimeCandidate, ...]:
        grouped: dict[int, list[tuple[TrackFrame, float]]] = defaultdict(list)
        for frame, score in zip(frames, scores, strict=True):
            grouped[frame.track_id].append((frame, float(score)))
        candidates: list[RuntimeCandidate] = []
        for track_id, rows in grouped.items():
            ranked = sorted(rows, key=lambda row: row[1], reverse=True)
            representative, _ = ranked[0]
            aggregate_count = min(3, len(ranked))
            track_score = sum(score for _, score in ranked[:aggregate_count]) / aggregate_count
            candidates.append(
                RuntimeCandidate(
                    candidateKey=f"track-{track_id}",
                    frameOffsetMs=representative.frame_offset_ms,
                    similarity=round(track_score, 6),
                    cropPath=representative.crop_path,
                    boundingBox=RuntimeBoundingBox(
                        x=representative.left,
                        y=representative.top,
                        width=representative.right - representative.left,
                        height=representative.bottom - representative.top,
                    ),
                    attributeSummary=(
                        f"trackFrames={len(rows)}; "
                        f"detectorConfidence={representative.detector_confidence:.3f}; "
                        f"scoring={scoring_mode}"
                    ),
                )
            )
        candidates.sort(key=lambda candidate: candidate.similarity, reverse=True)
        return tuple(candidates[: self._config.top_k])


def create_engine() -> SoliderClipCandidateEngine:
    return SoliderClipCandidateEngine(EngineConfig.from_environment())
