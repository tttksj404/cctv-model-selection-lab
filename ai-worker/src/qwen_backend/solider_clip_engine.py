from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from qwen_backend.candidate_runtime import (
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    RuntimeBoundingBox,
    RuntimeCandidate,
)
from qwen_backend.video_tracks import TrackFrame, detect_person_tracks


class CandidateEngineSettings(BaseSettings):
    """Environment-owned knobs for the archived candidate runtime.

    These values used to be read one-by-one with ``int(os.environ.get(...))``
    and several inference thresholds were embedded in ``analyze``.  Keeping
    them in one validated settings object makes a bad notebook ``.env`` fail
    before a job is claimed rather than halfway through inference.
    """

    model_config = SettingsConfigDict(
        env_prefix="QWEN_CANDIDATE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_key: str = Field(default="hybrid-solider-clip-v1", min_length=1, max_length=100)
    device: str = Field(default="cuda", min_length=1, max_length=50)
    yolo_weights: str = Field(default="yolo11s.pt", min_length=1, max_length=500)
    tracker: str = Field(default="bytetrack.yaml", min_length=1, max_length=500)
    reid_checkpoint: Path | None = None
    solider_root: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("SOLIDER_REID_ROOT", "QWEN_CANDIDATE_SOLIDER_ROOT"),
    )
    clip_checkpoint: str = Field(
        default="openai/clip-vit-large-patch14",
        min_length=1,
        max_length=500,
    )
    top_k: int = Field(default=20, ge=1, le=100)
    max_crops_per_track: int = Field(default=12, ge=1, le=100)
    detector_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    frame_stride: int = Field(default=3, ge=1, le=100)
    sample_every_seconds: float = Field(default=0.75, gt=0.0, le=60.0)
    crop_margin: float = Field(default=0.05, ge=0.0, le=0.5)
    reid_weight: float = Field(default=0.75, ge=0.0, le=1.0)
    clip_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    aggregate_top_frames: int = Field(default=3, ge=1, le=100)
    reid_batch_size: int = Field(default=32, ge=1, le=256)

    @model_validator(mode="after")
    def validate_scoring_weights(self) -> CandidateEngineSettings:
        if math.isclose(self.reid_weight + self.clip_weight, 0.0):
            raise ValueError("scoring weights must contain at least one positive value")
        return self


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
    detector_confidence: float
    frame_stride: int
    sample_every_seconds: float
    crop_margin: float
    reid_weight: float
    clip_weight: float
    aggregate_top_frames: int
    reid_batch_size: int

    @classmethod
    def from_environment(cls) -> EngineConfig:
        settings = CandidateEngineSettings()
        return cls(
            model_key=settings.model_key,
            device=settings.device,
            yolo_weights=settings.yolo_weights,
            tracker=settings.tracker,
            reid_checkpoint=settings.reid_checkpoint,
            solider_root=settings.solider_root,
            clip_checkpoint=settings.clip_checkpoint,
            top_k=settings.top_k,
            max_crops_per_track=settings.max_crops_per_track,
            detector_confidence=settings.detector_confidence,
            frame_stride=settings.frame_stride,
            sample_every_seconds=settings.sample_every_seconds,
            crop_margin=settings.crop_margin,
            reid_weight=settings.reid_weight,
            clip_weight=settings.clip_weight,
            aggregate_top_frames=settings.aggregate_top_frames,
            reid_batch_size=settings.reid_batch_size,
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
    frame_features = encoder.encode(records, batch_size=config.reid_batch_size)
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
            confidence=self._config.detector_confidence,
            stride=self._config.frame_stride,
            sample_every_seconds=self._config.sample_every_seconds,
            max_crops_per_track=self._config.max_crops_per_track,
            margin=self._config.crop_margin,
            search_from_ms=request.search_from_ms,
            search_to_ms=request.search_to_ms,
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
        weight_total = self._config.reid_weight + self._config.clip_weight
        combined = (
            (
                self._config.reid_weight * reid_scores
                + self._config.clip_weight * clip_scores
            )
            / weight_total
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
            candidates=self._aggregate_tracks(
                frames,
                combined,
                scoring_mode,
                similarity_threshold=request.similarity_threshold,
            ),
        )

    def _aggregate_tracks(
        self,
        frames: Sequence[TrackFrame],
        scores,
        scoring_mode: str,
        *,
        similarity_threshold: float | None,
    ) -> tuple[RuntimeCandidate, ...]:
        grouped: dict[int, list[tuple[TrackFrame, float]]] = defaultdict(list)
        for frame, score in zip(frames, scores, strict=True):
            grouped[frame.track_id].append((frame, float(score)))
        candidates: list[RuntimeCandidate] = []
        for track_id, rows in grouped.items():
            ranked = sorted(rows, key=lambda row: row[1], reverse=True)
            representative, _ = ranked[0]
            aggregate_count = min(self._config.aggregate_top_frames, len(ranked))
            track_score = sum(score for _, score in ranked[:aggregate_count]) / aggregate_count
            if similarity_threshold is not None and track_score < similarity_threshold:
                continue
            candidates.append(
                RuntimeCandidate(
                    candidateKey=f"track-{track_id}",
                    frameOffsetMs=representative.frame_offset_ms,
                    similarity=round(track_score, 6),
                    framePath=representative.frame_path,
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
