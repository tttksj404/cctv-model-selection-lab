#!/usr/bin/env python3
"""Build the simple presentation-first orchestration story diagram."""

from __future__ import annotations

import html
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
ASSET = ROOT / "tools" / "assets" / "claude_model_orchestration.svg"
OUTPUT = ROOT / "output" / "ai-presentation" / "model_orchestration.svg"
ROOT_SVG = REPO / "ai_worker_orchestration.svg"
PRES = REPO / "eyeson-u-ai-presentation-assets" / "svg" / "claude_ai_worker_orchestration.svg"
PRES_DATAFLOW = REPO / "eyeson-u-ai-presentation-assets" / "svg" / "claude_ai_worker_orchestration_dataflow.svg"

# DESIGN.md tokens, mapped to static-SVG sRGB values.
# The presentation enlarges the documented scale, but keeps its hierarchy:
# one primary accent, tonal surfaces, borders-only depth, and status colors only
# where they carry semantic meaning.
BG = "#f7f9fc"            # --surface-page
PANEL = "#ffffff"         # --surface-panel
SUBTLE = "#f1f4f8"        # --surface-subtle
SELECTED = "#eaf2fb"      # --surface-selected / --accent-soft
INK = "#252b36"           # --text-primary
MUTED = "#687386"         # --text-secondary
BORDER = "#d9e0ea"        # --border-default
STRONG_BORDER = "#b8c3d2" # --border-strong
BLUE = "#2f6fba"          # --accent-primary
BLUE_SOFT = SELECTED
GREEN = BLUE               # evidence is a tonal/runtime accent, not success
GREEN_SOFT = SUBTLE
ORANGE = "#b77721"        # --status-warning
ORANGE_SOFT = "#fff6e8"
PURPLE = BLUE              # late fusion remains in the primary accent family
PURPLE_SOFT = SELECTED
GRAY = "#7c8798"          # --status-unknown
GRAY_SOFT = SUBTLE
RED = ORANGE               # review is warning, not error
RED_SOFT = ORANGE_SOFT
SUCCESS = "#3b8a62"       # --status-success, used only for the result card
SUCCESS_SOFT = "#edf7f0"

WEIGHT_MAP = {400: 400, 600: 600, 650: 600, 700: 700, 750: 750,
              760: 760, 800: 750, 850: 760}


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def t(x: float, y: float, value: str, size: int = 16, color: str = INK,
      weight: int = 400, anchor: str = "start") -> str:
    weight = WEIGHT_MAP.get(weight, weight)
    return (
        f'<text x="{x}" y="{y}" font-family="Pretendard, Noto Sans KR, Arial, sans-serif" '
        f'font-size="{size}px" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(value)}</text>'
    )


def lines(x: float, y: float, values: list[str], size: int = 16,
          color: str = INK, weight: int = 400, gap: int = 24) -> str:
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else gap}px">{esc(value)}</tspan>'
        for i, value in enumerate(values)
    )
    return (
        f'<text x="{x}" y="{y}" font-family="Pretendard, Noto Sans KR, Arial, sans-serif" '
        f'font-size="{size}px" font-weight="{weight}" fill="{color}">{spans}</text>'
    )


def box(x: float, y: float, w: float, h: float, fill: str = PANEL,
        stroke: str = BORDER, radius: int = 14, width: int = 1,
        dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash_attr}/>'


def arrow(x1: float, y1: float, x2: float, y2: float, color: str = BLUE,
          marker: str = "blue", dash: str | None = None, width: int = 3) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    marker_attr = f' marker-end="url(#arrow-{marker})"' if marker != "none" else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{dash_attr}{marker_attr}/>'


def pill(x: float, y: float, value: str, color: str, fill: str,
         width: int, size: int = 14) -> str:
    return box(x, y - 19, width, 30, fill=fill, stroke=color, radius=8, width=1) + t(x + 10, y + 2, value, size, color, 650)


def stage(x: float, title: str, subtitle: str, receive: str, send: str | list[str],
          accent: str = BLUE, fill: str = PANEL, w: int = 244) -> str:
    y, h = 300, 300
    out = [box(x, y, w, h, fill=fill, stroke=BORDER)]
    out.append(box(x, y, 8, h, fill=accent, stroke=accent, radius=4, width=0))
    out.append(t(x + 24, y + 42, title, 23, INK, 800))
    out.append(t(x + 24, y + 70, subtitle, 16, accent, 700))
    out.append(arrow(x + 24, y + 88, x + w - 24, y + 88, "#edf0f5", "none", width=1))
    out.append(t(x + 24, y + 132, "받음", 14, accent, 800))
    out.append(t(x + 24, y + 164, receive, 18, INK, 650))
    out.append(t(x + 24, y + 214, "보냄", 14, accent, 800))
    send_lines = [send] if isinstance(send, str) else send
    for index, send_line in enumerate(send_lines):
        out.append(t(x + 24, y + 246 + index * 26, send_line, 18, INK, 650))
    return "".join(out)


def branch_card(x: float, title: str, receive: str, send: str, accent: str = BLUE) -> str:
    out = [box(x, 390, 144, 142, fill=SUBTLE, stroke=accent, radius=12, width=1)]
    out.append(t(x + 14, 419, title, 17, INK, 800))
    out.append(t(x + 14, 451, "받음", 14, accent, 800))
    out.append(t(x + 14, 473, receive, 15, INK, 600))
    out.append(t(x + 14, 501, "보냄", 14, accent, 800))
    out.append(t(x + 14, 523, send, 15, INK, 600))
    return "".join(out)


def build() -> str:
    out: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080" font-family="Pretendard, Noto Sans KR, Arial, sans-serif">',
        "<defs>",
        f'<marker id="arrow-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker>',
        f'<marker id="arrow-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{GREEN}"/></marker>',
        f'<marker id="arrow-orange" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{ORANGE}"/></marker>',
        f'<marker id="arrow-gray" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{GRAY}"/></marker>',
        "</defs>",
        box(0, 0, 1920, 1080, BG, BG, 0, 0),
    ]

    # Header and performance story.
    out += [
        t(56, 58, "AI Worker 오케스트레이션", 36, INK, 750),
        t(56, 94, "모델이 서로 다른 증거를 만들고, 오케스트레이션이 하나의 후보 판단으로 묶는다", 19, MUTED),
        t(56, 130, "단일 모델 최고 44%  →  증거 교환 + 파인튜닝 조합 77%", 20, BLUE, 750),
        box(110, 160, 520, 104, ORANGE_SOFT, STRONG_BORDER, 14, 1),
        t(138, 192, "단일 모델 최고", 18, ORANGE, 750),
        t(138, 245, "44%", 42, ORANGE, 760),
        t(280, 245, "한 모델의 단일 신호", 17, MUTED, 600),
        box(1290, 160, 520, 104, SUCCESS_SOFT, SUCCESS, 14, 1),
        t(1318, 192, "오케스트레이션 + 파인튜닝", 18, SUCCESS, 750),
        t(1318, 245, "77%", 42, SUCCESS, 760),
        t(1470, 245, "서로 다른 증거의 결합", 17, MUTED, 600),
        arrow(660, 212, 1260, 212, BLUE, "blue", width=4),
        pill(846, 200, "역할 분할 · track 집계 · late fusion", BLUE, BLUE_SOFT, 250, 15),
        arrow(56, 284, 1864, 284, BORDER, "none", width=1),
        t(56, 277, "RUNTIME · 한 줄로 읽는 정보 흐름", 18, INK, 750),
    ]

    # Six-step runtime, deliberately sparse.
    out.append(stage(56, "1  신고 + 녹화", "검색 입력", "인상착의·시간", "frame segment", BLUE))
    out.append(stage(320, "2  YOLO/ByteTrack", "사람 게이트", "frame", "crop + bbox + track_id", BLUE))
    # Branch group.
    out.append(box(584, 300, 488, 300, PANEL, BORDER, 14, 1))
    out.append(t(610, 342, "3  병렬 증거 모델", 23, INK, 800))
    out.append(t(610, 369, "같은 사람 crop을 서로 다른 증거로 변환", 16, MUTED))
    out.append(branch_card(600, "SOLIDER", "track crop", "reid_embedding"))
    out.append(branch_card(756, "CLIP", "text + crop", "clip_score"))
    out.append(branch_card(912, "PAR + ROI", "crop / mask", "attr_vector"))
    out.append(stage(1092, "4  Track 집계", "시간 축 통합", "3종 증거", "track_evidence", BLUE, PANEL, 240))
    out.append(stage(1352, "5  Late Fusion", "결합 판단", "track_evidence", ["match_score +", "uncertainty"], BLUE, SELECTED, 240))
    out.append(stage(1612, "6  Top-K 후보", "관리자 검토", "score + uncertainty", "candidate_packet", BLUE, PANEL, 252))
    # Arrows and short payload labels.
    out.append(arrow(300, 450, 320, 450, BLUE, "blue"))
    out.append(pill(296, 620, "segment", BLUE, BLUE_SOFT, 78, 13))
    out.append(arrow(564, 450, 584, 450, BLUE, "blue"))
    out.append(pill(560, 620, "crop + bbox + track_id", BLUE, BLUE_SOFT, 190, 13))
    out.append(arrow(1072, 450, 1092, 450, BLUE, "blue"))
    out.append(pill(1040, 620, "3 evidence", BLUE, BLUE_SOFT, 100, 13))
    out.append(arrow(1332, 450, 1352, 450, BLUE, "blue"))
    out.append(pill(1350, 620, "track_evidence", BLUE, BLUE_SOFT, 126, 13))
    out.append(arrow(1592, 450, 1612, 450, BLUE, "blue"))
    out.append(pill(1572, 620, "score + uncertainty", BLUE, BLUE_SOFT, 152, 13))

    # Why the orchestration improves the result.
    out.append(t(56, 650, "왜 오케스트레이션이 필요한가", 20, INK, 800))
    reasons = [
        (56, "역할을 나눔", "SOLIDER = 신원", "CLIP = 의미", "PAR = 속성", BLUE),
        (500, "시간으로 묶음", "프레임별 결과", "→ track_evidence", "한 사람 단위 판단", BLUE),
        (944, "결측에 대응", "가용 증거만 결합", "→ uncertainty", "검토 필요 사유", BLUE),
        (1388, "학습으로 개선", "teacher labels", "weights + calibration", "runtime에 반영", ORANGE),
    ]
    for x, title, first, second, third, accent in reasons:
        out.append(box(x, 674, 408, 122, PANEL, BORDER, 12, 1))
        out.append(t(x + 18, 704, title, 18, accent, 800))
        out.append(t(x + 18, 735, first, 16, INK, 650))
        out.append(t(x + 18, 760, second, 16, INK, 650))
        out.append(t(x + 18, 785, third, 15, MUTED, 600))

    # Offline teacher lane and Jetson bridge.
    out.append(box(56, 838, 1190, 112, SUBTLE, STRONG_BORDER, 14, 1, "10 7"))
    out.append(t(82, 873, "OFFLINE TEACHER", 18, MUTED, 800))
    out.append(t(82, 905, "Grounding DINO · SAM2.1 · Florence-2 · Sonnet", 18, INK, 650))
    out.append(arrow(610, 892, 754, 892, GRAY, "gray", dash="8 6", width=2))
    out.append(pill(650, 875, "labels / weights / calibration", GRAY, "#fff", 205, 13))
    out.append(t(790, 905, "→ 런타임 모델에 반영", 18, MUTED, 650))
    out.append(box(1280, 838, 584, 112, ORANGE_SOFT, ORANGE, 14, 1, "10 7"))
    out.append(t(1306, 873, "Jetson 실시간 후보", 18, "#b06a10", 800))
    out.append(t(1306, 905, "candidate_key + timestamp", 18, INK, 650))
    out.append(arrow(1600, 838, 1785, 600, ORANGE, "orange", dash="10 6", width=3))

    # Footer script/legend.
    out.append(arrow(56, 986, 1864, 986, BORDER, "none", width=1))
    out.append(t(56, 1022, "발표 한 문장", 16, BLUE, 800))
    out.append(t(190, 1022, "각 모델이 같은 답을 반복하는 것이 아니라, 서로 다른 증거를 만들고 late fusion에서 하나의 후보로 결합합니다.", 16, INK, 650))
    out.append(arrow(56, 1050, 92, 1050, BLUE, "none", width=3))
    out.append(t(104, 1056, "runtime", 13, MUTED, 650))
    out.append(arrow(180, 1050, 216, 1050, BLUE, "none", dash="6 4", width=3))
    out.append(t(228, 1056, "evidence · tonal shift", 13, MUTED, 600))
    out.append(arrow(420, 1050, 456, 1050, ORANGE, "none", width=3))
    out.append(t(468, 1056, "profile / control", 13, MUTED, 650))
    out.append(arrow(660, 1050, 696, 1050, GRAY, "none", dash="8 6", width=2))
    out.append(t(708, 1056, "offline teacher", 13, MUTED, 650))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    svg = build()
    for target in (ASSET, OUTPUT, ROOT_SVG, PRES):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8")
    # Preserve the previous detailed contract diagram as the appendix asset.
    if not PRES_DATAFLOW.exists():
        detailed = ROOT / "output" / "ai-presentation" / "model_orchestration_dataflow.svg"
        if detailed.exists():
            PRES_DATAFLOW.write_text(detailed.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"generated simple story SVG: {len(svg):,} bytes")


if __name__ == "__main__":
    main()

