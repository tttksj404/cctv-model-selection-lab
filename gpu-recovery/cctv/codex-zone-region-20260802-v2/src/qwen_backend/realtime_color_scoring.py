from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from qwen_backend.realtime_models import ColorTarget


class UnsupportedColorTargetError(ValueError):
    pass


def _clamp(score: float) -> float:
    return min(1.0, max(0.0, score))


def color_match_score(
    region_bgr: NDArray[np.uint8],
    *,
    target: ColorTarget,
) -> float:
    if region_bgr.size == 0:
        return 0.0
    pixels = region_bgr.reshape(-1, 3).astype(np.float32)
    blue = pixels[:, 0]
    green = pixels[:, 1]
    red = pixels[:, 2]

    if target == "navy":
        mask = (
            (blue >= 45.0)
            & (blue <= 180.0)
            & (blue >= green * 1.25)
            & (blue >= red * 1.55)
            & (green <= 130.0)
        )
    elif target == "black":
        maximum = pixels.max(axis=1)
        minimum = pixels.min(axis=1)
        mask = (maximum <= 70.0) & ((maximum - minimum) <= 45.0)
    elif target == "gray":
        maximum = pixels.max(axis=1)
        minimum = pixels.min(axis=1)
        brightness = pixels.mean(axis=1)
        mask = (
            (brightness >= 75.0)
            & (brightness <= 190.0)
            & ((maximum - minimum) <= 32.0)
        )
    else:
        hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        hue = hsv[:, 0]
        saturation = hsv[:, 1]
        value = hsv[:, 2]
        if target == "white":
            mask = (saturation <= 45) & (value >= 180)
        elif target == "red":
            mask = ((hue <= 10) | (hue >= 170)) & (saturation >= 80) & (value >= 60)
        elif target == "blue":
            mask = (hue >= 90) & (hue <= 130) & (saturation >= 70) & (value >= 50)
        elif target == "green":
            mask = (hue >= 35) & (hue <= 85) & (saturation >= 60) & (value >= 45)
        elif target == "brown":
            mask = (
                (hue >= 5)
                & (hue <= 25)
                & (saturation >= 60)
                & (value >= 35)
                & (value <= 180)
            )
        elif target == "yellow":
            mask = (hue >= 20) & (hue <= 38) & (saturation >= 70) & (value >= 100)
        elif target == "pink":
            mask = (hue >= 150) & (hue <= 179) & (saturation >= 40) & (value >= 100)
        elif target == "orange":
            mask = (hue >= 5) & (hue <= 22) & (saturation >= 90) & (value >= 170)
        elif target == "purple":
            mask = (hue >= 125) & (hue <= 160) & (saturation >= 60) & (value >= 60)
        else:
            raise UnsupportedColorTargetError(f"unsupported_color_target: {target}")

    return _clamp(float(np.mean(mask)) * 1.6)
