from __future__ import annotations

import os
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

import numpy as np

from qwen_backend.realtime_clip_scorer import ClipAttributeScorer
from qwen_backend.realtime_identity import SoliderIdentityScorer
from qwen_backend.realtime_model_security import verified_yolo_weights
from qwen_backend.realtime_models import (
    AppearanceProfile,
    BoundingBox,
    DecisionBand,
    FrameInference,
    RealtimeMatch,
    TrackState,
)
from qwen_backend.realtime_protocols import (
    AttributeScorer,
    Detector,
    IdentityScorer,
)
from qwen_backend.realtime_scoring import (
    resolve_frame_ambiguity,
    update_track,
)

os.environ["ULTRALYTICS_SAFE_LOAD"] = "1"


@dataclass(frozen=True, slots=True)
class RealtimeVisionConfig:
    clip_checkpoint: str = "openai/clip-vit-large-patch14"
    clip_revision: str = "32bd64288804d66eefd0ccbe215aa642df71cc41"
    yolo_weights: str = "models/yolo11x.pt"
    solider_checkpoint: str = "models/solider_reid/swin_base_msmt17.pth"
    solider_root: str = "external/SOLIDER-REID-runtime-8c08e1c"
    reference_image: Path | None = None
    model_directory: str = "models"
    model_manifest: str = "configs/realtime_model_manifest.json"
    device: str = "cuda"
    confidence: float = 0.30
    image_size: int = 640
    score_every_frames: int = 4
    track_ttl_frames: int = 90


@dataclass(frozen=True, slots=True)
class RealtimeVisionDependencies:
    detector: Detector
    scorer: AttributeScorer
    identity: IdentityScorer


class RealtimeVisionEngine:
    _config: RealtimeVisionConfig
    _profile: AppearanceProfile
    _detector: Detector
    _scorer: AttributeScorer
    _identity: IdentityScorer
    _states: dict[int, TrackState]
    _last_scored: dict[int, int]

    def __init__(
        self,
        profile: AppearanceProfile,
        config: RealtimeVisionConfig,
    ) -> None:
        from ultralytics import YOLO

        self._config = config
        self._profile = profile
        self._detector = cast(Detector, YOLO(verified_yolo_weights(config)))
        self._scorer = ClipAttributeScorer(profile, config)
        self._identity = SoliderIdentityScorer(config)
        self._states = {}
        self._last_scored = {}

    @classmethod
    def from_components(
        cls,
        profile: AppearanceProfile,
        config: RealtimeVisionConfig,
        dependencies: RealtimeVisionDependencies,
    ) -> RealtimeVisionEngine:
        engine = cls.__new__(cls)
        engine._config = config
        engine._profile = profile
        engine._detector = dependencies.detector
        engine._scorer = dependencies.scorer
        engine._identity = dependencies.identity
        engine._states = {}
        engine._last_scored = {}
        return engine

    def _expire_stale_tracks(self, frame_number: int) -> None:
        stale_track_ids = tuple(
            track_id
            for track_id, last_scored in self._last_scored.items()
            if frame_number - last_scored > self._config.track_ttl_frames
        )
        for track_id in stale_track_ids:
            self._states.pop(track_id, None)
            self._last_scored.pop(track_id, None)

    def process(self, frame_bgr: np.ndarray, frame_number: int) -> FrameInference:
        started = time.perf_counter()
        self._expire_stale_tracks(frame_number)
        results = self._detector.track(
            source=frame_bgr,
            persist=True,
            classes=[0],
            conf=self._config.confidence,
            imgsz=self._config.image_size,
            tracker="bytetrack.yaml",
            device=self._config.device,
            verbose=False,
        )
        result = results[0]
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            elapsed = (time.perf_counter() - started) * 1_000
            return FrameInference(
                matches=(),
                inference_ms=elapsed,
                identity_mode=self._identity.mode_label,
            )

        coordinates = boxes.xyxy.detach().cpu().numpy().astype(np.int32)
        confidences = boxes.conf.detach().cpu().numpy().astype(np.float32)
        track_ids = boxes.id.detach().cpu().numpy().astype(np.int32)
        matches: list[RealtimeMatch] = []
        scored_crops: dict[int, np.ndarray] = {}
        height, width = frame_bgr.shape[:2]
        for coordinates_row, confidence, track_id in zip(
            coordinates,
            confidences,
            track_ids,
            strict=True,
        ):
            left, top, right, bottom = (
                max(0, int(coordinates_row[0])),
                max(0, int(coordinates_row[1])),
                min(width, int(coordinates_row[2])),
                min(height, int(coordinates_row[3])),
            )
            crop = frame_bgr[top:bottom, left:right]
            box_area = (right - left) * (bottom - top)
            if crop.size == 0 or box_area < height * width * 0.01:
                continue
            track_id = int(track_id)
            previous = self._states.get(track_id)
            should_score = (
                previous is None
                or frame_number - self._last_scored.get(track_id, -999)
                >= self._config.score_every_frames
            )
            if should_score:
                evidence = self._scorer.score(crop)
                anchor_ready = self._identity.has_anchor
                if anchor_ready:
                    evidence = replace(
                        evidence,
                        identity=self._identity.similarity(crop),
                    )
                requirements = replace(
                    self._profile.requirements,
                    identity=anchor_ready,
                )
                state = update_track(
                    previous,
                    evidence,
                    requirements=requirements,
                )
                self._states[track_id] = state
                self._last_scored[track_id] = frame_number
                scored_crops[track_id] = crop
            else:
                assert previous is not None
                state = previous
            matches.append(
                RealtimeMatch(
                    track_id=track_id,
                    box=BoundingBox(left=left, top=top, right=right, bottom=bottom),
                    detection_confidence=float(confidence),
                    state=state,
                )
            )
        matches.sort(key=lambda item: item.state.decision.score, reverse=True)
        resolved = resolve_frame_ambiguity(tuple(matches))
        if not self._identity.has_anchor:
            enrollment_candidates = [
                match
                for match in resolved
                if match.track_id in scored_crops
                and match.state.decision.band is DecisionBand.CANDIDATE
            ]
            if len(enrollment_candidates) == 1:
                enrollment_candidate = enrollment_candidates[0]
                self._identity.enroll(scored_crops[enrollment_candidate.track_id])
        elapsed = (time.perf_counter() - started) * 1_000
        return FrameInference(
            matches=resolved,
            inference_ms=elapsed,
            identity_mode=self._identity.mode_label,
        )
