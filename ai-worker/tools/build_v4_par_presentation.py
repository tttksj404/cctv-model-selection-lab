#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""Build presentation visuals for the repository-backed PAR v4 decision."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
REPO: Final = ROOT.parent
BG: Final = "#F8FAFC"
PANEL: Final = "#FFFFFF"
SUBTLE: Final = "#F1F5F9"
SELECTED: Final = "#EFF6FF"
INK: Final = "#1E293B"
MUTED: Final = "#64748B"
BORDER: Final = "#E2E8F0"
BLUE: Final = "#2563EB"
SLATE: Final = "#94A3B8"
GREEN: Final = "#34D399"
AMBER: Final = "#F59E0B"
FONT: Final = "Pretendard, Noto Sans KR, Arial, sans-serif"
MONO: Final = "Consolas, SFMono-Regular, Liberation Mono, monospace"


@dataclass(frozen=True, slots=True)
class ParRow:
    """One repository-reported PAR version comparison row."""

    version: str
    gender: float
    upper: float
    lower: float
    sleeve: float | None
    mean: float
    status: str


ROWS: Final[tuple[ParRow, ...]] = (
    ParRow("v1", 0.73, 0.53, 0.73, None, 0.67, "baseline"),
    ParRow("v2", 0.93, 0.47, 0.87, None, 0.76, "comparison"),
    ParRow("v3", 0.87, 0.53, 1.00, None, 0.80, "comparison"),
    ParRow("v4", 0.87, 0.80, 0.87, 1.00, 0.885, "adopted"),
    ParRow("v5", 0.80, 0.67, 0.87, 1.00, 0.835, "not_adopted"),
)
ATTRIBUTES: Final[tuple[tuple[str, str], ...]] = (
    ("성별", SLATE),
    ("상의색", BLUE),
    ("하의색", GREEN),
    ("소매길이", AMBER),
)


def esc(value: str) -> str:
    """Escape SVG text and attributes."""
    return html.escape(value, quote=True)


def text(x: int, y: int, value: str, size: int = 20, color: str = INK,
         weight: int = 400, family: str = FONT, anchor: str = "start") -> str:
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'font-family="{family}" font-size="{size}px" font-weight="{weight}" '
            f'fill="{color}">{esc(value)}</text>')


def center(x: int, y: int, value: str, size: int = 20, color: str = INK,
           weight: int = 400, family: str = FONT) -> str:
    return text(x, y, value, size, color, weight, family, "middle")


def box(x: int, y: int, w: int, h: int, fill: str = PANEL,
        stroke: str = BORDER, radius: int = 14, width: int = 1,
        opacity: str | None = None) -> str:
    alpha = f' opacity="{opacity}"' if opacity else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{alpha}/>')


def line(x1: int, y1: int, x2: int, y2: int, color: str = BORDER,
         width: int = 1, dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="{width}"{dash_attr}/>')


def arrow(x1: int, y1: int, x2: int, y2: int) -> str:
    """Return a blue line with a small arrowhead."""
    return (line(x1, y1, x2 - 9, y2, BLUE, 3) +
            f'<path d="M{x2 - 14},{y2 - 7} L{x2},{y2} L{x2 - 14},{y2 + 7} '
            f'Z" fill="{BLUE}"/>')


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def badge(out: list[str], x: int, y: int, label: str, fill: str, color: str) -> None:
    out.append(box(x, y, 150, 30, fill, fill, 15, 0))
    out.append(center(x + 75, y + 21, label, 13, color, 700, MONO))


def card(out: list[str], x: int, y: int, w: int, h: int, title: str,
         body: tuple[str, ...], tag: str, accent: str = BLUE) -> None:
    out.append(box(x, y, w, h, PANEL, BORDER, 12, 1))
    out.append(box(x, y, 7, h, accent, accent, 4, 0))
    out.append(text(x + 28, y + 38, title, 20, INK, 750))
    for index, value in enumerate(body):
        out.append(text(x + 28, y + 75 + index * 29, value, 17, MUTED, 550))
    badge(out, x + w - 178, y + h - 43, tag, SELECTED if accent == BLUE else SUBTLE,
          BLUE if accent == BLUE else MUTED)


def frame(title: str, subtitle: str) -> list[str]:
    return [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">',
        box(0, 0, 1920, 1080, BG, BG, 0, 0),
        text(80, 82, title, 46, INK, 750),
        text(80, 126, subtitle, 22, MUTED, 450),
        line(80, 164, 1840, 164, BORDER, 1),
    ]


def build_selection() -> str:
    out = frame("왜 v4를 채택했는가", "PAR 모델 버전별 비교 · yopar-train README 공개 테스트 수치")
    out.append(box(80, 200, 1100, 770, PANEL, BORDER, 18, 1))
    out.append(text(120, 252, "모델 버전 비교", 28, INK, 750))
    out.append(text(120, 286, "성별·상의색·하의색·소매길이별 분류 정확도", 18, MUTED, 500))
    for index, (label, color) in enumerate(ATTRIBUTES):
        x = 145 + index * 185
        out.append(box(x, 318, 14, 14, color, color, 3, 0))
        out.append(text(x + 22, 331, label, 16, MUTED, 650))
    chart_x, chart_y, chart_w, chart_h = 160, 400, 900, 430
    for tick in range(0, 6):
        y = chart_y + chart_h - int(chart_h * tick / 5)
        out.append(line(chart_x, y, chart_x + chart_w, y, BORDER, 1, "4 6"))
        out.append(center(chart_x - 34, y + 6, f"{tick * 20}%", 14, MUTED, 550, MONO))
    step = chart_w // len(ROWS)
    values = ("gender", "upper", "lower", "sleeve")
    for index, row in enumerate(ROWS):
        cx = chart_x + step * index + step // 2
        if row.status == "adopted":
            out.append(box(cx - 78, chart_y - 42, 156, chart_h + 72, SELECTED, BLUE, 2, 1))
        out.append(center(cx, chart_y - 58, pct(row.mean), 22 if row.status == "adopted" else 17,
                          BLUE if row.status == "adopted" else MUTED, 750 if row.status == "adopted" else 600, MONO))
        for attr_index, key in enumerate(values):
            value = getattr(row, key)
            bx = cx - 56 + attr_index * 29
            if value is None:
                out.append(center(bx + 8, chart_y + chart_h + 28, "—", 16, MUTED, 600, MONO))
                continue
            height = int(chart_h * value)
            out.append(box(bx, chart_y + chart_h - height, 17, height, ATTRIBUTES[attr_index][1],
                           ATTRIBUTES[attr_index][1], 3, 0,
                           "0.52" if row.status == "not_adopted" else None))
        out.append(center(cx, chart_y + chart_h + 58, row.version, 22, BLUE if row.status == "adopted" else INK,
                          750 if row.status == "adopted" else 650, MONO))
    out.append(text(120, 905, "평균 = 해당 버전에서 보고된 속성별 정확도의 평균", 16, MUTED, 500))
    out.append(text(120, 938, "v4 평균 88.5% · 비교 버전 중 최고", 21, BLUE, 750))
    card(out, 1230, 200, 610, 220, "v4 선정", ("PETA+Market 통합 학습", "4-head: 성별·상의·하의·소매", "평균 88.5% · 소매길이 100%"), "REPO MEASURED")
    card(out, 1230, 448, 610, 220, "v5 미채택", ("강한 augmentation + sampler", "상의색 80% → 67% 하락", "파랑·무채색 혼동 증가"), "README NOTE", MUTED)
    card(out, 1230, 696, 610, 220, "배포 형태", ("v4 weight → ONNX export", "TensorRT FP16 준비 경로", "color_par_v4_multi_resnet50_sleeve.onnx"), "REPO CODE")
    out.extend((line(80, 1002, 1840, 1002, BORDER, 1),
                text(80, 1036, "출처: github.com/donghyeoni/yopar-train · 테스트 15장(남 9 / 여 6)", 16, MUTED, 550),
                text(1840, 1036, "PAR 속성 분류 지표 · CCTV ReID Recall@5와 별개", 16, BLUE, 650, MONO, "end"),
                "</svg>"))
    return "\n".join(out) + "\n"


def build_pipeline() -> str:
    out = frame("v4 속성 인식이 들어가는 위치", "외부 PAR 모델을 CCTV 후보 탐색 오케스트레이션의 속성 게이트로 연결")
    out.append(box(80, 200, 610, 770, PANEL, BORDER, 18, 1))
    out.append(text(120, 252, "v4 4-head 프로파일", 28, INK, 750))
    out.append(text(120, 286, "저장소 테스트 수치", 18, MUTED, 500))
    heads = (("성별", 0.87, SLATE), ("상의색", 0.80, BLUE), ("하의색", 0.87, GREEN), ("소매길이", 1.00, AMBER))
    for index, (label, value, color) in enumerate(heads):
        y = 330 + index * 135
        out.append(box(120, y, 530, 105, PANEL, BORDER, 12, 1))
        out.append(text(148, y + 34, label + " head", 20, INK, 700))
        out.append(text(550, y + 34, pct(value), 22, BLUE if value >= 0.87 else INK, 750, MONO, "end"))
        out.append(box(148, y + 55, 430, 12, SUBTLE, BORDER, 6, 1))
        out.append(box(148, y + 55, int(430 * value), 12, color, color, 6, 0))
        out.append(text(148, y + 91, "PETA + Market · repository measured", 14, MUTED, 550, MONO))
    out.append(text(120, 920, "평균 88.5%", 26, BLUE, 750, MONO))
    out.append(text(310, 920, "4-head Multi-task ResNet50", 18, MUTED, 550))
    out.append(box(760, 200, 1080, 770, PANEL, BORDER, 18, 1))
    out.append(text(800, 252, "CCTV 후보 탐색 오케스트레이션", 28, INK, 750))
    out.append(text(800, 286, "v4는 신원 확정기가 아니라 속성 불일치를 줄이는 게이트로 동작", 18, MUTED, 500))
    nodes = (("RTSP 입력", ("4채널 카메라", "녹화·실시간"), False),
             ("검출 + 추적", ("YOLO11", "ByteTrack"), False),
             ("외모 특징", ("CLIP", "SOLIDER"), False),
             ("PAR v4 게이트", ("4개 속성 head", "불일치 제외"), True),
             ("후보 집계", ("track 증거", "Qwen 검토"), False))
    start_x, node_y, node_w, node_h, gap = 800, 430, 178, 142, 34
    for index, (title, details, highlighted) in enumerate(nodes):
        x = start_x + index * (node_w + gap)
        out.append(box(x, node_y, node_w, node_h, SELECTED if highlighted else SUBTLE,
                       BLUE if highlighted else BORDER, 14, 2 if highlighted else 1))
        out.append(center(x + node_w // 2, node_y + 38, title, 18, BLUE if highlighted else INK, 750))
        out.append(center(x + node_w // 2, node_y + 78, details[0], 16, MUTED, 600, MONO))
        out.append(center(x + node_w // 2, node_y + 106, details[1], 16, MUTED, 600))
        if index < len(nodes) - 1:
            out.append(arrow(x + node_w + 8, node_y + node_h // 2, x + node_w + gap - 8, node_y + node_h // 2))
    out.append(line(1412, 600, 1412, 690, BLUE, 2, "6 6"))
    out.append(text(1412, 726, "필수 속성 불일치면 후보에서 제외", 17, BLUE, 650, anchor="middle"))
    out.append(text(1412, 754, "저신뢰·모델 충돌만 Qwen이 설명", 17, MUTED, 550, anchor="middle"))
    badge(out, 800, 820, "REPOSITORY", SELECTED, BLUE)
    out.append(text(970, 842, "PAR v4 수치·Jetson 적용 경로", 16, MUTED, 550))
    badge(out, 800, 866, "PROJECT DESIGN", SUBTLE, MUTED)
    out.append(text(970, 888, "CLIP/SOLIDER late fusion·track 집계·Qwen 보조", 16, MUTED, 550))
    out.extend((box(80, 1002, 1760, 54, SELECTED, BORDER, 12, 1),
                text(108, 1037, "주의: PAR 평균 88.5%는 속성 분류 정확도이며, CCTV 인물 재식별 Recall@5와 합산한 수치가 아닙니다.", 17, BLUE, 650),
                "</svg>"))
    return "\n".join(out) + "\n"


def write_svg(name: str, content: str) -> None:
    """Write one SVG to the presentation package and handoff copies."""
    targets = (ROOT / "tools" / "assets" / name, ROOT / "output" / "ai-presentation" / name,
               REPO / name, REPO / "eyeson-u-ai-presentation-assets" / "svg" / name)
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def main() -> None:
    """Generate both v4 presentation visuals."""
    write_svg("v4_par_model_selection.svg", build_selection())
    write_svg("v4_par_pipeline.svg", build_pipeline())
    print("generated v4 PAR selection and pipeline SVGs")


if __name__ == "__main__":
    main()

