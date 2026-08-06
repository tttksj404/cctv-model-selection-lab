from __future__ import annotations

import logging
import threading
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image

from qwen_backend.attribute_ensemble import (
    FrameAttributeScores,
    SearchAttributes,
    add_track_consistency,
    aggregate_track_scores,
    color_scores,
    crop_quality,
    decide_track,
    fuse_track_scores,
    model_trace,
    parse_search_attributes,
)
from qwen_backend.candidate_runtime import (
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    RuntimeBoundingBox,
    RuntimeCandidate,
)
from qwen_backend.fine_attribute_runtime import (
    FineAttributeRuntime,
    SoliderParRuntime,
    discover_fine_head_paths,
    discover_solider_par_head_path,
)
from qwen_backend.historical_retrieval import HistoricalRetrievalRuntime
from qwen_backend.qwen_review_runtime import QwenReviewRuntime
from qwen_backend.solider_clip_engine import (
    EngineConfig,
    SoliderClipCandidateEngine,
    score_solider,
)
from qwen_backend.video_tracks import TrackFrame, detect_person_tracks

logger = logging.getLogger(__name__)


def _clip_text_features(bundle: Any, prompts: tuple[str, str], device: str) -> torch.Tensor:
    inputs = bundle.processor(text=list(prompts), return_tensors="pt", padding=True)
    inputs = {key: value.to(device) for key, value in inputs.items()}
    with torch.inference_mode():
        features = bundle.model.get_text_features(**inputs)
    return torch.nn.functional.normalize(features, dim=-1)


def _clip_image_features(
    bundle: Any,
    paths: Sequence[Path],
    device: str,
    *,
    batch_size: int = 32,
) -> torch.Tensor:
    outputs: list[torch.Tensor] = []
    for start in range(0, len(paths), batch_size):
        images: list[Image.Image] = []
        for path in paths[start : start + batch_size]:
            with Image.open(path) as source:
                images.append(source.convert("RGB"))
        try:
            inputs = bundle.processor(images=images, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(device, dtype=bundle.model.dtype)
            with torch.inference_mode():
                features = bundle.model.get_image_features(pixel_values=pixel_values)
            outputs.append(torch.nn.functional.normalize(features, dim=-1).float().cpu())
        finally:
            for image in images:
                image.close()
    if not outputs:
        return torch.empty((0, 1), dtype=torch.float32)
    return torch.cat(outputs, dim=0)


def _contrastive_clip_scores(
    frames: Sequence[TrackFrame],
    prompt: str,
    exclusion_prompt: str | None,
    bundle: Any,
    device: str,
) -> np.ndarray:
    positive = prompt.strip()
    if not positive:
        raise ValueError("appearance prompt is required")
    negative = (exclusion_prompt or "").strip() or (
        "a person whose visible appearance does not match the requested clothing "
        "and physical attributes"
    )
    text_features = _clip_text_features(bundle, (positive, negative), device).cpu()
    image_features = _clip_image_features(
        bundle,
        tuple(frame.crop_path for frame in frames),
        device,
    )
    cosine = image_features @ text_features.T
    logit_scale = bundle.model.logit_scale.exp().clamp(max=100.0).detach().cpu()
    logits = logit_scale * cosine
    contrastive = torch.softmax(logits.float(), dim=1)[:, 0]
    # A free-form exclusion prompt is useful as a disagreement signal, but it
    # must not erase the calibrated positive CLIP score.  The positive-only
    # score remains the primary term so a verbose or poorly phrased exclusion
    # prompt cannot turn every valid track into zero evidence.
    positive = ((cosine[:, 0].float() + 1.0) / 2.0).clamp(0.0, 1.0)
    return (0.75 * positive + 0.25 * contrastive).numpy()


def _fine_score(
    values: dict[str, float] | None,
    *,
    glasses: bool,
    hair: bool,
    upper_style: bool,
) -> float | None:
    if values is None:
        return None
    required: list[float] = []
    for key, enabled in (
        ("glasses", glasses),
        ("hair", hair),
        ("upper_style", upper_style),
    ):
        if enabled and key in values:
            required.append(values[key])
    if not required:
        return None
    return sum(required) / len(required)


def select_evidence_frame(
    frames: Sequence[TrackFrame],
    rows: Sequence[FrameAttributeScores],
    *,
    minimum_quality: float,
) -> TrackFrame | None:
    """Select a readable person crop for review and candidate evidence.

    ``detect_person_tracks`` already limits YOLO to class ``0`` (person), but
    a track can still contain tiny/partial crops.  Attribute scores must not
    be allowed to select one of those crops merely because a shirt-colour
    patch scored highly.  The evidence gate is therefore applied before the
    Qwen review and before a candidate is emitted.
    """

    if len(frames) != len(rows):
        return None

    candidates: list[tuple[TrackFrame, float, FrameAttributeScores]] = []
    for frame, row in zip(frames, rows, strict=True):
        quality = crop_quality(frame.crop_path)
        if quality < minimum_quality:
            continue
        if frame.right <= frame.left or frame.bottom <= frame.top:
            continue
        candidates.append((frame, quality, row))
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            item[1],
            item[0].detector_confidence,
            item[2].semantic
            + (item[2].upper_color or 0.0)
            + (item[2].lower_color or 0.0),
        ),
    )[0]


class MultiModelCandidateEngine:
    """Recording-path ensemble without changing the central worker contract.

    The engine intentionally keeps YOLO, CLIP and SOLIDER in one lifecycle.
    PETA/PA100k heads reuse the cached CLIP ViT-L/14 backbone when local
    checkpoints exist.  A missing optional model is recorded as unavailable;
    it is never represented as a successful score.
    """

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        self.model_key = config.model_key
        self._base = SoliderClipCandidateEngine(config)
        self._fine: FineAttributeRuntime | None = None
        self._fine_checked = False
        self._fine_status = "not_checked"
        self._solider_par: SoliderParRuntime | None = None
        self._solider_par_checked = False
        self._solider_par_status = "not_checked"
        self._historical = HistoricalRetrievalRuntime(
            config.historical_gallery_directory,
            config.device,
        )
        self._qwen_review = QwenReviewRuntime(
            enabled=config.qwen_review_enabled,
            top_k=config.qwen_review_top_k,
            provider_mode=config.qwen_review_provider,
            remote_base_url=config.qwen_remote_base_url,
            remote_model=config.qwen_remote_model,
            remote_api_key=config.qwen_remote_api_key,
            remote_timeout_seconds=config.qwen_remote_timeout_seconds,
        )
        self._lock = threading.RLock()
        self._last_model_trace: tuple[tuple[str, str], ...] = ()
        self._minimum_output_score = _env_float(
            "QWEN_CANDIDATE_MIN_OUTPUT_SCORE", 0.30, minimum=0.0, maximum=1.0
        )
        self._color_reject_threshold = _env_float(
            "QWEN_CANDIDATE_COLOR_REJECT_THRESHOLD", 0.35, minimum=0.0, maximum=1.0
        )
        self._minimum_person_crop_quality = config.minimum_person_crop_quality

    @property
    def cache_status(self) -> dict[str, dict[str, int | bool | str]]:
        status: dict[str, dict[str, int | bool | str]] = {
            name: dict(values) for name, values in self._base.cache_status.items()
        }
        with self._lock:
            status["fine_attribute"] = {
                "loaded": self._fine is not None,
                "loads": int(self._fine is not None),
                "hits": 0,
                "status": self._fine_status,
            }
            status["solider_par"] = {
                "loaded": self._solider_par is not None,
                "loads": int(self._solider_par is not None),
                "hits": 0,
                "status": self._solider_par_status,
            }
        return status

    @property
    def last_model_trace(self) -> tuple[tuple[str, str], ...]:
        return self._last_model_trace

    def _get_fine(self, bundle: Any) -> FineAttributeRuntime | None:
        with self._lock:
            if self._fine_checked:
                return self._fine
            self._fine_checked = True
            peta, pa100k = discover_fine_head_paths(self._config.model_directory)
            if peta is None or pa100k is None:
                self._fine_status = "unavailable: PETA/PA100k head checkpoint missing"
                return None
            try:
                self._fine = FineAttributeRuntime(
                    peta,
                    pa100k,
                    bundle,
                    self._config.device,
                )
            except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
                self._fine_status = f"unavailable: {type(error).__name__}"
                logger.warning("fine attribute heads were not loaded: %s", error)
                self._fine = None
            else:
                self._fine_status = "used"
                logger.info("candidate model cached component=CLIP-PETA-PA100k")
            return self._fine

    def _get_solider_par(self) -> SoliderParRuntime | None:
        with self._lock:
            if self._solider_par_checked:
                return self._solider_par
            self._solider_par_checked = True
            checkpoint = discover_solider_par_head_path(
                self._config.model_directory,
                self._config.solider_par_head,
            )
            if checkpoint is None:
                self._solider_par_status = "unavailable:checkpoint_missing"
                return None
            try:
                self._solider_par = SoliderParRuntime(checkpoint, self._config.device)
            except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
                self._solider_par_status = f"unavailable:{type(error).__name__}"
                logger.warning("SOLIDER PAR head was not loaded: %s", error)
                self._solider_par = None
            else:
                self._solider_par_status = "ready"
            return self._solider_par

    def _resolve_identity_anchor(
        self,
        request: CandidateRuntimeRequest,
    ) -> tuple[Path | None, str]:
        if request.reference_path is not None:
            return request.reference_path, "reference"
        root = self._config.anchor_directory
        if root is None:
            return None, "not_configured"
        root = root.expanduser().resolve()
        candidates = (root / f"case-{request.case_id}", root / str(request.case_id))
        selected = next((path for path in candidates if path.is_dir()), None)
        if selected is None:
            return None, "not_found"
        images = tuple(
            path
            for path in sorted(selected.iterdir())
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        if not images:
            return None, "not_found"
        return images[0], "case_anchor"

    def _track_color_values(
        self,
        frames: Sequence[TrackFrame],
        attributes: SearchAttributes,
    ) -> dict[int, tuple[float | None, float | None]]:
        values: dict[int, tuple[float | None, float | None]] = {}
        for frame in frames:
            image = cv2.imread(str(frame.crop_path), cv2.IMREAD_COLOR)
            if image is None or image.size == 0:
                values[id(frame)] = (None, None)
                continue
            values[id(frame)] = color_scores(np.asarray(image, dtype=np.uint8), attributes)
        return values

    def analyze(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        detected_frames = detect_person_tracks(
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
            detector=self._base.get_detector(),
        )
        if not detected_frames:
            self._last_model_trace = (("YOLO", "used:no_person_track"),)
            return CandidateRuntimeResponse(model_key=self.model_key, candidates=())

        # Keep low-resolution/partial detections out of every downstream
        # attribute score, not only out of the final representative image.
        # This makes the order explicit: YOLO person detection -> readable
        # person evidence -> attribute/identity decision.
        frames = tuple(
            frame
            for frame in detected_frames
            if frame.right > frame.left
            and frame.bottom > frame.top
            and crop_quality(frame.crop_path) >= self._minimum_person_crop_quality
        )
        if not frames:
            self._last_model_trace = (
                ("YOLO", "used:no_readable_person_evidence"),
                (
                    "Person-evidence",
                    f"rejected:quality<{self._minimum_person_crop_quality:.3f}",
                ),
            )
            logger.info(
                "recording produced no readable person evidence frames "
                "minimum_quality=%.3f",
                self._minimum_person_crop_quality,
            )
            return CandidateRuntimeResponse(model_key=self.model_key, candidates=())

        attributes = parse_search_attributes(request.prompt)
        bundle = self._base.get_clip_bundle()
        semantic_scores = _contrastive_clip_scores(
            frames,
            request.prompt,
            request.exclusion_prompt,
            bundle,
            self._config.device,
        )
        color_values = self._track_color_values(frames, attributes)

        fine_runtime = self._get_fine(bundle)
        fine_by_track: dict[int, dict[str, float]] = {}
        if fine_runtime is not None:
            try:
                fine_by_track = fine_runtime.score(frames)
            except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
                self._fine_status = f"failed: {type(error).__name__}"
                logger.warning("fine attribute inference failed: %s", error)
                fine_by_track = {}

        identity_anchor, anchor_status = self._resolve_identity_anchor(request)
        reid_scores: np.ndarray | None = None
        reid_status = f"not_configured:{anchor_status}"
        if identity_anchor is not None:
            try:
                reid_scores = np.asarray(
                    score_solider(
                        frames,
                        identity_anchor,
                        self._config,
                        self._base.get_solider_encoder(),
                    ),
                    dtype=np.float32,
                )
                reid_status = "used"
            except (OSError, RuntimeError, TypeError, ValueError) as error:
                reid_status = f"failed:{type(error).__name__}"
                logger.warning(
                    "SOLIDER inference failed; continuing in attribute-review mode: %s",
                    error,
                )

        par_runtime = self._get_solider_par()
        par_by_track: dict[int, dict[str, float]] = {}
        par_status = self._solider_par_status
        if par_runtime is not None:
            try:
                par_by_track = par_runtime.score(frames, self._base.get_solider_encoder())
                par_status = "used"
            except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
                par_status = f"failed:{type(error).__name__}"
                logger.warning("SOLIDER PAR inference failed: %s", error)
        elif fine_by_track:
            # This is a measurable fallback, not a SOLIDER success.  It keeps
            # the no-reference path useful while the GPU server artifact is
            # being provisioned.
            par_status = f"fallback:CLIP-PETA-PA100k:{self._fine_status}"

        grouped: dict[int, list[FrameAttributeScores]] = defaultdict(list)
        for index, (frame, semantic) in enumerate(zip(frames, semantic_scores, strict=True)):
            upper_color, lower_color = color_values[id(frame)]
            grouped[frame.track_id].append(
                FrameAttributeScores(
                    semantic=float(semantic),
                    upper_color=upper_color,
                    lower_color=lower_color,
                    fine_attribute=_fine_score(
                        fine_by_track.get(frame.track_id),
                        glasses=attributes.glasses,
                        hair=attributes.hair,
                        upper_style=attributes.upper_style,
                    ),
                    identity=(float(reid_scores[index]) if reid_scores is not None else None),
                    quality=crop_quality(frame.crop_path),
                    par_attribute=_fine_score(
                        par_by_track.get(frame.track_id) or fine_by_track.get(frame.track_id),
                        glasses=attributes.glasses,
                        hair=attributes.hair,
                        upper_style=attributes.upper_style,
                    ),
                )
            )

        base_by_track = {
            track_id: add_track_consistency(
                aggregate_track_scores(
                    rows,
                    attributes,
                    top_frames=self._config.aggregate_top_frames,
                ),
                [frame for frame in frames if frame.track_id == track_id],
            )
            for track_id, rows in grouped.items()
        }
        historical_by_track, historical_status = self._historical.score(
            frames,
            case_id=request.case_id,
            identity_anchor=identity_anchor,
            bundle=bundle,
        )
        fused_by_track = {
            track_id: fuse_track_scores(
                scores,
                historical=historical_by_track.get(track_id),
            )
            for track_id, scores in base_by_track.items()
        }
        evidence_frame_by_track: dict[int, TrackFrame] = {}
        evidence_quality_by_track: dict[int, float] = {}
        for track_id, track_rows in grouped.items():
            evidence = select_evidence_frame(
                tuple(frame for frame in frames if frame.track_id == track_id),
                tuple(track_rows),
                minimum_quality=self._minimum_person_crop_quality,
            )
            if evidence is not None:
                evidence_frame_by_track[track_id] = evidence
                evidence_quality_by_track[track_id] = crop_quality(evidence.crop_path)

        qwen_by_track: dict[int, float] = {}
        qwen_statuses: list[str] = []
        review_order = sorted(
            evidence_frame_by_track,
            key=lambda track_id: fused_by_track[track_id].score,
            reverse=True,
        )[: self._qwen_review.top_k]
        for track_id in review_order:
            representative = evidence_frame_by_track[track_id]
            review, status = self._qwen_review.review(
                representative.crop_path,
                case_id=request.case_id,
                camera_id=request.camera_id,
                track_id=track_id,
                prompt=request.prompt,
            )
            qwen_statuses.append(status)
            if review is not None:
                qwen_by_track[track_id] = review.score
        fused_by_track = {
            track_id: fuse_track_scores(
                scores,
                historical=historical_by_track.get(track_id),
                qwen=qwen_by_track.get(track_id),
            )
            for track_id, scores in base_by_track.items()
        }
        if qwen_by_track:
            mode = next(
                (
                    status.removeprefix("used:")
                    for status in qwen_statuses
                    if status.startswith("used:")
                ),
                "unknown",
            )
            qwen_status = f"used:{mode}:top{len(qwen_by_track)}"
        elif qwen_statuses:
            qwen_status = qwen_statuses[0]
        else:
            qwen_status = "not_attempted:no_track"

        statuses = [
            ("YOLO", "used"),
            ("CLIP-ViT-L/14", "used"),
            ("ROI-color", "used" if attributes.has_color_requirement else "not_required"),
            ("SOLIDER", reid_status),
            ("SOLIDER-PAR", par_status),
            ("CLIP-PETA-PA100k", self._fine_status),
            ("Historical-retrieval", historical_status),
            ("Temporal-fusion", "used"),
            ("Spatial-fusion", "used"),
            ("Grounding-DINO", "offline_teacher_not_runtime"),
            ("SAM2.1", "offline_teacher_not_runtime"),
            ("Florence-2", "offline_teacher_not_runtime"),
            ("Qwen", qwen_status),
            ("Sonnet", "offline_teacher_not_runtime"),
        ]
        self._last_model_trace = tuple(statuses)
        logger.info("candidate model ensemble trace %s", model_trace(statuses))

        candidates: list[RuntimeCandidate] = []
        for track_id, _rows in grouped.items():
            representative = evidence_frame_by_track.get(track_id)
            if representative is None:
                logger.info(
                    "candidate track rejected before attribute decision: "
                    "no readable YOLO person evidence track_id=%d minimum_quality=%.3f",
                    track_id,
                    self._minimum_person_crop_quality,
                )
                continue
            aggregate = fused_by_track[track_id]
            decision = decide_track(
                aggregate,
                attributes,
                minimum_output_score=self._minimum_output_score,
                color_reject_threshold=self._color_reject_threshold,
                similarity_threshold=request.similarity_threshold,
            )
            if not decision.emit:
                logger.debug(
                    "candidate track rejected track_id=%d score=%.4f reason=%s",
                    track_id,
                    decision.score,
                    decision.reason,
                )
                continue
            readable_frame_count = sum(
                1
                for frame in frames
                if frame.track_id == track_id
                and crop_quality(frame.crop_path) >= self._minimum_person_crop_quality
            )
            candidates.append(
                RuntimeCandidate(
                    candidate_key=f"track-{track_id}",
                    frame_offset_ms=representative.frame_offset_ms,
                    similarity=round(decision.score, 6),
                    frame_path=representative.frame_path,
                    crop_path=representative.crop_path,
                    bounding_box=RuntimeBoundingBox(
                        x=representative.left,
                        y=representative.top,
                        width=representative.right - representative.left,
                        height=representative.bottom - representative.top,
                    ),
                    attribute_summary=(
                        f"models={model_trace(statuses)};"
                        f"semantic={aggregate.semantic:.3f};"
                        f"requiredColor={_format_score(aggregate.required_color)};"
                        f"fine={_format_score(aggregate.fine_attribute)};"
                        f"par={_format_score(aggregate.par_attribute)};"
                        f"identity={_format_score(aggregate.identity)};"
                        f"historical={_format_score(aggregate.historical)};"
                        f"qwen={_format_score(aggregate.qwen)};"
                        f"temporal={aggregate.temporal:.3f};"
                        f"spatial={aggregate.spatial:.3f};"
                        f"quality={aggregate.quality:.3f};"
                        "personGate=YOLO:class0;"
                        f"readableFrames={readable_frame_count};"
                        f"evidenceQuality={evidence_quality_by_track[track_id]:.3f};"
                        f"identityAnchor={anchor_status};"
                        "candidateMode=operator_review"
                    )[:2_000],
                )
            )
        candidates.sort(key=lambda candidate: candidate.similarity, reverse=True)
        return CandidateRuntimeResponse(
            model_key=self.model_key,
            candidates=tuple(candidates[: self._config.top_k]),
        )


def _format_score(value: float | None) -> str:
    return "na" if value is None else f"{value:.3f}"


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    import os

    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def create_engine() -> MultiModelCandidateEngine:
    return MultiModelCandidateEngine(EngineConfig.from_environment())
