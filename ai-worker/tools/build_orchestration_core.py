#!/usr/bin/env python3
"""Build the presentation-first model-to-model orchestration diagram."""

from __future__ import annotations

import html
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
ASSET = ROOT / "tools" / "assets" / "claude_model_orchestration.svg"
OUTPUT = ROOT / "output" / "ai-presentation" / "model_orchestration.svg"
ROOT_SVG = REPO / "ai_worker_orchestration.svg"
PRES = REPO / "eyeson-u-ai-presentation-assets" / "svg" / "claude_ai_worker_orchestration.svg"

# DESIGN.md tokens mapped to static-SVG sRGB values.
BG = "#f7f9fc"            # --surface-page
PANEL = "#ffffff"         # --surface-panel
SUBTLE = "#f1f4f8"        # --surface-subtle
SELECTED = "#eaf2fb"      # --surface-selected / --accent-soft
INK = "#252b36"           # --text-primary
MUTED = "#687386"         # --text-secondary
BORDER = "#d9e0ea"        # --border-default
STRONG = "#b8c3d2"        # --border-strong
BLUE = "#2f6fba"          # --accent-primary

FONT = "Pretendard, Noto Sans KR, Arial, sans-serif"
MONO = "Consolas, SFMono-Regular, Liberation Mono, monospace"


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def text(x: int, y: int, value: str, size: int = 16, color: str = INK,
         weight: int = 400, family: str = FONT) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}px" '
        f'font-weight="{weight}" fill="{color}">{esc(value)}</text>'
    )


def rect(x: int, y: int, w: int, h: int, fill: str = PANEL,
         stroke: str = BORDER, radius: int = 14, width: int = 1,
         dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash_attr}/>'
    )


def line(x1: int, y1: int, x2: int, y2: int, color: str = BLUE,
         width: int = 2, marker: str | None = "blue",
         dash: str | None = None) -> str:
    marker_attr = f' marker-end="url(#arrow-{marker})"' if marker else ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="{width}"{dash_attr}{marker_attr}/>'
    )


def path(points: list[tuple[int, int]], color: str = BLUE, width: int = 2,
         marker: str | None = "blue") -> str:
    d = "M" + " L".join(f"{x},{y}" for x, y in points)
    marker_attr = f' marker-end="url(#arrow-{marker})"' if marker else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{marker_attr}/>'


def pill(x: int, y: int, value: str, color: str = BLUE, fill: str = SELECTED,
         width: int = 160, size: int = 13) -> str:
    return rect(x, y - 19, width, 30, fill, color, 8, 1) + text(x + 10, y + 2, value, size, color, 600, MONO)


def accent_card(x: int, y: int, w: int, h: int, title: str,
                subtitle: str = "", fill: str = PANEL,
                accent: str = BLUE) -> str:
    out = [rect(x, y, w, h, fill, BORDER, 14, 1)]
    out.append(rect(x, y, 8, h, accent, accent, 4, 0))
    out.append(text(x + 28, y + 44, title, 28, INK, 700))
    if subtitle:
        out.append(text(x + 28, y + 78, subtitle, 18, MUTED, 400))
    return "".join(out)


def model_card(x: int, y: int, title: str, role: str, input_value: str,
               output_value: str) -> str:
    out = [rect(x, y, 400, 128, SUBTLE, BORDER, 12, 1)]
    out.append(rect(x, y, 6, 128, BLUE, BLUE, 3, 0))
    out.append(text(x + 22, y + 34, title, 24, INK, 700))
    out.append(text(x + 22, y + 64, role, 17, MUTED, 400))
    out.append(text(x + 22, y + 96, "→", 18, BLUE, 700))
    out.append(text(x + 48, y + 96, output_value, 18, BLUE, 600, MONO))
    out.append(text(x + 22, y + 120, f"입력: {input_value}", 16, MUTED, 400, MONO))
    return "".join(out)


def build() -> str:
    out: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">',
        "<defs>",
        f'<marker id="arrow-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker>',
        f'<marker id="arrow-gray" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{STRONG}"/></marker>',
        "</defs>",
        rect(0, 0, 1920, 1080, BG, BG, 0, 0),
    ]

    # Only the orchestration story remains in the main figure.
    out += [
        text(80, 62, "AI Worker 모델 오케스트레이션", 44, INK, 750),
        text(80, 104, "하나의 입력을 나눠 보고, 서로 다른 증거를 다시 하나의 후보로 결합한다", 22, MUTED, 400),
        rect(1320, 32, 520, 48, SUBTLE, BORDER, 10, 1),
        text(1344, 63, "단일 모델 최고 44%", 18, INK, 700),
        text(1544, 63, "→", 20, BLUE, 700),
        text(1580, 63, "Qwen 포함 오케스트레이션 77%", 18, BLUE, 700),
        line(80, 140, 1840, 140, BORDER, 1, None),
        text(80, 190, "모델 간 연결", 28, INK, 700),
        text(310, 190, "payload가 오케스트레이션의 핵심이다", 18, MUTED, 400),
    ]

    # Shared input: one context is fanned out to all evidence models.
    out.append(accent_card(80, 330, 320, 300, "공유 입력", "동일한 context를 병렬 전달", PANEL))
    out += [
        line(112, 416, 368, 416, BORDER, 1, None),
        text(112, 458, "인상착의 text", 22, INK, 600, MONO),
        text(112, 512, "track_crop", 22, BLUE, 600, MONO),
        text(112, 566, "track_id", 22, BLUE, 600, MONO),
    ]

    # Parallel model lane.
    out.append(rect(520, 210, 520, 590, PANEL, BORDER, 14, 1))
    out.append(text(552, 254, "병렬 증거 모델", 28, INK, 700))
    out.append(text(552, 290, "같은 입력 · 서로 다른 출력", 18, MUTED, 400))
    out.append(model_card(580, 320, "SOLIDER", "신원 증거", "text + crop", "reid_embedding"))
    out.append(model_card(580, 464, "CLIP", "의미 증거", "text + crop", "clip_score"))
    out.append(model_card(580, 608, "PAR + ROI", "속성 증거", "crop + mask", "attr_vector"))

    # Fan-out: structure lines are neutral; output payload lines are primary accent.
    out += [
        line(400, 480, 500, 480, STRONG, 1, None),
        line(500, 376, 500, 664, STRONG, 1, None),
        line(500, 376, 580, 376, BLUE, 2, "blue"),
        line(500, 520, 580, 520, BLUE, 2, "blue"),
        line(500, 664, 580, 664, BLUE, 2, "blue"),
    ]

    # Three outputs converge into one evidence contract.
    out.append(accent_card(1180, 330, 320, 300, "Evidence Contract", "track 단위로 세 출력을 묶음", SELECTED))
    out += [
        text(1212, 430, "reid_embedding", 16, BLUE, 600, MONO),
        text(1212, 480, "clip_score", 16, BLUE, 600, MONO),
        text(1212, 530, "attr_vector", 16, BLUE, 600, MONO),
        line(980, 376, 1100, 376, BLUE, 2, None),
        path([(980, 376), (1100, 376), (1100, 430), (1180, 430)], BLUE, 2, "blue"),
        path([(980, 520), (1120, 520), (1120, 480), (1180, 480)], BLUE, 2, "blue"),
        path([(980, 664), (1140, 664), (1140, 530), (1180, 530)], BLUE, 2, "blue"),
        text(1212, 610, "track_evidence", 20, BLUE, 600, MONO),
        path([(1340, 630), (1340, 680)], BLUE, 2, "blue"),
        text(1186, 662, "profile + evidence", 16, BLUE, 600, MONO),
    ]

    # Qwen validates semantic and attribute consistency before late fusion.
    out.append(accent_card(1180, 680, 320, 160, "Qwen3-VL", "의미·속성 검증", SUBTLE))
    out += [
        text(1212, 790, "qwen_score", 22, BLUE, 600, MONO),
        text(1212, 826, "입력: profile + evidence", 16, MUTED, 400, MONO),
    ]

    # Late fusion and candidate result are the only sequential decision stages.
    out.append(accent_card(1580, 330, 280, 240, "Late Fusion", "시각 증거 + Qwen 검증 결합", PANEL))
    out += [
        text(1612, 430, "track_evidence", 20, BLUE, 600, MONO),
        text(1612, 466, "qwen_score", 20, BLUE, 600, MONO),
        text(1612, 510, "match_score +", 20, INK, 600, MONO),
        text(1612, 540, "uncertainty", 20, INK, 600, MONO),
        line(1500, 430, 1580, 430, BLUE, 3, "blue"),
        path([(1500, 790), (1540, 790), (1540, 466), (1580, 466)], BLUE, 3, "blue"),
        line(1720, 570, 1720, 650, BLUE, 3, "blue"),
    ]
    out.append(accent_card(1580, 650, 280, 180, "최종 후보", "후보 점수와 검토 사유", SELECTED))
    out += [
        text(1612, 754, "candidate_score", 20, BLUE, 600, MONO),
        text(1612, 794, "review_required", 18, INK, 600, MONO),
    ]

    out += [
        line(80, 900, 1840, 900, BORDER, 1, None),
        text(80, 956, "발표 한 문장", 20, BLUE, 700),
        text(250, 956, "같은 입력을 세 시각 증거 모델에 공유하고, Qwen이 속성·의미를 검증한 뒤 Late Fusion에서 하나의 후보 점수로 결합합니다.", 22, INK, 600),
    ]
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    svg = build()
    for target in (ASSET, OUTPUT, ROOT_SVG, PRES):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8")
    print(f"generated orchestration core SVG: {len(svg):,} bytes")


if __name__ == "__main__":
    main()

