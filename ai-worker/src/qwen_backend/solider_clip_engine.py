from __future__ import annotations

import importlib.util
import logging
import math
import shutil
import threading
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from qwen_backend.candidate_runtime import (
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    RuntimeBoundingBox,
    RuntimeCandidate,
)
from qwen_backend.video_tracks import TrackFrame, detect_person_tracks

logger = logging.getLogger(__name__)


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
    model_directory: Path = Field(default=Path("models"))
    model_manifest: Path = Field(default=Path("configs/realtime_model_manifest.json"))
    yolo_weights: str = Field(default="models/yolo11x.pt", min_length=1, max_length=500)
    tracker: str = Field(default="bytetrack.yaml", min_length=1, max_length=500)
    reid_checkpoint: Path | None = Path("models/solider_reid/swin_base_msmt17.pth")
    solider_root: Path | None = Field(
        default=Path("external/SOLIDER-REID-runtime-8c08e1c"),
        validation_alias=AliasChoices("SOLIDER_REID_ROOT", "QWEN_CANDIDATE_SOLIDER_ROOT"),
    )
    clip_checkpoint: str = Field(
        default="openai/clip-vit-large-patch14",
        min_length=1,
        max_length=500,
    )
    clip_revision: str = Field(
        default="32bd64288804d66eefd0ccbe215aa642df71cc41",
        min_length=1,
        max_length=100,
    )
    clip_cache_dir: Path | None = Field(
        default=Path("artifacts/ai-worker/model-cache/clip"),
        validation_alias=AliasChoices(
            "QWEN_CANDIDATE_CLIP_CACHE_DIR",
            "CLIP_CACHE_DIR",
        ),
    )
    clip_local_files_only: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "QWEN_CANDIDATE_CLIP_LOCAL_FILES_ONLY",
            "CLIP_LOCAL_FILES_ONLY",
        ),
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
    model_directory: str = "models"
    model_manifest: str = "configs/realtime_model_manifest.json"
    clip_revision: str = "32bd64288804d66eefd0ccbe215aa642df71cc41"
    clip_cache_dir: Path | None = Path("artifacts/ai-worker/model-cache/clip")
    clip_local_files_only: bool = True

    @property
    def solider_checkpoint(self) -> str:
        if self.reid_checkpoint is None:
            raise RuntimeError("SOLIDER checkpoint is not configured")
        return str(self.reid_checkpoint)

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
            model_directory=str(settings.model_directory),
            model_manifest=str(settings.model_manifest),
            clip_revision=settings.clip_revision,
            clip_cache_dir=settings.clip_cache_dir,
            clip_local_files_only=settings.clip_local_files_only,
        )


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def validate_realtime_dependencies(*, ffmpeg_path: str | None = None) -> None:
    """Fail fast when the worker was started without its realtime extra."""

    required_modules = ("cv2", "torch", "transformers", "ultralytics")
    missing = tuple(
        module for module in required_modules if importlib.util.find_spec(module) is None
    )
    if missing:
        raise RuntimeError(
            "realtime dependencies are missing; run `uv sync --extra realtime`: "
            + ", ".join(missing)
        )
    if ffmpeg_path is not None and shutil.which(ffmpeg_path) is None:
        raise RuntimeError(f"ffmpeg executable was not found: {ffmpeg_path}")


def _to_unit_interval(scores):
    import numpy as np

    return np.clip((scores + 1.0) / 2.0, 0.0, 1.0)


def _solider_scores(
    frames: Sequence[TrackFrame],
    reference_path: Path,
    config: EngineConfig,
    encoder: Any,
):
    if config.reid_checkpoint is None or config.solider_root is None:
        raise RuntimeError("SOLIDER checkpoint and repository must be configured")
    frame_features = _encode_solider_paths(
        tuple(frame.crop_path for frame in frames),
        encoder,
        batch_size=config.reid_batch_size,
    )
    reference_feature = _encode_solider_paths(
        (reference_path,),
        encoder,
        batch_size=1,
    )[0]
    return _to_unit_interval(frame_features @ reference_feature)


def _encode_solider_paths(
    paths: Sequence[Path],
    encoder: Any,
    *,
    batch_size: int,
):
    """Encode local crops through the same verified SOLIDER runtime as realtime inference."""

    import torch
    from PIL import Image

    features = []
    for start in range(0, len(paths), batch_size):
        tensors = []
        for path in paths[start : start + batch_size]:
            with Image.open(path) as image:
                rgb_image = image.convert("RGB")
                try:
                    tensors.append(encoder.processor(rgb_image))
                finally:
                    rgb_image.close()
        batch = torch.stack(tensors).to(encoder.device)
        with torch.inference_mode():
            feature = encoder.model(batch)[0]
            flipped_feature = encoder.model(torch.flip(batch, dims=(3,)))[0]
            combined = torch.nn.functional.normalize(feature, dim=-1) + (
                torch.nn.functional.normalize(flipped_feature, dim=-1)
            )
            features.append(torch.nn.functional.normalize(combined, dim=-1).cpu())
    return torch.cat(features, dim=0).numpy()


@dataclass(frozen=True, slots=True)
class _ClipBundle:
    processor: Any
    model: Any


def _clip_scores(
    frames: Sequence[TrackFrame],
    prompt: str,
    bundle: _ClipBundle,
    device: str,
):
    import torch
    from PIL import Image

    processor = bundle.processor
    model = bundle.model
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
        self._cache_lock = threading.RLock()
        self._detector: Any | None = None
        self._clip_bundle: _ClipBundle | None = None
        self._solider_encoder: Any | None = None
        self._cache_loads = {"yolo": 0, "clip": 0, "solider": 0}
        self._cache_hits = {"yolo": 0, "clip": 0, "solider": 0}

    @property
    def cache_status(self) -> dict[str, dict[str, int | bool]]:
        """Return non-sensitive model-cache state for status pages and logs."""

        with self._cache_lock:
            return {
                name: {
                    "loaded": value > 0,
                    "loads": value,
                    "hits": self._cache_hits[name],
                }
                for name, value in self._cache_loads.items()
            }

    def _load_detector(self) -> Any:
        from ultralytics import YOLO

        from qwen_backend.realtime_model_security import verified_yolo_weights

        return YOLO(verified_yolo_weights(self._config))

    def _get_detector(self) -> Any:
        with self._cache_lock:
            if self._detector is None:
                self._detector = self._load_detector()
                self._cache_loads["yolo"] += 1
                logger.info("candidate model cached component=YOLO")
            else:
                self._cache_hits["yolo"] += 1
            return self._detector

    def _load_clip_bundle(self) -> _ClipBundle:
        from transformers import CLIPModel, CLIPProcessor

        cache_dir = self._config.clip_cache_dir
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
        load_options = {
            "revision": self._config.clip_revision,
            "cache_dir": str(cache_dir) if cache_dir is not None else None,
            "local_files_only": self._config.clip_local_files_only,
            "use_fast": False,
        }
        processor = CLIPProcessor.from_pretrained(
            self._config.clip_checkpoint,
            **load_options,
        )
        model = CLIPModel.from_pretrained(
            self._config.clip_checkpoint,
            revision=self._config.clip_revision,
            cache_dir=str(cache_dir) if cache_dir is not None else None,
            local_files_only=self._config.clip_local_files_only,
        )
        return _ClipBundle(processor=processor, model=model.to(self._config.device).eval())

    def _get_clip_bundle(self) -> _ClipBundle:
        with self._cache_lock:
            if self._clip_bundle is None:
                self._clip_bundle = self._load_clip_bundle()
                self._cache_loads["clip"] += 1
                logger.info("candidate model cached component=CLIP")
            else:
                self._cache_hits["clip"] += 1
            return self._clip_bundle

    def _load_solider_encoder(self) -> Any:
        import sys

        import torch

        from qwen_backend.realtime_identity import verified_solider_root
        from qwen_backend.realtime_model_security import verified_solider_checkpoint
        from qwen_backend.solider_runtime import SoliderImageEncoder

        if self._config.solider_root is None or self._config.reid_checkpoint is None:
            raise RuntimeError("SOLIDER checkpoint and repository must be configured")
        # The verified checkout is an immutable runtime dependency.  Prevent the
        # legacy package imports from leaving untracked __pycache__ files in it,
        # which would make the integrity check fail on the next job.
        sys.dont_write_bytecode = True
        root = verified_solider_root(str(self._config.solider_root))
        checkpoint = verified_solider_checkpoint(self._config)
        return SoliderImageEncoder(
            device=torch.device(self._config.device),
            checkpoint=checkpoint,
            root=root,
        )

    def _get_solider_encoder(self) -> Any:
        with self._cache_lock:
            if self._solider_encoder is None:
                self._solider_encoder = self._load_solider_encoder()
                self._cache_loads["solider"] += 1
                logger.info("candidate model cached component=SOLIDER")
            else:
                self._cache_hits["solider"] += 1
            return self._solider_encoder

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
            detector=self._get_detector(),
        )
        if not frames:
            return CandidateRuntimeResponse(modelKey=self.model_key, candidates=())
        if request.reference_path is None and not request.prompt.strip():
            raise ValueError("reference image or appearance prompt is required")

        reid_scores = (
            _solider_scores(
                frames,
                request.reference_path,
                self._config,
                self._get_solider_encoder(),
            )
            if request.reference_path is not None
            else None
        )
        clip_scores = (
            _clip_scores(
                frames,
                request.prompt,
                self._get_clip_bundle(),
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
