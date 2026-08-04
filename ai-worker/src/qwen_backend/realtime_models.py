from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

ColorTarget = Literal[
    "black",
    "blue",
    "brown",
    "gray",
    "green",
    "navy",
    "orange",
    "pink",
    "purple",
    "red",
    "white",
    "yellow",
]


class DecisionBand(StrEnum):
    CANDIDATE = "candidate"
    REVIEW = "review"
    MISMATCH = "mismatch"


@dataclass(frozen=True, slots=True)
class AppearanceRequirements:
    top_color: bool
    bottom_color: bool
    glasses: bool
    hair: bool
    upper_style: bool
    identity: bool

    @classmethod
    def default_demo(cls) -> AppearanceRequirements:
        return cls(
            top_color=True,
            bottom_color=True,
            glasses=True,
            hair=True,
            upper_style=True,
            identity=False,
        )


@dataclass(frozen=True, slots=True)
class AppearanceProfile:
    description_ko: str
    clip_query_en: str
    exclusion_query_en: str
    top_color_target: ColorTarget | None
    top_color_label_ko: str
    bottom_color_target: ColorTarget | None
    bottom_color_label_ko: str
    glasses_label_ko: str
    glasses_positive_en: str
    glasses_negative_en: str
    hair_label_ko: str
    hair_positive_en: str
    hair_negative_en: str
    upper_style_label_ko: str
    upper_style_positive_en: str
    upper_style_negative_en: str
    requirements: AppearanceRequirements

    @classmethod
    def default_demo(cls) -> AppearanceProfile:
        return cls(
            description_ko="회색 반팔, 검은색 바지, 안경, 넘긴 머리",
            clip_query_en=(
                "a person with swept-back hair wearing eyeglasses, "
                "a gray short-sleeve shirt, and black pants"
            ),
            exclusion_query_en=(
                "a person in different-colored clothes with no glasses and a different hairstyle"
            ),
            top_color_target="gray",
            top_color_label_ko="회색 상의",
            bottom_color_target="black",
            bottom_color_label_ko="검은 바지",
            glasses_label_ko="안경",
            glasses_positive_en="a close-up portrait wearing clear eyeglasses",
            glasses_negative_en="a close-up portrait with bare eyes and no eyeglasses",
            hair_label_ko="넘긴 머리",
            hair_positive_en="a portrait with swept-back or side-parted hair and visible forehead",
            hair_negative_en="a portrait with straight bangs covering the forehead",
            upper_style_label_ko="반팔",
            upper_style_positive_en="a short-sleeve shirt with bare forearms",
            upper_style_negative_en="a long-sleeve shirt, sweater, or jacket",
            requirements=AppearanceRequirements.default_demo(),
        )

    @classmethod
    def from_description(
        cls,
        description_ko: str,
        *,
        clip_query_en: str | None = None,
    ) -> AppearanceProfile:
        from qwen_backend.realtime_profile import parse_appearance_profile

        return parse_appearance_profile(
            description_ko,
            clip_query_en=clip_query_en,
        )


@dataclass(frozen=True, slots=True)
class AttributeEvidence:
    top_color: float | None
    bottom_color: float | None
    glasses: float | None
    hair: float | None
    upper_style: float | None
    holistic: float | None
    identity: float | None = None


@dataclass(frozen=True, slots=True)
class MatchDecision:
    band: DecisionBand
    score: float
    required_color_score: float | None
    required_semantic_score: float | None


@dataclass(frozen=True, slots=True)
class TrackState:
    evidence: AttributeEvidence
    observations: int
    decision: MatchDecision


@dataclass(frozen=True, slots=True)
class BoundingBox:
    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True, slots=True)
class RealtimeMatch:
    track_id: int
    box: BoundingBox
    detection_confidence: float
    state: TrackState


@dataclass(frozen=True, slots=True)
class FrameInference:
    matches: tuple[RealtimeMatch, ...]
    inference_ms: float
    identity_mode: str = "SOLIDER 자동등록 대기"


class CameraOpenError(Exception):
    def __init__(self, camera_index: int) -> None:
        super().__init__(f"카메라 인덱스 {camera_index}를 열 수 없습니다.")


class FrameReadError(Exception):
    def __init__(self, camera_index: int) -> None:
        super().__init__(
            f"카메라 인덱스 {camera_index}에서 프레임을 읽지 못했습니다."
        )


class AppearanceProfileError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ProfileInputCancelledError(Exception):
    def __init__(self) -> None:
        super().__init__("프로필 입력이 취소되었습니다.")


class HeadlessAppearanceRequiredError(Exception):
    def __init__(self) -> None:
        super().__init__("--headless 실행에는 --appearance가 필요합니다.")


class ReferenceImageError(Exception):
    def __init__(self, path: Path) -> None:
        super().__init__(f"기준 사진을 읽을 수 없습니다: {path.name}")


class SoliderCheckoutError(Exception):
    def __init__(self, root: Path, detail: str) -> None:
        super().__init__(f"SOLIDER 실행 코드 검증 실패 ({root.name}): {detail}")


class SoliderFeatureError(Exception):
    def __init__(self) -> None:
        super().__init__("SOLIDER 모델이 인물 특징 벡터를 반환하지 않았습니다.")
