#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""Create neutral-white presentation copies without changing source evidence."""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
REPO = ROOT.parent
sys.path.insert(0, str(TOOLS))

import build_orchestration_core as orchestration  # noqa: E402
import build_performance_improvement_external85 as performance  # noqa: E402

WHITE = "#FFFFFF"
INK = "#171717"
MUTED = "#5A5A5A"
BORDER = "#D8D8D8"
SUBTLE = "#F6F6F6"
SELECTED = "#F0F0F0"
ACCENT = "#252525"


def neutral_svg(svg: str) -> str:
    """Replace the previous blue-toned design tokens with neutral tokens."""
    palette = {
        "#f7f9fc": WHITE,
        "#f1f4f8": WHITE,
        "#eaf2fb": WHITE,
        "#252b36": INK,
        "#687386": MUTED,
        "#d9e0ea": BORDER,
        "#b8c3d2": "#A8A8A8",
        "#2f6fba": ACCENT,
    }
    for source, target in palette.items():
        svg = svg.replace(source, target)
    return svg


def clean_performance() -> str:
    """Build the 85% comparison without the source/log disclosure on the slide."""
    data = json.loads(
        (ROOT / "output" / "ai-presentation" / "presentation_data.json").read_text(
            encoding="utf-8"
        )
    )
    claim = performance.load_claim()
    performance.BG = WHITE
    performance.PANEL = WHITE
    performance.SUBTLE = WHITE
    performance.SELECTED = WHITE
    performance.INK = INK
    performance.MUTED = MUTED
    performance.BORDER = BORDER
    performance.STRONG = "#A8A8A8"
    performance.BLUE = ACCENT
    return performance.build(data, claim)


def build_domain_gap_svg() -> str:
    """Rebuild the domain-gap chart with the annotation outside the bars."""
    width, height = 1674, 934
    left, right, top, bottom = 115, 1650, 150, 850
    plot_height = bottom - top
    centers = [255, 555, 855, 1155, 1455]
    labels = [
        ("v1", "Market, r18"),
        ("v2", "PETA, resnet50"),
        ("v3", "PETA+Market"),
        ("v4", "+소매 헤드"),
        ("v5", "+강한 증강"),
    ]
    validation = [0.94, 0.78, 0.77, None, 0.83]
    reality = [0.67, 0.76, 0.80, 0.89, 0.83]

    def y(value: float) -> float:
        return bottom - value * plot_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<style>text{font-family:Arial,"Malgun Gothic","Noto Sans KR",sans-serif;fill:#333333} .title{font-size:38px;font-weight:700;fill:#111111} .axis{font-size:27px;fill:#777777} .label{font-size:27px;fill:#4A4A4A} .value{font-size:27px;fill:#555555} .note{font-size:23px;fill:#555555}</style>',
        '<text x="115" y="58" class="title">검증 정확도 vs 실전 정확도 — 도메인 갭</text>',
        '<text x="430" y="92" class="note">검증셋 대비 실전 하락: 단일 도메인 과적합을 확인</text>',
        '<rect x="1215" y="84" width="28" height="22" fill="#2B2B2B"/><text x="1260" y="105" class="label">검증셋 (학습 데이터 분할)</text>',
        '<rect x="1215" y="122" width="28" height="22" fill="#F06A32"/><text x="1260" y="143" class="label">실전 테스트 (자체 촬영 15장)</text>',
    ]

    for tick in range(6):
        value = tick / 5
        yy = y(value)
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="#DDDDDD" stroke-width="2"/>')
        parts.append(f'<text x="72" y="{yy + 9:.1f}" text-anchor="middle" class="axis">{value:.1f}</text>')

    for index, center in enumerate(centers):
        first_x = center - 105
        second_x = center
        first = validation[index]
        if first is not None:
            first_y = y(first)
            parts.append(f'<rect x="{first_x}" y="{first_y:.1f}" width="105" height="{bottom - first_y:.1f}" fill="#2B2B2B"/>')
            parts.append(f'<text x="{first_x + 52.5}" y="{first_y - 10:.1f}" text-anchor="middle" class="value">{first:.2f}</text>')
        second_y = y(reality[index])
        parts.append(f'<rect x="{second_x}" y="{second_y:.1f}" width="105" height="{bottom - second_y:.1f}" fill="#F06A32"/>')
        parts.append(f'<text x="{second_x + 52.5}" y="{second_y - 10:.1f}" text-anchor="middle" class="value">{reality[index]:.2f}</text>')
        first_label, second_label = labels[index]
        parts.append(f'<text x="{center}" y="{bottom + 42}" text-anchor="middle" class="label"><tspan x="{center}" dy="0">{escape(first_label)}</tspan><tspan x="{center}" dy="34">{escape(second_label)}</tspan></text>')

    parts.extend([
        '<text x="34" y="520" transform="rotate(-90 34 520)" text-anchor="middle" class="label">평균 정확도</text>',
        '</svg>',
    ])
    return "".join(parts)


def write_svg(name: str, svg: str) -> None:
    """Write a clean SVG to the output package and desktop handoff root."""
    targets = (
        ROOT / "output" / "ai-presentation" / "clean" / name,
        ROOT / "tools" / "assets" / name,
        REPO / name,
        REPO / "eyeson-u-ai-presentation-assets" / "svg" / name,
    )
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8")


def main() -> None:
    """Generate neutral versions of the orchestration and performance slides."""
    write_svg("model_orchestration_clean.svg", neutral_svg(orchestration.build()))
    write_svg("performance_improvement_external85_clean.svg", clean_performance())
    write_svg("04_domain_gap_clean.svg", build_domain_gap_svg())
    print("generated neutral-white SVG presentation copies")


if __name__ == "__main__":
    main()

