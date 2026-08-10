#!/usr/bin/env python3
"""Build a presentation chart with final orchestration performance as the headline."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
DATA_PATH = ROOT / "output" / "ai-presentation" / "presentation_data.json"
ASSET = ROOT / "tools" / "assets" / "claude_performance_improvement.svg"
OUTPUT = ROOT / "output" / "ai-presentation" / "performance_improvement.svg"
ROOT_SVG = REPO / "performance_improvement.svg"
PRES_SVG = REPO / "eyeson-u-ai-presentation-assets" / "svg" / "claude_performance_improvement.svg"

BG = "#f7f9fc"
PANEL = "#ffffff"
SUBTLE = "#f1f4f8"
SELECTED = "#eaf2fb"
INK = "#252b36"
MUTED = "#687386"
BORDER = "#d9e0ea"
STRONG = "#b8c3d2"
BLUE = "#2f6fba"
FONT = "Pretendard, Noto Sans KR, Arial, sans-serif"
MONO = "Consolas, SFMono-Regular, Liberation Mono, monospace"


class PerformanceDataError(ValueError):
    """Raised when the saved presentation evidence lacks a required method."""


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def text(x: int, y: int, value: str, size: int = 20, color: str = INK,
         weight: int = 400, family: str = FONT, anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-family="{family}" font-size="{size}px" font-weight="{weight}" '
        f'fill="{color}">{esc(value)}</text>'
    )


def rect(x: int, y: int, w: int, h: int, fill: str = PANEL,
         stroke: str = BORDER, radius: int = 16, width: int = 1) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
    )


def line(x1: int, y1: int, x2: int, y2: int, color: str = BORDER,
         width: int = 2, marker: str | None = None) -> str:
    marker_attr = f' marker-end="url(#{marker})"' if marker else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="{width}"{marker_attr}/>'
    )


def center_text(x: int, y: int, value: str, size: int = 20,
                color: str = INK, weight: int = 400,
                family: str = FONT) -> str:
    return text(x, y, value, size, color, weight, family, "middle")


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp(current: float, baseline: float) -> str:
    return f"{(current - baseline) * 100:+.2f}%p"


def find_method(identity: dict[str, Any], short_name: str) -> dict[str, Any]:
    for method in identity["strict_methods"]:
        if method["short_name"] == short_name:
            return method
    raise PerformanceDataError(f"strict method not found: {short_name}")


def metric_row(y: int, label: str, description: str, baseline: float,
               current: float, delta: str, max_width: int = 900) -> str:
    baseline_width = int(max_width * baseline)
    current_width = int(max_width * current)
    out = [
        text(120, y, label, 29, INK, 750),
        text(120, y + 35, description, 18, MUTED, 500),
        center_text(500, y + 4, percent(baseline), 26, INK, 700, MONO),
        center_text(805, y + 4, percent(current), 30, BLUE, 750, MONO),
        center_text(1080, y + 4, delta, 27, BLUE, 750, MONO),
        rect(120, y + 62, max_width, 20, SUBTLE, BORDER, 10, 1),
        rect(120, y + 62, baseline_width, 20, PANEL, STRONG, 10, 1),
        rect(120, y + 92, max_width, 20, SUBTLE, BORDER, 10, 1),
        rect(120, y + 92, current_width, 20, SELECTED, BLUE, 10, 1),
    ]
    return "".join(out)


def build(data: dict[str, Any]) -> str:
    headline = data["headline"]
    identity = data["identity_evidence"]
    attributes = data["attribute_evidence"]
    baseline = find_method(identity, headline["baseline_name"])
    best = find_method(identity, headline["best_name"])
    recall_delta = pp(best["recall_at_5"], baseline["recall_at_5"])
    rank1_delta = pp(best["rank1"], baseline["rank1"])

    out: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">',
        "<defs>",
        f'<marker id="arrow-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="10" markerHeight="10" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker>',
        "</defs>",
        rect(0, 0, 1920, 1080, BG, BG, 0, 0),
        text(80, 78, "AI Worker 최종 성능", 46, INK, 750),
        text(80, 120, "동일 strict Rank-1/Recall@5 평가에서 후보 검색 성능과 선택 runtime을 분리해 표시", 22, MUTED, 400),
        rect(1430, 48, 410, 54, SELECTED, BORDER, 12, 1),
        center_text(1635, 82, "STRICT TOP-K · Recall@5 77.89%", 19, BLUE, 750, MONO),
        line(80, 154, 1840, 154, BORDER, 1),
        rect(80, 204, 1160, 570, PANEL, BORDER, 18, 1),
        text(120, 254, "최종 서비스 지표", 28, INK, 750),
        text(120, 286, "정답 identity를 Top-K 후보 안에 넣고 관리자 검토로 연결", 19, MUTED, 500),
        text(500, 328, "strict 기준선", 18, MUTED, 700, anchor="middle"),
        text(805, 328, "strict 최고 후보", 18, BLUE, 700, anchor="middle"),
        text(1080, 328, "개선폭", 18, MUTED, 700, anchor="middle"),
        metric_row(374, "Recall@5", "최종 후보 포함률 · 서비스 주지표", baseline["recall_at_5"], best["recall_at_5"], recall_delta),
        metric_row(558, "Rank-1", "1위 후보가 정답인 비율 · 보조 지표", baseline["rank1"], best["rank1"], rank1_delta),
        text(120, 742, "baseline = CLIP ViT-B/32", 18, MUTED, 600, MONO),
        text(1080, 742, "selected runtime = hybrid-solider-clip-v1", 18, BLUE, 650, MONO, "end"),
        rect(1280, 204, 560, 570, SELECTED, BLUE, 2, 1),
        rect(1280, 204, 10, 570, BLUE, BLUE, 5, 0),
        text(1320, 260, "strict 최고 후보 검색", 24, BLUE, 750),
        text(1320, 304, "SOLIDER top-3", 28, INK, 750, MONO),
        text(1320, 356, "strict 후보 포함률", 21, MUTED, 600),
        text(1320, 445, percent(best["recall_at_5"]), 78, BLUE, 750, MONO),
        text(1320, 488, "Recall@5", 24, BLUE, 700, MONO),
        line(1320, 520, 1790, 520, BORDER, 1),
        text(1320, 570, f"Rank-1  {percent(best['rank1'])}", 28, INK, 700, MONO),
        text(1320, 615, f"{rank1_delta} · 약 2.8배", 24, BLUE, 700, MONO),
        text(1320, 675, "strict metric row = SOLIDER top-3", 18, BLUE, 650, MONO),
        text(1320, 705, "runtime selected = hybrid-solider-clip-v1", 18, MUTED, 550, MONO),
        rect(80, 814, 840, 126, PANEL, BORDER, 14, 1),
        text(112, 854, "별도 속성 분류 보조 지표", 22, MUTED, 700),
        text(112, 898, f"SOLIDER PAR fine-tune  {percent(attributes['solider_ft_instance_accuracy'])}", 26, INK, 700, MONO),
        text(112, 925, "identity retrieval 정확도와 다른 평가 축", 18, MUTED, 500),
        rect(960, 814, 880, 126, SUBTLE, BORDER, 14, 1),
        text(992, 854, "평가 범위", 22, INK, 700),
        text(992, 898, "CHIRLA strict · 11 identities · 95 queries", 23, BLUE, 700, MONO),
        text(992, 925, "camera/sequence overlap 제거", 18, MUTED, 500),
        rect(80, 968, 1760, 64, SUBTLE, BORDER, 12, 1),
        text(112, 1009, "Qwen3-VL은 후보 설명·속성 충돌 검토 보조 계층이며, 77.89%는 Qwen 단독 상승이 아닌 최종 후보 검색 Recall@5", 23, MUTED, 650),
        "</svg>",
    ]
    return "\n".join(out) + "\n"


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    svg = build(data)
    for target in (ASSET, OUTPUT, ROOT_SVG, PRES_SVG):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8")
    print(f"generated final performance SVG: {len(svg):,} bytes")


if __name__ == "__main__":
    main()

