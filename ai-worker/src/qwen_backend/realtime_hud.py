from __future__ import annotations

from pathlib import Path
from typing import Final

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from qwen_backend.realtime_models import (
    AppearanceProfile,
    DecisionBand,
    FrameInference,
)

PANEL_WIDTH: Final = 460
FRAME_WIDTH: Final = 960
FRAME_HEIGHT: Final = 720
BACKGROUND: Final = (12, 16, 24)
PANEL: Final = (19, 25, 36)
TEXT: Final = (236, 240, 248)
MUTED: Final = (148, 163, 184)
ACCENT: Final = (70, 196, 255)
SUCCESS: Final = (67, 214, 160)
WARNING: Final = (255, 184, 77)
DANGER: Final = (255, 92, 120)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("C:/Windows/Fonts/malgunbd.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _band_style(band: DecisionBand) -> tuple[str, tuple[int, int, int]]:
    styles = {
        DecisionBand.CANDIDATE: ("인상착의 유사도 높음", DANGER),
        DecisionBand.REVIEW: ("인상착의 재검토", WARNING),
        DecisionBand.MISMATCH: ("인상착의 유사도 낮음", SUCCESS),
    }
    return styles[band]

def _fit_frame(frame_bgr: np.ndarray) -> tuple[Image.Image, float, int, int]:
    height, width = frame_bgr.shape[:2]
    scale = min(FRAME_WIDTH / width, FRAME_HEIGHT / height)
    resized_width = round(width * scale)
    resized_height = round(height * scale)
    resized = cv2.resize(frame_bgr, (resized_width, resized_height))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    offset_x = (FRAME_WIDTH - resized_width) // 2
    offset_y = (FRAME_HEIGHT - resized_height) // 2
    return Image.fromarray(rgb), scale, offset_x, offset_y


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    position: tuple[int, int],
    width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    line_height: int,
) -> int:
    x, y = position
    line = ""
    lines: list[str] = []
    for character in text:
        candidate = f"{line}{character}"
        if draw.textlength(candidate, font=font) <= width:
            line = candidate
        else:
            lines.append(line)
            line = character
    if line:
        lines.append(line)
    for row in lines:
        draw.text((x, y), row, font=font, fill=fill)
        y += line_height
    return y


def _draw_attribute_bars(
    draw: ImageDraw.ImageDraw,
    profile: AppearanceProfile,
    inference: FrameInference,
    *,
    panel_x: int,
    start_y: int,
) -> None:
    label_font = _font(18)
    value_font = _font(16)
    if not inference.matches:
        draw.text(
            (panel_x, start_y),
            "화면에서 사람을 찾는 중입니다.",
            font=label_font,
            fill=MUTED,
        )
        return
    evidence = inference.matches[0].state.evidence
    rows: list[tuple[str, float | None]] = []
    if profile.requirements.top_color:
        rows.append((profile.top_color_label_ko, evidence.top_color))
    if profile.requirements.bottom_color:
        rows.append((profile.bottom_color_label_ko, evidence.bottom_color))
    if profile.requirements.glasses:
        rows.append((profile.glasses_label_ko, evidence.glasses))
    if profile.requirements.hair:
        rows.append((profile.hair_label_ko, evidence.hair))
    if profile.requirements.upper_style:
        rows.append((profile.upper_style_label_ko, evidence.upper_style))
    rows.append(("전체 인상착의", evidence.holistic))
    if evidence.identity is not None:
        rows.append(("SOLIDER 동일인", evidence.identity))
    for index, (label, score) in enumerate(rows):
        y = start_y + index * 40
        draw.text((panel_x, y), label, font=label_font, fill=TEXT)
        value_text = "관측 불가" if score is None else f"{score * 100:5.1f}점"
        draw.text(
            (panel_x + 310, y),
            value_text,
            font=value_font,
            fill=MUTED,
        )
        draw.rounded_rectangle(
            (panel_x, y + 26, panel_x + 360, y + 34),
            radius=4,
            fill=(43, 52, 68),
        )
        if score is not None:
            draw.rounded_rectangle(
                (panel_x, y + 26, panel_x + round(360 * score), y + 34),
                radius=4,
                fill=ACCENT,
            )


def render_dashboard(
    frame_bgr: np.ndarray,
    profile: AppearanceProfile,
    inference: FrameInference,
    *,
    camera_index: int,
    fps: float,
    device_name: str,
    auto_save_interval: int,
) -> np.ndarray:
    canvas = Image.new("RGB", (FRAME_WIDTH + PANEL_WIDTH, FRAME_HEIGHT), BACKGROUND)
    camera_image, scale, offset_x, offset_y = _fit_frame(frame_bgr)
    canvas.paste(camera_image, (offset_x, offset_y))
    draw = ImageDraw.Draw(canvas)
    title_font = _font(28)
    heading_font = _font(20)
    body_font = _font(17)
    small_font = _font(14)
    footer_font = _font(12)
    panel_x = FRAME_WIDTH + 34
    draw.rectangle((FRAME_WIDTH, 0, FRAME_WIDTH + PANEL_WIDTH, FRAME_HEIGHT), fill=PANEL)
    draw.text((panel_x, 28), "EYES:ON U", font=title_font, fill=TEXT)
    draw.text((panel_x, 68), "실시간 인상착의 유사도 탐색", font=heading_font, fill=ACCENT)
    draw.text((panel_x, 112), "신고 인상착의", font=small_font, fill=MUTED)
    profile_end = _draw_wrapped(
        draw,
        profile.description_ko,
        position=(panel_x, 136),
        width=380,
        font=body_font,
        fill=TEXT,
        line_height=28,
    )
    draw.line((panel_x, profile_end + 12, panel_x + 390, profile_end + 12), fill=(48, 59, 76))

    for match in inference.matches:
        label, color = _band_style(match.state.decision.band)
        box = match.box
        scaled = (
            offset_x + round(box.left * scale),
            offset_y + round(box.top * scale),
            offset_x + round(box.right * scale),
            offset_y + round(box.bottom * scale),
        )
        draw.rectangle(scaled, outline=color, width=4)
        short_label = {
            DecisionBand.CANDIDATE: "후보",
            DecisionBand.REVIEW: "검토",
            DecisionBand.MISMATCH: "낮음",
        }[match.state.decision.band]
        tag = f"{short_label}  T{match.track_id}  {match.state.decision.score * 100:.1f}"
        tag_width = round(draw.textlength(tag, font=body_font)) + 20
        tag_top = max(4, scaled[1] - 34)
        draw.rounded_rectangle(
            (scaled[0], tag_top, scaled[0] + tag_width, tag_top + 30),
            radius=6,
            fill=color,
        )
        draw.text((scaled[0] + 10, tag_top + 4), tag, font=body_font, fill=BACKGROUND)

    if inference.matches:
        top = inference.matches[0]
        label, color = _band_style(top.state.decision.band)
        draw.text(
            (panel_x, profile_end + 34),
            "현재 최고 유사 항목 · 휴리스틱 점수(확률 아님)",
            font=small_font,
            fill=MUTED,
        )
        draw.text(
            (panel_x, profile_end + 56),
            f"{label}  유사도점수 {top.state.decision.score * 100:.1f}",
            font=heading_font,
            fill=color,
        )
        bars_y = profile_end + 102
    else:
        bars_y = profile_end + 50
    _draw_attribute_bars(
        draw,
        profile,
        inference,
        panel_x=panel_x,
        start_y=bars_y,
    )

    footer_y = FRAME_HEIGHT - 100
    draw.line((panel_x, footer_y - 14, panel_x + 390, footer_y - 14), fill=(48, 59, 76))
    draw.text(
        (panel_x, footer_y),
        f"Camera {camera_index}  |  {fps:.1f} FPS  |  {inference.inference_ms:.0f} ms",
        font=footer_font,
        fill=MUTED,
    )
    save_status = (
        "자동저장 꺼짐"
        if auto_save_interval == 0
        else f"자동저장 {auto_save_interval}프레임"
    )
    draw.text(
        (panel_x, footer_y + 23),
        device_name,
        font=footer_font,
        fill=MUTED,
    )
    draw.text(
        (panel_x, footer_y + 46),
        inference.identity_mode,
        font=footer_font,
        fill=MUTED,
    )
    draw.text(
        (panel_x, footer_y + 69),
        f"{save_status}  |  Q/ESC 종료  ·  S 화면 저장",
        font=footer_font,
        fill=TEXT,
    )
    return cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR)
