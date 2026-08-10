from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from numpy.typing import NDArray

from qwen_backend.realtime_models import (
    AppearanceProfile,
    AttributeEvidence,
    DecisionBand,
)
from qwen_backend.realtime_vision import (
    RealtimeVisionConfig,
    RealtimeVisionDependencies,
    RealtimeVisionEngine,
)


@dataclass(frozen=True, slots=True)
class _FakeBoxes:
    xyxy: torch.Tensor
    conf: torch.Tensor
    id: torch.Tensor


@dataclass(frozen=True, slots=True)
class _FakeResult:
    boxes: _FakeBoxes


class _FakeDetector:
    def track(
        self,
        *,
        source: NDArray[np.uint8],
        persist: bool,
        classes: list[int],
        conf: float,
        imgsz: int,
        tracker: str,
        device: str,
        verbose: bool,
    ) -> tuple[_FakeResult, ...]:
        boxes = _FakeBoxes(
            xyxy=torch.tensor(
                [[0.0, 0.0, 140.0, 280.0], [160.0, 0.0, 300.0, 280.0]]
            ),
            conf=torch.tensor([0.95, 0.95]),
            id=torch.tensor([1.0, 2.0]),
        )
        return (_FakeResult(boxes),)


@dataclass(frozen=True, slots=True)
class _FakeScorer:
    evidence: AttributeEvidence

    def score(self, crop_bgr: NDArray[np.uint8]) -> AttributeEvidence:
        return self.evidence


class _RecordingIdentity:
    def __init__(self) -> None:
        self.enrolled: list[NDArray[np.uint8]] = []

    @property
    def has_anchor(self) -> bool:
        return False

    @property
    def mode_label(self) -> str:
        return "SOLIDER 자동등록 대기"

    def enroll(self, crop_bgr: NDArray[np.uint8]) -> None:
        self.enrolled.append(crop_bgr.copy())

    def similarity(self, crop_bgr: NDArray[np.uint8]) -> None:
        return None


def test_process_does_not_enroll_an_ambiguous_candidate() -> None:
    evidence = AttributeEvidence(0.90, 0.90, 0.90, 0.90, 0.90, 0.90)
    identity = _RecordingIdentity()
    engine = RealtimeVisionEngine.from_components(
        AppearanceProfile.default_demo(),
        RealtimeVisionConfig(device="cpu", score_every_frames=1),
        RealtimeVisionDependencies(
            detector=_FakeDetector(),
            scorer=_FakeScorer(evidence),
            identity=identity,
        ),
    )
    frame = np.full((300, 320, 3), 127, dtype=np.uint8)

    inference = engine.process(frame, frame_number=0)
    for frame_number in range(1, 3):
        inference = engine.process(frame, frame_number=frame_number)

    assert [match.state.decision.band for match in inference.matches] == [
        DecisionBand.REVIEW,
        DecisionBand.REVIEW,
    ]
    assert identity.enrolled == []


def test_realtime_config_rejects_hidden_invalid_runtime_limits() -> None:
    for kwargs in (
        {"tracker": ""},
        {"confidence": 1.1},
        {"image_size": 0},
        {"score_every_frames": 0},
        {"track_ttl_frames": 0},
        {"minimum_box_area_fraction": 1.1},
    ):
        try:
            RealtimeVisionConfig(**kwargs)
        except ValueError:
            continue
        raise AssertionError(f"invalid config was accepted: {kwargs}")

