#!/usr/bin/env python3
"""Build the Claude-directed BEFORE/AFTER performance presentation chart."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from build_performance_improvement import (  # noqa: E402
    BG,
    BLUE,
    BORDER,
    FONT,
    INK,
    MUTED,
    PANEL,
    SELECTED,
    STRONG,
    SUBTLE,
    center_text,
    find_method,
    line,
    percent,
    pp,
    rect,
    text,
)


ROOT = TOOLS.parent
REPO = ROOT.parent
DATA_PATH = ROOT / "output" / "ai-presentation" / "presentation_data.json"
CLAIM_PATH = ROOT / "output" / "ai-presentation" / "external_recall5_result.json"
OUTPUTS = (
    ROOT / "tools" / "assets" / "claude_performance_improvement_external85.svg",
    ROOT / "output" / "ai-presentation" / "performance_improvement_external85.svg",
    REPO / "performance_improvement_external85.svg",
    REPO / "eyeson-u-ai-presentation-assets" / "svg" / "claude_performance_improvement_external85.svg",
)
MONO = "Consolas, SFMono-Regular, Liberation Mono, monospace"


class ExternalResultError(ValueError):
    """Raised when the supplied Recall@5 value is malformed."""


def circle(cx: int, cy: int, radius: int, fill: str, stroke: str | None = None) -> str:
    stroke = stroke or fill
    return f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'


def load_claim() -> dict[str, Any]:
    claim = json.loads(CLAIM_PATH.read_text(encoding="utf-8"))
    if claim.get("metric") != "Recall@5":
        raise ExternalResultError("claim metric must be Recall@5")
    value = float(claim["value"])
    if not 0.0 <= value <= 1.0:
        raise ExternalResultError("Recall@5 must be between 0 and 1")
    if claim.get("status") != "user_reported_external":
        raise ExternalResultError("claim status must remain user_reported_external")
    return claim


def build(data: dict[str, Any], claim: dict[str, Any]) -> str:
    headline = data["headline"]
    identity = data["identity_evidence"]
    baseline = find_method(identity, headline["baseline_name"])
    current = float(claim["value"])
    delta = pp(current, baseline["recall_at_5"])

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">',
        rect(0, 0, 1920, 1080, BG, BG, 0, 0),
        text(80, 84, "AI 오케스트레이션 Re-ID 성능 개선", 46, INK, 750),
        text(80, 132, "단일 모델 → 오케스트레이션 + 파인튜닝", 24, MUTED, 500),
        text(1840, 84, "ORCHESTRATION + FINE-TUNING", 18, BLUE, 750, MONO, "end"),
        line(80, 166, 1840, 166, BORDER, 1),
        rect(80, 212, 600, 430, PANEL, BORDER, 18, 1),
        text(120, 268, "BEFORE · 단일 모델", 20, MUTED, 750, MONO),
        text(120, 322, "CLIP ViT-B/32", 30, INK, 750, MONO),
        text(120, 378, "Recall@5", 22, MUTED, 600, MONO),
        text(120, 516, percent(baseline["recall_at_5"]), 64, INK, 750, MONO),
        text(120, 558, "단일 임베딩 후보 검색", 20, MUTED, 500),
        text(640, 596, "baseline", 17, MUTED, 600, MONO, "end"),
        rect(1230, 192, 610, 470, SELECTED, BLUE, 2, 18),
        text(1270, 250, "AFTER · ORCHESTRATION", 20, BLUE, 750, MONO),
        text(1270, 304, "CLIP + SOLIDER + Qwen", 30, INK, 750, MONO),
        text(1270, 360, "Recall@5", 22, MUTED, 600, MONO),
        text(1270, 510, percent(current), 100, BLUE, 750, MONO),
        text(1270, 555, "오케스트레이션 + 파인튜닝", 20, BLUE, 650),
        text(1800, 616, "final", 17, BLUE, 650, MONO, "end"),
        center_text(955, 400, "→", 88, BLUE, 750, MONO),
        center_text(955, 500, delta, 27, BLUE, 750, MONO),
        center_text(955, 535, "개선폭", 17, MUTED, 600),
        rect(80, 730, 1760, 260, SUBTLE, BORDER, 18, 1),
        text(120, 778, "오케스트레이션 파이프라인", 23, INK, 750),
        line(430, 850, 680, 850, BORDER, 3),
        line(1000, 850, 1250, 850, BORDER, 3),
        circle(170, 850, 28, BLUE),
        circle(740, 850, 28, BLUE),
        circle(1310, 850, 28, BLUE),
        center_text(170, 858, "1", 20, PANEL, 750, MONO),
        center_text(740, 858, "2", 20, PANEL, 750, MONO),
        center_text(1310, 858, "3", 20, PANEL, 750, MONO),
        text(220, 846, "CLIP 검색", 23, INK, 750),
        text(220, 880, "후보 추출", 18, MUTED, 500),
        text(790, 846, "SOLIDER 파인튜닝", 23, INK, 750),
        text(790, 880, "특징 정밀화", 18, MUTED, 500),
        text(1360, 846, "Qwen 품질검토", 23, INK, 750),
        text(1360, 880, "후보 설명·오답 필터링", 18, MUTED, 500),
        line(120, 925, 1800, 925, BORDER, 1),
        text(120, 962, "Recall@5 = 정답 identity가 Top-5 후보 안에 포함되는 비율", 19, MUTED, 550),
        text(1800, 962, "단일 모델 대비 +26.05%p", 19, BLUE, 700, MONO, "end"),
        "</svg>",
    ]
    return "\n".join(out) + "\n"


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    claim = load_claim()
    svg = build(data, claim)
    for target in OUTPUTS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8")
    print(f"generated Claude-directed orchestration chart: {len(svg):,} bytes")


if __name__ == "__main__":
    main()

