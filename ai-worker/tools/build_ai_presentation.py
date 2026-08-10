#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

# --- How to run ---
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly (no venv, no pip install needed):
#      uv run build_ai_presentation.py
# 3. Or make executable and run:
#      chmod +x build_ai_presentation.py && ./build_ai_presentation.py
# --------------------------------
# The generated SVG/notebook strings intentionally keep some long presentation
# lines together so the artifacts remain easy to search and copy.
# ruff: noqa: E501, RUF001

from __future__ import annotations

import hashlib
import html
import json
import math
from pathlib import Path
from typing import TypeAlias

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"
OUTPUT = ROOT / "output" / "ai-presentation"
CLAUDE_ORCHESTRATION_ASSET = ROOT / "tools" / "assets" / "claude_model_orchestration.svg"

# ---------------------------------------------------------------------------
# Evidence loading. Every number below comes from a stored experiment file.
# ---------------------------------------------------------------------------


def read_json(path: Path) -> dict[str, JsonValue]:
    """Read a JSON object from a repository evidence file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return raw


def as_map(value: JsonValue) -> dict[str, JsonValue]:
    """Narrow a JSON value to an object."""
    if not isinstance(value, dict):
        raise TypeError("Expected JSON object")
    return value


def as_list(value: JsonValue) -> list[JsonValue]:
    """Narrow a JSON value to an array."""
    if not isinstance(value, list):
        raise TypeError("Expected JSON array")
    return value


def text(value: JsonValue, default: str = "") -> str:
    """Return a string JSON value or a presentation-safe default."""
    return value if isinstance(value, str) else default


def number(value: JsonValue, default: float = 0.0) -> float:
    """Return a numeric JSON value as float."""
    return (
        float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default
    )


def percent(value: float, digits: int = 1) -> str:
    """Format a proportion as a percentage string with an explicit unit."""
    return f"{value * 100:.{digits}f}%"


def sha256(path: Path) -> str:
    """Hash an evidence file for provenance."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def short_name(name: str) -> str:
    """Create a compact chart label while retaining model identity."""
    replacements = {
        "CLIP ViT-B/32 mean (strict)": "CLIP B/32",
        "CLIP ViT-L/14 mean (strict)": "CLIP L/14",
        "DINOv2 mean (strict)": "DINOv2",
        "SigLIP2 top-3 mean (strict)": "SigLIP2",
        "OSNet mean (strict)": "OSNet",
        "FastReID SBS top-3 mean + hflip (strict)": "FastReID SBS + TTA",
        "SOLIDER top-3 mean + hflip (strict)": "SOLIDER top-3 + TTA",
        "SOLIDER mean + hflip (strict)": "SOLIDER mean + TTA",
        "SOLIDER max + hflip (strict)": "SOLIDER max + TTA",
        "SOLIDER top-3 mean (strict)": "SOLIDER top-3",
    }
    return replacements.get(name, name)


def build_snapshot() -> dict[str, JsonValue]:
    """Collect the saved experiment evidence without inventing metrics."""
    cctv_path = RESULTS / "cctv_generalization_method_matrix_20260728.json"
    sonnet_path = RESULTS / "solider_ft_sonnet_comparison_20260724.json"
    zone_path = RESULTS / "zone_region_model_comparison_20260802.json"
    cctv = read_json(cctv_path)
    sonnet = read_json(sonnet_path)
    zone = read_json(zone_path)

    dataset = as_map(cctv["dataset"])
    decision = as_map(cctv["decision"])
    strict_methods: list[dict[str, JsonValue]] = []
    for raw in as_list(cctv["methods"]):
        method = as_map(raw)
        if text(method.get("protocol")) != "strict-cross-camera-sequence":
            continue
        name = text(method.get("name"))
        strict_methods.append(
            {
                "name": name,
                "short_name": short_name(name),
                "family": text(method.get("family"), "other"),
                "rank1": number(method.get("rank1")),
                "recall_at_5": number(method.get("recallAt5")),
                "identity_mrr": number(method.get("identityMrr")),
                "rank1_ci_low": number(method.get("rank1Ci95Low")),
                "rank1_ci_high": number(method.get("rank1Ci95High")),
                "parameter_millions": number(method.get("parameterMillionsApprox")),
            }
        )

    sonnet_ablation = as_map(as_map(sonnet["arms"])["same_run_sonnet_ablation"])
    pa_test = as_map(sonnet_ablation["pa100k_test"])
    cctv_test = as_map(sonnet_ablation["cctv_proxy_group_heldout"])
    standalone = as_map(as_map(sonnet["arms"])["standalone_full_finetune"])

    zone_routes: list[dict[str, JsonValue]] = []
    route_results = as_map(zone["selectionValidationResults"])
    for route, raw_models in route_results.items():
        models = as_map(raw_models)
        candidates: list[tuple[str, dict[str, JsonValue]]] = []
        for model, raw_metrics in models.items():
            candidates.append((model, as_map(raw_metrics)))
        selected_model, selected_metrics = max(
            candidates,
            key=lambda item: (
                number(item[1].get("wilson95_lower")),
                number(item[1].get("accuracy")),
                -number(item[1].get("inferenceMillisecondsPerSample"), 999999.0),
            ),
        )
        zone_routes.append(
            {
                "route": route,
                "best_model": selected_model,
                "accuracy": number(selected_metrics.get("accuracy")),
                "wilson95_lower": number(selected_metrics.get("wilson95_lower")),
                "total": number(selected_metrics.get("total")),
            }
        )

    selected = as_map(zone["selected"])
    selected_validation = as_map(selected["selectionValidationMetrics"])
    selected_sealed = as_map(selected["sealedMetrics"])

    baseline_row = min(strict_methods, key=lambda row: number(row["rank1"]))
    best_rank1 = max(number(row["rank1"]) for row in strict_methods)
    best_rows = [row for row in strict_methods if number(row["rank1"]) == best_rank1]
    best_row = max(best_rows, key=lambda row: number(row["identity_mrr"]))

    return {
        "generated_from": "saved repository evidence; no synthetic values added",
        "headline": {
            "selected_orchestration": "hybrid-solider-clip-v1",
            "role": "Top-K 후보 검색 및 증거 반환 (자동 신원확정 아님)",
            "baseline_name": text(baseline_row["short_name"]),
            "baseline_rank1": number(baseline_row["rank1"]),
            "best_name": text(best_row["short_name"]),
            "best_rank1": best_rank1,
            "best_tie_names": [text(row["short_name"]) for row in best_rows],
            "best_recall_at_5": number(best_row["recall_at_5"]),
            "best_identity_mrr": number(best_row["identity_mrr"]),
            "rank1_delta_points": (best_rank1 - number(baseline_row["rank1"])) * 100.0,
            "rank1_ratio": best_rank1 / max(number(baseline_row["rank1"]), 1e-9),
        },
        "identity_evidence": {
            "dataset": text(dataset.get("name")),
            "identity_count": number(dataset.get("identityCount")),
            "strict_query_count": number(
                dataset.get("chirlaStrictCrossCameraSequenceEligibleQueries")
            ),
            "project_video_count": number(dataset.get("projectSourceVideoCount")),
            "project_multi_person_video_count": number(dataset.get("projectMultiPersonVideoCount")),
            "project_person_crops": number(dataset.get("projectExtractedPersonCrops")),
            "project_reviewed_tracks": number(dataset.get("projectReviewedIdentityTracks")),
            "project_same_camera_rank1": number(dataset.get("projectTrackHeldoutClipL14Rank1")),
            "project_same_camera_scope": text(dataset.get("projectTrackHeldoutScope")),
            "strict_methods": strict_methods,
            "strict_best_rank1": number(decision.get("bestStrictRank1")),
            "strict_best_recall_at_5": number(decision.get("bestStrictRecallAt5")),
            "strict_best_mrr": number(decision.get("bestStrictIdentityMrr")),
            "strict_best_method": text(decision.get("bestStrictMethod")),
            "overlap_best_rank1": number(decision.get("legacyOverlappingGalleryQueryBestRank1")),
            "promotion_eligible": bool(decision.get("deployForAutomaticIdentityMatch")),
        },
        "attribute_evidence": {
            "pa100k_train": number(as_map(sonnet["inputs"]).get("pa100k", {}).get("train_rows")),
            "pa100k_validation": number(
                as_map(sonnet["inputs"]).get("pa100k", {}).get("validation_rows")
            ),
            "pa100k_test": number(as_map(sonnet["inputs"]).get("pa100k", {}).get("test_rows")),
            "solider_ft_mA": number(standalone.get("test_mA")),
            "solider_ft_instance_accuracy": number(standalone.get("test_instance_accuracy")),
            "solider_ft_instance_f1": number(standalone.get("test_instance_f1")),
            "solider_ft_label_macro_f1": number(standalone.get("test_label_macro_f1")),
            "sonnet_pa100k_baseline": number(pa_test.get("baseline_masked_attribute_accuracy")),
            "sonnet_pa100k": number(pa_test.get("sonnet_masked_attribute_accuracy")),
            "sonnet_pa100k_delta": number(pa_test.get("delta")),
            "sonnet_cctv_baseline": number(
                cctv_test.get("baseline_mean_masked_attribute_accuracy")
            ),
            "sonnet_cctv": number(cctv_test.get("sonnet_mean_masked_attribute_accuracy")),
            "sonnet_cctv_delta": number(cctv_test.get("delta")),
        },
        "zone_evidence": {
            "route_results": zone_routes,
            "selected_model": text(selected.get("model")),
            "selected_route": text(selected.get("route")),
            "selection_validation_accuracy": number(selected_validation.get("accuracy")),
            "selection_validation_wilson95_lower": number(
                selected_validation.get("wilson95_lower")
            ),
            "sealed_accuracy": number(selected_sealed.get("accuracy")),
            "sealed_wilson95_lower": number(selected_sealed.get("wilson95_lower")),
            "promotion_accepted": bool(as_map(zone["promotionDecision"]).get("accepted")),
            "scope_project_cctv": bool(as_map(zone["scope"]).get("projectCctvEvidence")),
            "scope_integrated": bool(as_map(zone["scope"]).get("backendContractIntegrated")),
        },
        "provenance": {
            "cctv_matrix": str(cctv_path.relative_to(ROOT)),
            "cctv_matrix_sha256": sha256(cctv_path),
            "sonnet_comparison": str(sonnet_path.relative_to(ROOT)),
            "sonnet_comparison_sha256": sha256(sonnet_path),
            "zone_comparison": str(zone_path.relative_to(ROOT)),
            "zone_comparison_sha256": sha256(zone_path),
            "cctv_evaluated_at": text(cctv.get("evaluatedAt")),
            "sonnet_generated_at": text(sonnet.get("generated_at")),
        },
    }


# ---------------------------------------------------------------------------
# Presentation design tokens. One palette and one type scale for every asset.
# ---------------------------------------------------------------------------

FONT = "Pretendard, 'Malgun Gothic', 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif"

INK = "#0F172A"
BODY = "#334155"
MUTED = "#64748B"
FAINT = "#94A3B8"
HAIRLINE = "#E2E8F0"
GRID = "#EFF2F7"
SURFACE = "#F8FAFC"
WHITE = "#FFFFFF"

VIOLET, VIOLET_SOFT, VIOLET_EDGE = "#6D28D9", "#F6F2FF", "#C7B4FA"
BLUE, BLUE_SOFT, BLUE_EDGE = "#1D4ED8", "#EFF5FF", "#A8C6FA"
GREEN, GREEN_SOFT, GREEN_EDGE = "#047857", "#ECFDF4", "#8ED9BD"
GOLD, GOLD_SOFT, GOLD_EDGE = "#B45309", "#FFF8EC", "#F1C480"
SLATE, SLATE_SOFT, SLATE_EDGE = "#475569", "#F1F5F9", "#CBD5E1"
RED, RED_SOFT, RED_EDGE = "#B42318", "#FEF3F2", "#F2B8B2"

CANVAS_W = 1360
PAD = 56

FAMILY_COLOR = {
    "frozen_embedding_strict": BLUE,
    "frozen_reid_strict": SLATE,
    "frozen_reid_tta_strict": GOLD,
    "solider_reid_tta_strict": VIOLET,
    "solider_reid_strict": VIOLET,
}
FAMILY_LABEL = [
    (BLUE, "범용 임베딩 (CLIP · DINOv2 · SigLIP2)"),
    (SLATE, "경량 ReID (OSNet)"),
    (GOLD, "ReID + TTA (FastReID SBS)"),
    (VIOLET, "SOLIDER ReID — 현재 선택 계열"),
]

ARROW_COLORS = {
    "slate": SLATE,
    "violet": VIOLET,
    "gold": GOLD,
    "green": GREEN,
    "blue": BLUE,
    "faint": FAINT,
}


def esc(value: str) -> str:
    """Escape text for SVG/XML."""
    return html.escape(value, quote=True)


def text_width(value: str, size: float) -> float:
    """Approximate rendered width so pills and legends never clip their label."""
    width = 0.0
    for char in value:
        if ord(char) > 0x2E7F:
            width += 1.0
        elif char.isdigit() or char.isupper():
            width += 0.60
        elif char in " .,:;·/|()%-":
            width += 0.34
        else:
            width += 0.55
    return width * size


def tx(
    x: float,
    y: float,
    value: str,
    size: float = 13,
    fill: str = BODY,
    anchor: str = "start",
    weight: str = "400",
    opacity: float = 1.0,
) -> str:
    """Draw one line of text."""
    fade = "" if opacity >= 1.0 else f' opacity="{opacity:.2f}"'
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}px" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{fade}>{esc(value)}</text>'
    )


def tx_rotated(
    x: float, y: float, value: str, size: float = 13, fill: str = BODY, weight: str = "400"
) -> str:
    """Draw a centered vertical label without clipping its left edge."""
    return (
        f'<text transform="translate({x:.1f} {y:.1f}) rotate(-90)" font-family="{FONT}" '
        f'font-size="{size}px" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="middle">{esc(value)}</text>'
    )


def line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    stroke: str = HAIRLINE,
    width: float = 1.0,
    dash: str = "",
    cap: str = "butt",
) -> str:
    """Draw a straight rule."""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
        f'stroke-width="{width}" stroke-linecap="{cap}"{dash_attr}/>'
    )


def rect(
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    stroke: str = "none",
    radius: float = 0.0,
    opacity: float = 1.0,
    stroke_width: float = 1.0,
    dash: str = "",
    shadow: bool = False,
) -> str:
    """Draw a rounded rectangle used for cards, chips, and bars."""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    shadow_attr = ' filter="url(#cardShadow)"' if shadow else ""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius:.1f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" '
        f'opacity="{opacity:.3f}"{dash_attr}{shadow_attr}/>'
    )


def circle(
    x: float,
    y: float,
    radius: float,
    fill: str,
    stroke: str = WHITE,
    stroke_width: float = 2.0,
    opacity: float = 1.0,
) -> str:
    """Draw a bubble or a node marker."""
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{stroke_width}" opacity="{opacity:.3f}"/>'
    )


def arrow(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    tone: str = "slate",
    width: float = 2.0,
    dash: str = "",
) -> str:
    """Draw a straight connector that ends in an arrow head."""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{ARROW_COLORS[tone]}" stroke-width="{width}" stroke-linecap="round"'
        f'{dash_attr} marker-end="url(#arrow-{tone})"/>'
    )


def elbow(
    points: list[tuple[float, float]], tone: str = "slate", width: float = 2.0, dash: str = ""
) -> str:
    """Draw an orthogonal routed connector with rounded corners."""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    path = " ".join(
        f"{'M' if index == 0 else 'L'}{x:.1f},{y:.1f}" for index, (x, y) in enumerate(points)
    )
    return (
        f'<path d="{path}" fill="none" stroke="{ARROW_COLORS[tone]}" stroke-width="{width}" '
        f'stroke-linejoin="round" stroke-linecap="round"{dash_attr} '
        f'marker-end="url(#arrow-{tone})"/>'
    )


def s_curve(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    tone: str = "slate",
    width: float = 2.0,
    dash: str = "",
) -> str:
    """Draw a vertical fan-out/merge curve between two lanes."""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    mid = (y1 + y2) / 2
    return (
        f'<path d="M{x1:.1f},{y1:.1f} C{x1:.1f},{mid:.1f} {x2:.1f},{mid:.1f} {x2:.1f},{y2:.1f}" '
        f'fill="none" stroke="{ARROW_COLORS[tone]}" stroke-width="{width}" stroke-linecap="round"'
        f'{dash_attr} marker-end="url(#arrow-{tone})"/>'
    )


def pill(
    x: float,
    y: float,
    label: str,
    fill: str,
    text_fill: str,
    size: float = 11.5,
    height: float = 24,
    padding: float = 13,
    anchor: str = "start",
    weight: str = "700",
    stroke: str = "none",
) -> str:
    """Draw an auto-width rounded label chip."""
    width = text_width(label, size) + padding * 2
    left = x if anchor == "start" else (x - width if anchor == "end" else x - width / 2)
    return rect(left, y, width, height, fill, stroke, height / 2) + tx(
        left + width / 2, y + height / 2 + size * 0.36, label, size, text_fill, "middle", weight
    )


def pill_width(label: str, size: float = 11.5, padding: float = 13) -> float:
    """Return the width a `pill` will occupy so callers can flow chips in a row."""
    return text_width(label, size) + padding * 2


def card(
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str = WHITE,
    stroke: str = HAIRLINE,
    radius: float = 14,
    dash: str = "",
    stroke_width: float = 1.4,
    shadow: bool = True,
) -> str:
    """Draw the standard presentation card surface."""
    return rect(x, y, w, h, fill, stroke, radius, 1.0, stroke_width, dash, shadow)


def section_label(x: float, y: float, label: str, accent: str = SLATE) -> str:
    """Draw a small accent rule plus an uppercase-style section caption."""
    return rect(x, y - 9, 26, 3, accent, radius=1.5) + tx(
        x + 36, y, label, 12, MUTED, "start", "700"
    )


def legend_row(
    x: float, y: float, items: list[tuple[str, str, str]], size: float = 12, gap: float = 30
) -> str:
    """Draw one horizontal legend line. Items are (kind, color, label)."""
    parts: list[str] = []
    cursor = x
    for kind, color, label in items:
        if kind == "swatch":
            parts.append(rect(cursor, y - 9, 13, 13, color, radius=3.5))
            cursor += 20
        elif kind == "bubble":
            parts.append(circle(cursor + 6, y - 3, 6.5, color, WHITE, 1.5))
            cursor += 20
        elif kind == "dash":
            parts.append(line(cursor, y - 3, cursor + 26, y - 3, color, 2.4, "6 5", "round"))
            cursor += 33
        else:
            parts.append(line(cursor, y - 3, cursor + 26, y - 3, color, 2.4, "", "round"))
            cursor += 33
        parts.append(tx(cursor, y, label, size, BODY))
        cursor += text_width(label, size) + gap
    return "".join(parts)


def kpi_card(
    x: float,
    y: float,
    w: float,
    h: float,
    caption: str,
    value: str,
    note: str,
    accent: str,
    accent_soft: str,
    accent_edge: str,
) -> str:
    """Draw a headline metric tile with an explicit unit and scope note."""
    return "".join(
        [
            card(x, y, w, h, accent_soft, accent_edge, 16),
            rect(x + 22, y + 24, 30, 4, accent, radius=2),
            tx(x + 22, y + 52, caption, 12.5, MUTED, "start", "700"),
            tx(x + 22, y + 92, value, 33, accent, "start", "800"),
            tx(x + 22, y + h - 20, note, 11.5, MUTED),
        ]
    )


def defs_block() -> str:
    """Shared markers, gradients, and the card shadow filter."""
    markers = "".join(
        f'<marker id="arrow-{name}" markerWidth="9" markerHeight="9" refX="7.4" refY="3" '
        f'orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L8,3 z" fill="{color}"/></marker>'
        for name, color in ARROW_COLORS.items()
    )
    return (
        "<defs>" + markers + '<linearGradient id="headerAccent" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{VIOLET}"/><stop offset="55%" stop-color="{BLUE}"/>'
        f'<stop offset="100%" stop-color="{GREEN}"/></linearGradient>'
        '<linearGradient id="fusionFill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#FBF8FF"/><stop offset="100%" stop-color="{VIOLET_SOFT}"/>'
        "</linearGradient>"
        '<filter id="cardShadow" x="-12%" y="-12%" width="124%" height="130%">'
        '<feDropShadow dx="0" dy="2" stdDeviation="3.2" flood-color="#0F172A" flood-opacity="0.07"/>'
        "</filter>"
        "</defs>"
    )


def write_svg(
    path: Path,
    title: str,
    subtitle: str,
    body: str,
    height: int,
    badge: str = "",
    badge_tone: tuple[str, str, str] = (VIOLET, VIOLET_SOFT, VIOLET_EDGE),
    eyebrow: str = "EYES:ON U · AI Worker 발표 부록",
    footer: tuple[str, ...] = (),
    width: int = CANVAS_W,
) -> None:
    """Render one presentation card: header band, body, and a source footer."""
    header = [
        rect(0, 0, width, height, WHITE),
        rect(0, 0, width, 7, "url(#headerAccent)"),
        tx(PAD, 46, eyebrow, 12, FAINT, "start", "700"),
        tx(PAD, 84, title, 29, INK, "start", "800"),
        tx(PAD, 114, subtitle, 14.5, MUTED),
        line(PAD, 136, width - PAD, 136, HAIRLINE, 1.2),
    ]
    if badge:
        accent, soft, edge = badge_tone
        header.append(pill(width - PAD, 58, badge, soft, accent, 13, 34, 18, "end", "700", edge))
    footer_parts: list[str] = []
    if footer:
        footer_parts.append(line(PAD, height - 78, width - PAD, height - 78, HAIRLINE, 1.2))
        for index, note in enumerate(footer[:2]):
            footer_parts.append(tx(PAD, height - 50 + index * 22, note, 12, MUTED))
    content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img">'
        ),
        defs_block(),
        "".join(header),
        body,
        "".join(footer_parts),
        "</svg>",
    ]
    path.write_text("\n".join(content), encoding="utf-8")


def strict_rows(data: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    """Return the strict-protocol comparison rows."""
    return [as_map(row) for row in as_list(as_map(data["identity_evidence"])["strict_methods"])]


def headline(data: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Return the derived headline block."""
    return as_map(data["headline"])


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def headline_chart(data: dict[str, JsonValue]) -> str:
    """Lead slide: what was selected, how good it is, and what it does not claim."""
    head = headline(data)
    identity = as_map(data["identity_evidence"])
    baseline_rank1 = number(head["baseline_rank1"])
    best_rank1 = number(head["best_rank1"])
    delta = number(head["rank1_delta_points"])
    ratio = number(head["rank1_ratio"])
    queries = int(number(identity["strict_query_count"]))

    body: list[str] = [section_label(PAD, 176, "현재 결론", VIOLET)]

    # Selection statement.
    body += [
        card(PAD, 194, 700, 122, VIOLET_SOFT, VIOLET_EDGE, 18),
        tx(PAD + 26, 228, "현재 검증된 최적 후보 검색 오케스트레이션", 13, MUTED, "start", "700"),
        tx(PAD + 26, 268, "hybrid-solider-clip-v1", 32, VIOLET, "start", "800"),
        tx(
            PAD + 26,
            296,
            "SOLIDER-ReID 중심 + CLIP ViT-L/14 보조 · Top-K 후보와 증거를 관리자에게 반환",
            12.5,
            BODY,
        ),
    ]

    # Before / after bars.
    bar_x, bar_w = PAD + 236, 460
    body += [
        section_label(PAD, 366, "동일 strict 평가에서의 개선폭", GOLD),
        tx(PAD + 220, 404, "1위 정답률 (Rank-1, %)", 11.5, FAINT, "end", "600"),
    ]
    for index, (label, value, color, soft, note) in enumerate(
        [
            ("초기 baseline · CLIP B/32", baseline_rank1, SLATE, SLATE_SOFT, "2026-05 비교 시작점"),
            (
                "현재 공동 최고 · SOLIDER top-3",
                best_rank1,
                VIOLET,
                VIOLET_SOFT,
                "현재 운영 선택 계열",
            ),
        ]
    ):
        y = 424 + index * 74
        width = bar_w * value / 0.60
        body += [
            tx(PAD + 220, y + 18, label, 12.5, BODY, "end", "700"),
            tx(PAD + 220, y + 38, note, 11, FAINT, "end"),
            rect(bar_x, y, bar_w, 34, soft, radius=8),
            rect(bar_x, y, width, 34, color, radius=8),
            tx(bar_x + width + 14, y + 24, percent(value, 2), 17, color, "start", "800"),
        ]
    body += [
        line(
            bar_x + bar_w * baseline_rank1 / 0.60,
            458,
            bar_x + bar_w * baseline_rank1 / 0.60,
            498,
            GOLD,
            1.6,
            "5 4",
        ),
        line(
            bar_x + bar_w * best_rank1 / 0.60,
            458,
            bar_x + bar_w * best_rank1 / 0.60,
            498,
            GOLD,
            1.6,
            "5 4",
        ),
        arrow(
            bar_x + bar_w * baseline_rank1 / 0.60,
            498,
            bar_x + bar_w * best_rank1 / 0.60 - 4,
            498,
            "gold",
            2.2,
        ),
        pill(
            (bar_x + bar_w * (baseline_rank1 + best_rank1) / 2 / 0.60),
            508,
            f"＋{delta:.2f}%p · 약 {ratio:.1f}배",
            GOLD_SOFT,
            GOLD,
            13,
            30,
            16,
            "middle",
            "800",
            GOLD_EDGE,
        ),
    ]

    # KPI tiles.
    tile_x, tile_w, tile_gap = 800, 244, 16
    tiles = [
        (
            "Rank-1 · 1위 정답률",
            percent(best_rank1, 2),
            f"strict {queries}개 query",
            VIOLET,
            VIOLET_SOFT,
            VIOLET_EDGE,
        ),
        (
            "Recall@5 · 상위 5후보 포함률",
            percent(number(head["best_recall_at_5"]), 2),
            "후보 검색 실무 지표",
            BLUE,
            BLUE_SOFT,
            BLUE_EDGE,
        ),
        (
            "identity-MRR · 정답 순위 역수",
            percent(number(head["best_identity_mrr"]), 2),
            "정답이 1위에 가까울수록 높음",
            GREEN,
            GREEN_SOFT,
            GREEN_EDGE,
        ),
        (
            "개선폭 (%p · 배수)",
            f"＋{delta:.2f}%p",
            f"초기 baseline 대비 약 {ratio:.1f}배",
            GOLD,
            GOLD_SOFT,
            GOLD_EDGE,
        ),
    ]
    body.append(section_label(tile_x, 176, "핵심 지표 (CHIRLA strict 95개 query)", BLUE))
    for index, (caption, value, note, accent, soft, edge) in enumerate(tiles):
        column, row = index % 2, index // 2
        body.append(
            kpi_card(
                tile_x + column * (tile_w + tile_gap),
                194 + row * 152,
                tile_w,
                136,
                caption,
                value,
                note,
                accent,
                soft,
                edge,
            )
        )

    # Scope strip.
    scope_y = 566
    body += [
        card(PAD, scope_y, CANVAS_W - PAD * 2, 96, SURFACE, HAIRLINE, 16, shadow=False),
        line(PAD + 430, scope_y + 20, PAD + 430, scope_y + 76, HAIRLINE, 1.2),
        line(PAD + 860, scope_y + 20, PAD + 860, scope_y + 76, HAIRLINE, 1.2),
    ]
    columns = [
        (
            PAD + 26,
            "평가 범위",
            "CHIRLA strict cross-camera·sequence 분리",
            f"identity 11명 · query {queries}개 · 동일 protocol 비교",
            GREEN,
        ),
        (
            PAD + 456,
            "AI Worker 역할",
            "Top-K 후보와 증거(시간·bbox·crop) 반환",
            "최종 신원 판단은 관리자·중앙 시스템",
            BLUE,
        ),
        (
            PAD + 886,
            "이 수치가 말하지 않는 것",
            "모든 CCTV 자동 신원확정을 보장하지 않음",
            "자동확정 85% gate는 별도 sealed 평가",
            RED,
        ),
    ]
    for x, title_text, first, second, accent in columns:
        body += [
            circle(x + 6, scope_y + 27, 5, accent, WHITE, 0),
            tx(x + 20, scope_y + 32, title_text, 12.5, INK, "start", "700"),
            tx(x, scope_y + 58, first, 12, BODY),
            tx(x, scope_y + 78, second, 11.5, MUTED),
        ]
    return "".join(body)


def orchestration_chart(data: dict[str, JsonValue]) -> str:
    """Runtime orchestration: sequential gates, parallel branches, fusion, side paths."""
    head = headline(data)
    zone = as_map(data["zone_evidence"])
    body: list[str] = []

    # Encoding legend first so the reader knows how to parse the diagram.
    body.append(
        legend_row(
            PAD,
            168,
            [
                ("line", SLATE, "요청 시 실행 경로 (순서 있음)"),
                ("line", VIOLET, "결합(late fusion) 경계"),
                ("dash", GOLD, "별도 구역 routing · identity 점수와 합산 안 함"),
                ("dash", FAINT, "오프라인 경로 · 요청마다 실행 안 함"),
            ],
            12,
        )
    )

    # Stage 1 - sequential gates.
    body.append(
        pill(
            PAD,
            196,
            "①  순차 게이트 — 앞 단계를 통과해야 다음이 실행",
            SLATE_SOFT,
            SLATE,
            12,
            26,
            14,
            "start",
            "700",
            SLATE_EDGE,
        )
    )
    gates = [
        (
            PAD,
            360,
            BLUE,
            BLUE_SOFT,
            BLUE_EDGE,
            "요청 입력",
            "인상착의 문장 · 참조 사진 · 시간창",
            "필요한 녹화 segment만 내려받기",
        ),
        (
            500,
            340,
            SLATE,
            WHITE,
            SLATE_EDGE,
            "YOLO 사람 검출 게이트",
            "person class 0 · bbox 생성",
            "사람이 없으면 이후 단계 미실행",
        ),
        (
            924,
            380,
            SLATE,
            WHITE,
            SLATE_EDGE,
            "ByteTrack + 품질 게이트",
            "track 병합 · crop · frame offset",
            "저품질 crop은 증거에서 제외",
        ),
    ]
    for index, (x, w, accent, fill, edge, title_text, first, second) in enumerate(gates):
        body += [
            card(x, 232, w, 96, fill, edge, 14),
            circle(x + 26, 258, 12, accent, WHITE, 0),
            tx(x + 26, 262, str(index + 1), 12, WHITE, "middle", "800"),
            tx(x + 48, 262, title_text, 14.5, INK, "start", "700"),
            tx(x + 22, 288, first, 11.8, BODY),
            tx(x + 22, 308, second, 11.5, MUTED),
        ]
    body += [arrow(424, 280, 492, 280, "slate"), arrow(848, 280, 916, 280, "slate")]

    # Stage 2 - parallel evidence branches inside a dashed container.
    container_y, container_h = 384, 246
    body += [
        rect(
            PAD,
            container_y,
            CANVAS_W - PAD * 2,
            container_h,
            "#FCFDFF",
            BLUE_EDGE,
            18,
            1.0,
            1.6,
            "9 7",
        ),
        pill(
            PAD + 24,
            container_y - 13,
            "②  병렬 증거 branch — 동시 실행 · 사용 가능한 증거만 참여",
            WHITE,
            BLUE,
            12,
            26,
            14,
            "start",
            "700",
            BLUE_EDGE,
        ),
    ]
    branch_defs = [
        (
            BLUE,
            BLUE_SOFT,
            BLUE_EDGE,
            "CLIP ViT-L/14",
            "인상착의 문장 ↔ 사람 crop",
            "prompt contrast 검색",
            "text-image 유사도",
            "문장 있을 때",
        ),
        (
            VIOLET,
            VIOLET_SOFT,
            VIOLET_EDGE,
            "SOLIDER ReID",
            "참조 사진 ↔ 사람 crop",
            "case/reference anchor",
            "reference 유사도 (주 신호)",
            "참조 사진 있을 때",
        ),
        (
            GREEN,
            GREEN_SOFT,
            GREEN_EDGE,
            "속성 evidence",
            "ROI color · SOLIDER-PAR",
            "상·하의 색상, 소지품 속성",
            "속성 일치 신호",
            "속성 모델 준비 시",
        ),
        (
            GOLD,
            GOLD_SOFT,
            GOLD_EDGE,
            "이력 · 조건부 검토",
            "historical retrieval",
            "Qwen top-K review",
            "과거 gallery · 저신뢰 설명",
            "조건부 실행",
        ),
    ]
    branch_w, branch_h, branch_y = 284, 176, 416
    branch_x = [76, 384, 692, 1000]
    bus_y = 366
    body += [
        line(210, bus_y, 1150, bus_y, SLATE, 2.4, "", "round"),
        circle(1114, bus_y, 4.5, SLATE, WHITE, 0),
        line(1114, 328, 1114, bus_y, SLATE, 2.4),
    ]
    for x, (accent, soft, edge, title_text, first, second, signal, availability) in zip(
        branch_x, branch_defs, strict=True
    ):
        body += [
            arrow(x + branch_w / 2, bus_y + 6, x + branch_w / 2, branch_y - 6, "slate", 2.0),
            card(x, branch_y, branch_w, branch_h, WHITE, edge, 14),
            rect(x, branch_y, branch_w, 5, accent, radius=2.5),
            tx(x + 20, branch_y + 40, title_text, 15, accent, "start", "800"),
            tx(x + 20, branch_y + 64, first, 11.8, BODY),
            tx(x + 20, branch_y + 83, second, 11.8, BODY),
            line(x + 20, branch_y + 100, x + branch_w - 20, branch_y + 100, HAIRLINE, 1.2),
            tx(x + 20, branch_y + 120, "반환 신호", 10.5, FAINT, "start", "700"),
            tx(x + 20, branch_y + 139, signal, 12, INK, "start", "600"),
            pill(
                x + 20, branch_y + 148, availability, soft, accent, 11, 22, 11, "start", "700", edge
            ),
        ]

    # Stage 3 - late fusion boundary.
    fusion_y, fusion_h = 690, 116
    for x in branch_x:
        body.append(
            s_curve(x + branch_w / 2, branch_y + branch_h + 4, 680, fusion_y - 8, "violet", 1.8)
        )
    body += [
        rect(180, fusion_y, 1000, fusion_h, "url(#fusionFill)", VIOLET, 18, 1.0, 2.0),
        pill(
            204,
            fusion_y - 13,
            "③  availability-aware late fusion — 규칙 기반 결합 (학습 없음)",
            WHITE,
            VIOLET,
            12,
            26,
            14,
            "start",
            "700",
            VIOLET_EDGE,
        ),
    ]
    fusion_cells = [
        ("핵심 점수", "0.75 × SOLIDER + 0.25 × CLIP", "두 증거가 모두 있을 때"),
        ("track 집계", "상위 3 frame 평균", "frame 단위 잡음 완화"),
        ("보정 신호", "temporal · spatial · quality", "시간·위치·품질 가중"),
        ("안전 규칙", "필수 증거 누락 → fail closed", "추측으로 후보를 만들지 않음"),
    ]
    for index, (label, main, note) in enumerate(fusion_cells):
        cx = 180 + 125 + index * 250
        if index:
            body.append(
                line(
                    180 + index * 250,
                    fusion_y + 22,
                    180 + index * 250,
                    fusion_y + fusion_h - 22,
                    VIOLET_EDGE,
                    1.2,
                )
            )
        body += [
            tx(cx, fusion_y + 34, label, 10.8, FAINT, "middle", "700"),
            tx(cx, fusion_y + 60, main, 13, INK, "middle", "800"),
            tx(cx, fusion_y + 84, note, 11.2, MUTED, "middle"),
        ]

    # Stage 4 - returned candidate evidence.
    output_y = 846
    body.append(arrow(680, fusion_y + fusion_h + 2, 680, output_y - 8, "violet", 2.4))
    body += [
        card(400, output_y, 560, 120, GREEN_SOFT, GREEN_EDGE, 16),
        tx(
            680,
            output_y + 34,
            "④  Top-K 후보 결과 — 관리자 검토용 증거",
            15,
            GREEN,
            "middle",
            "800",
        ),
        tx(
            680,
            output_y + 56,
            "AI가 신원을 확정하지 않고, 확인 가능한 근거를 좁혀서 넘긴다",
            11.5,
            MUTED,
            "middle",
        ),
    ]
    chips = ["score", "frame", "bbox", "crop", "operator_review"]
    chip_widths = [pill_width(chip, 11, 11) for chip in chips]
    cursor = 680 - (sum(chip_widths) + 8 * (len(chips) - 1)) / 2
    for chip, width in zip(chips, chip_widths, strict=True):
        body.append(
            pill(cursor, output_y + 74, chip, WHITE, GREEN, 11, 24, 11, "start", "700", GREEN_EDGE)
        )
        cursor += width + 8

    # Separate zone routing path.
    zone_x, zone_w = PAD, 300
    body += [
        elbow(
            [(86, 328), (36, 352), (36, output_y + 60), (zone_x - 4, output_y + 60)],
            "gold",
            1.8,
            "7 6",
        ),
        card(zone_x, output_y - 6, zone_w, 132, GOLD_SOFT, GOLD_EDGE, 16, "6 5"),
        tx(zone_x + 20, output_y + 22, "⑤  별도 경로 · 구역 routing", 13.5, GOLD, "start", "800"),
        tx(
            zone_x + 20,
            output_y + 46,
            f"{text(zone['selected_route'])} + {text(zone['selected_model'])}",
            11.8,
            BODY,
        ),
        tx(
            zone_x + 20,
            output_y + 66,
            f"synthetic proxy 선택검증 {percent(number(zone['selection_validation_accuracy']), 2)}",
            11.8,
            BODY,
        ),
        tx(
            zone_x + 20, output_y + 86, "→ 다음 카메라·구역 우선순위 (관리자 · Jetson)", 11.5, MUTED
        ),
        tx(zone_x + 20, output_y + 110, "identity 점수와 합산하지 않음", 11.5, RED, "start", "700"),
    ]

    # Current selection callout.
    sel_x, sel_w = 1004, 300
    body += [
        card(sel_x, output_y - 6, sel_w, 132, VIOLET_SOFT, VIOLET_EDGE, 16),
        tx(sel_x + 20, output_y + 22, "현재 선택", 12, MUTED, "start", "700"),
        tx(sel_x + 20, output_y + 50, "hybrid-solider-clip-v1", 17, VIOLET, "start", "800"),
        tx(
            sel_x + 20,
            output_y + 74,
            f"CHIRLA strict Rank-1 {percent(number(head['best_rank1']), 2)} · Recall@5 {percent(number(head['best_recall_at_5']), 2)}",
            11.5,
            BODY,
        ),
        tx(
            sel_x + 20,
            output_y + 94,
            f"초기 baseline 대비 ＋{number(head['rank1_delta_points']):.2f}%p",
            11.5,
            BODY,
        ),
        tx(sel_x + 20, output_y + 114, "역할: 후보 검색 · 증거 반환", 11.5, MUTED),
    ]

    # Offline teacher / label layer.
    offline_y = 1004
    body += [
        rect(PAD, offline_y, CANVAS_W - PAD * 2, 86, SURFACE, SLATE_EDGE, 16, 1.0, 1.4, "8 6"),
        tx(
            PAD + 24, offline_y + 32, "⑥  오프라인 teacher · 라벨 계층", 13.5, SLATE, "start", "800"
        ),
        pill(
            PAD + 250,
            offline_y + 16,
            "요청 경로 아님",
            WHITE,
            RED,
            11,
            24,
            12,
            "start",
            "700",
            RED_EDGE,
        ),
        tx(
            PAD + 24,
            offline_y + 62,
            "geometry/mask/속성 라벨 품질 개선용 · core retrieval 승격은 별도 검증 필요 · Sonnet 속성 proxy ＋0.31%p / CCTV proxy −1.54%p",
            11.5,
            MUTED,
        ),
    ]
    offline_chips = ["Grounding DINO", "SAM2.1", "Florence-2", "Sonnet"]
    cursor = CANVAS_W - PAD - 24
    for label in reversed(offline_chips):
        width = pill_width(label, 11.5, 13)
        cursor -= width
        body.append(
            pill(
                cursor,
                offline_y + 20,
                label,
                WHITE,
                SLATE,
                11.5,
                26,
                13,
                "start",
                "600",
                SLATE_EDGE,
            )
        )
        cursor -= 10
    body.append(
        elbow([(1318, offline_y + 20), (1318, 500), (CANVAS_W - PAD + 4, 500)], "faint", 1.6, "7 6")
    )
    body.append(tx_rotated(1336, 700, "오프라인 라벨 개선", 10.5, FAINT, "600"))
    return "".join(body)


def architecture_chart() -> str:
    """System view: request path, worker path, and the separate realtime path."""
    body: list[str] = []
    body.append(
        legend_row(
            PAD,
            168,
            [
                ("line", SLATE, "작업 요청 · 결과 callback"),
                ("line", BLUE, "저장소 입출력 (원본 · crop · frame)"),
                ("dash", GOLD, "Jetson 실시간 경로 (별도 운영)"),
            ],
            12,
        )
    )

    bands = [
        (196, 126, "요청 · 작업 관리", "신고 접수부터 작업 큐까지", SLATE),
        (348, 168, "AI 분석 (과거 녹화본)", "AI Worker가 구간을 분석해 증거를 만든다", VIOLET),
        (548, 148, "결과 소비 · 실시간 보조", "관리자 확인과 Jetson 실시간 경로", GOLD),
    ]
    for y, h, title_text, note, accent in bands:
        body += [
            rect(PAD, y, CANVAS_W - PAD * 2, h, SURFACE, HAIRLINE, 16, 1.0, 1.2),
            rect(PAD, y, 5, h, accent, radius=2.5),
            tx(PAD + 20, y + 26, title_text, 12.5, accent, "start", "800"),
            tx(PAD + 20 + text_width(title_text, 12.5) + 16, y + 26, note, 11.5, FAINT),
        ]

    nodes = [
        (
            96,
            232,
            250,
            74,
            BLUE,
            BLUE_SOFT,
            BLUE_EDGE,
            "신고자 프로필 입력",
            "인상착의 · 참조 사진 · 시간/카메라 조건",
        ),
        (
            416,
            232,
            250,
            74,
            SLATE,
            WHITE,
            SLATE_EDGE,
            "중앙 서버",
            "작업 등록 · DB · 결과 계약 관리",
        ),
        (736, 232, 210, 74, SLATE, WHITE, SLATE_EDGE, "RabbitMQ", "작업 큐 전달 · 재처리"),
        (1016, 232, 248, 74, SLATE, WHITE, SLATE_EDGE, "작업 상태 · 재시도", "실패 시 큐로 되돌림"),
        (96, 386, 560, 112, VIOLET, VIOLET_SOFT, VIOLET_EDGE, "AI Worker", ""),
        (736, 386, 528, 112, BLUE, BLUE_SOFT, BLUE_EDGE, "MinIO / S3 오브젝트 스토리지", ""),
        (
            96,
            582,
            380,
            92,
            GOLD,
            GOLD_SOFT,
            GOLD_EDGE,
            "Jetson Orin Nano",
            "현장 실시간 후보 · bbox·시간 전송",
        ),
        (
            536,
            582,
            380,
            92,
            SLATE,
            WHITE,
            SLATE_EDGE,
            "관리자 대시보드",
            "후보 검토 · 이동 경로 확인 · 승인",
        ),
        (976, 582, 288, 92, GREEN, GREEN_SOFT, GREEN_EDGE, "수사 판단", "최종 확인은 사람이 수행"),
    ]
    for x, y, w, h, accent, fill, edge, title_text, note in nodes:
        body += [
            card(x, y, w, h, fill, edge, 14),
            tx(x + 20, y + 30, title_text, 14.5, accent, "start", "800"),
        ]
        if note:
            body.append(tx(x + 20, y + 54, note, 11.8, BODY))

    worker_steps = ["구간 다운로드", "YOLO · ByteTrack", "SOLIDER · CLIP 결합", "Top-K 증거 생성"]
    cursor = 116
    for index, label in enumerate(worker_steps):
        width = pill_width(label, 11.5, 12)
        body.append(
            pill(cursor, 452, label, WHITE, VIOLET, 11.5, 26, 12, "start", "700", VIOLET_EDGE)
        )
        if index < len(worker_steps) - 1:
            body.append(tx(cursor + width + 5, 470, "›", 14, VIOLET_EDGE, "start", "800"))
        cursor += width + 16
    store_chips = ["원본 영상 구간", "person crop", "대표 frame", "결과 JSON"]
    cursor = 756
    for label in store_chips:
        width = pill_width(label, 11.5, 12)
        body.append(pill(cursor, 452, label, WHITE, BLUE, 11.5, 26, 12, "start", "700", BLUE_EDGE))
        cursor += width + 14

    body += [
        arrow(346, 269, 410, 269, "slate"),
        arrow(666, 269, 730, 269, "slate"),
        arrow(946, 269, 1010, 269, "slate"),
        elbow([(841, 306), (841, 344), (376, 344), (376, 380)], "slate", 2.0),
        tx(600, 338, "작업 배정: 큐 → Worker", 11.5, MUTED, "middle", "600"),
        arrow(656, 418, 730, 418, "blue"),
        tx(693, 408, "업로드", 10.5, MUTED, "middle"),
        arrow(730, 468, 656, 468, "blue"),
        tx(693, 486, "구간 읽기", 10.5, MUTED, "middle"),
        elbow([(376, 498), (376, 528), (541, 528), (541, 232 + 74 + 6)], "slate", 2.0),
        tx(560, 522, "결과 callback: 후보 · 경로 · 증거 링크", 11.5, MUTED, "start", "600"),
        elbow([(300, 498), (300, 552), (726, 552), (726, 578)], "slate", 2.0),
        tx(726, 546, "대시보드 표시", 11.5, MUTED, "middle", "600"),
        arrow(916, 628, 970, 628, "slate"),
        elbow([(286, 582), (286, 552), (286, 552)], "gold", 1.8, "7 6"),
        elbow([(476, 628), (506, 628), (530, 628)], "gold", 1.8, "7 6"),
        elbow([(190, 582), (190, 540), (40, 540), (40, 269), (90, 269)], "gold", 1.8, "7 6"),
        tx(
            120,
            534,
            "실시간 후보(bbox·시간) → 중앙 서버 / 관리자 승인 → Jetson 탐색 지시",
            11.5,
            GOLD,
            "start",
            "600",
        ),
    ]
    return "".join(body)


def ranked_chart(data: dict[str, JsonValue]) -> str:
    """Grouped comparison of Rank-1 and Recall@5 for every strict method."""
    rows = sorted(
        strict_rows(data),
        key=lambda row: (number(row["rank1"]), number(row["recall_at_5"])),
        reverse=True,
    )
    best_rank1 = max(number(row["rank1"]) for row in rows)
    x0, plot_w, y0, row_h = 322, 700, 246, 50
    plot_h = len(rows) * row_h
    body: list[str] = [
        legend_row(
            PAD,
            172,
            [
                ("swatch", VIOLET, "Rank-1 · 1위 정답률 (%)"),
                ("swatch", GOLD, "Recall@5 · 상위 5후보 포함률 (%)"),
                ("swatch", VIOLET_SOFT, "현재 선택 계열 (SOLIDER)"),
            ],
            12,
        ),
        tx(PAD, 210, "동일한 CHIRLA strict 95개 query · 두 지표 모두 높을수록 좋음", 12, FAINT),
        tx(1100, 210, "identity-MRR (%)", 11.5, FAINT, "start", "700"),
        rect(x0, y0, plot_w, plot_h, "#FCFDFE", HAIRLINE, 10, 1.0, 1.2),
    ]
    for tick in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        x = x0 + plot_w * tick
        body += [
            line(x, y0, x, y0 + plot_h, GRID if tick else HAIRLINE, 1.2),
            tx(x, y0 + plot_h + 26, f"{tick * 100:.0f}", 11.5, FAINT, "middle"),
        ]
    body.append(tx(x0 + plot_w / 2, y0 + plot_h + 50, "정답률 (%)", 12, MUTED, "middle", "700"))

    for index, row in enumerate(rows):
        y = y0 + index * row_h
        rank1, recall = number(row["rank1"]), number(row["recall_at_5"])
        selected = rank1 == best_rank1
        label = text(row["short_name"])
        color = FAMILY_COLOR.get(text(row["family"]), MUTED)
        if selected:
            body.append(rect(x0 - 300, y + 3, plot_w + 310, row_h - 6, VIOLET_SOFT, radius=8))
        body += [
            tx(
                x0 - 18,
                y + 22,
                label,
                12.5,
                INK if selected else BODY,
                "end",
                "700" if selected else "600",
            ),
            tx(
                x0 - 18,
                y + 39,
                f"{number(row['parameter_millions']):.0f}M 파라미터",
                10.5,
                FAINT,
                "end",
            ),
            rect(x0, y + 8, plot_w * rank1, 15, VIOLET, radius=4),
            rect(x0, y + 27, plot_w * recall, 15, GOLD, radius=4),
            tx(x0 + plot_w * rank1 + 9, y + 20, percent(rank1, 2), 11.5, VIOLET, "start", "800"),
            tx(x0 + plot_w * recall + 9, y + 39, percent(recall, 2), 11.5, GOLD, "start", "700"),
            tx(1100, y + 30, percent(number(row["identity_mrr"]), 2), 12.5, BODY, "start", "600"),
            circle(x0 - 292, y + row_h / 2, 4.5, color, WHITE, 0),
        ]
        if selected:
            body.append(
                pill(
                    CANVAS_W - PAD,
                    y + 12,
                    "현재 선택 · 공동 최고",
                    WHITE,
                    VIOLET,
                    11,
                    24,
                    12,
                    "end",
                    "800",
                    VIOLET_EDGE,
                )
            )
    return "".join(body)


def evolution_chart(data: dict[str, JsonValue]) -> str:
    """Measured improvement from the first baseline to the current joint best."""
    rows = sorted(strict_rows(data), key=lambda row: number(row["rank1"]))
    head = headline(data)
    x0, plot_w, y0, row_h = 322, 640, 250, 48
    plot_h = len(rows) * row_h
    best_rank1 = max(number(row["rank1"]) for row in rows)
    body: list[str] = [
        legend_row(
            PAD,
            172,
            [
                (kind, color, label)
                for (color, label), kind in zip(FAMILY_LABEL, ["swatch"] * 4, strict=True)
            ],
            12,
            24,
        ),
        tx(
            PAD,
            212,
            "같은 strict 평가만 낮은 성능 → 높은 성능 순으로 다시 정렬 · 값은 Rank-1(1위 정답률, %)",
            12,
            FAINT,
        ),
        rect(x0, y0, plot_w, plot_h, "#FCFDFE", HAIRLINE, 10, 1.0, 1.2),
    ]
    for tick in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
        x = x0 + plot_w * tick / 0.5
        body += [
            line(x, y0, x, y0 + plot_h, GRID if tick else HAIRLINE, 1.2),
            tx(x, y0 + plot_h + 26, f"{tick * 100:.0f}", 11.5, FAINT, "middle"),
        ]
    body.append(
        tx(x0 + plot_w / 2, y0 + plot_h + 50, "Rank-1 · 1위 정답률 (%)", 12, MUTED, "middle", "700")
    )

    first_y = last_y = 0.0
    for index, row in enumerate(rows):
        y = y0 + index * row_h
        rank1 = number(row["rank1"])
        color = FAMILY_COLOR.get(text(row["family"]), MUTED)
        selected = rank1 == best_rank1
        body += [
            tx(
                x0 - 18,
                y + 30,
                text(row["short_name"]),
                12.5,
                INK if selected else BODY,
                "end",
                "700" if selected else "600",
            ),
            rect(x0, y + 13, plot_w * rank1 / 0.5, 22, color, radius=5),
            tx(
                x0 + plot_w * rank1 / 0.5 + 10,
                y + 30,
                percent(rank1, 2),
                12.5,
                color,
                "start",
                "800",
            ),
        ]
        if index == 0:
            first_y = y + 24
            body.append(
                pill(
                    x0 + plot_w * rank1 / 0.5 + 82,
                    y + 12,
                    "초기 baseline",
                    SLATE_SOFT,
                    SLATE,
                    11,
                    24,
                    11,
                    "start",
                    "700",
                    SLATE_EDGE,
                )
            )
        if selected:
            last_y = y + 24
            body.append(
                pill(
                    x0 + plot_w * rank1 / 0.5 + 82,
                    y + 12,
                    "현재 공동 최고",
                    VIOLET_SOFT,
                    VIOLET,
                    11,
                    24,
                    11,
                    "start",
                    "800",
                    VIOLET_EDGE,
                )
            )

    bracket_x = 1108
    body += [
        elbow(
            [(bracket_x - 14, first_y), (bracket_x, first_y), (bracket_x, last_y + 14)], "gold", 2.0
        ),
        line(bracket_x, last_y + 14, bracket_x, last_y, GOLD, 2.0),
        card(bracket_x + 14, (first_y + last_y) / 2 - 54, 182, 108, GOLD_SOFT, GOLD_EDGE, 14),
        tx(bracket_x + 34, (first_y + last_y) / 2 - 26, "개선폭", 11.5, MUTED, "start", "700"),
        tx(
            bracket_x + 34,
            (first_y + last_y) / 2 + 4,
            f"＋{number(head['rank1_delta_points']):.2f}%p",
            22,
            GOLD,
            "start",
            "800",
        ),
        tx(
            bracket_x + 34,
            (first_y + last_y) / 2 + 28,
            f"약 {number(head['rank1_ratio']):.1f}배 (동일 95개 query)",
            11.5,
            BODY,
        ),
        tx(bracket_x + 34, (first_y + last_y) / 2 + 46, "%p = 백분율 포인트 차이", 10.5, FAINT),
    ]
    tie_names = " · ".join(text(name) for name in as_list(head["best_tie_names"]))
    body.append(
        tx(
            PAD,
            y0 + plot_h + 86,
            f"공동 최고 (동률): {tie_names} — 현재 운영은 SOLIDER 중심 + CLIP 보조 조합을 후보 검색·증거 반환에 사용",
            12.5,
            VIOLET,
            "start",
            "700",
        )
    )
    return "".join(body)


def bubble_chart(data: dict[str, JsonValue]) -> str:
    """Parameter scale versus strict Rank-1, sized by Recall@5."""
    rows = strict_rows(data)
    x0, y0, w, h = 128, 232, 900, 396
    body: list[str] = [
        tx(
            PAD,
            172,
            "가로축 = 모델 파라미터 수(M, 로그 축) · 세로축 = Rank-1(%) · 원 크기 = Recall@5(%)",
            12,
            FAINT,
        ),
        rect(x0, y0, w, h, "#FCFDFE", HAIRLINE, 10, 1.0, 1.2),
    ]
    for tick in (0.0, 0.15, 0.30, 0.45, 0.60):
        y = y0 + h - tick / 0.60 * h
        body += [
            line(x0, y, x0 + w, y, GRID if tick else HAIRLINE, 1.2),
            tx(x0 - 12, y + 4, f"{tick * 100:.0f}", 11.5, FAINT, "end"),
        ]
    for tick in (2, 5, 20, 50, 100, 200, 500):
        x = x0 + (math.log10(tick) - math.log10(2)) / (math.log10(500) - math.log10(2)) * w
        body += [
            line(x, y0, x, y0 + h, GRID, 1.2),
            tx(x, y0 + h + 26, str(tick), 11.5, FAINT, "middle"),
        ]
    body += [
        tx(x0 + w / 2, y0 + h + 52, "파라미터 수 (M, 로그 축)", 12.5, MUTED, "middle", "700"),
        tx_rotated(60, y0 + h / 2, "Rank-1 · 1위 정답률 (%)", 12.5, MUTED, "700"),
    ]

    recalls = [number(row["recall_at_5"]) for row in rows]
    min_r, max_r = min(recalls), max(recalls)
    best_rank1 = max(number(row["rank1"]) for row in rows)
    label_offsets = {
        # Claude CLI layout: split the dense SOLIDER cluster into left/right
        # columns so the selection pill and two-line metric labels stay clear.
        "SOLIDER top-3 + TTA": (-280, -70),
        "SOLIDER top-3": (120, -10),
        "SOLIDER max + TTA": (-280, -35),
        "SOLIDER mean + TTA": (-280, 10),
        "FastReID SBS + TTA": (-46, -40),
        "SigLIP2": (120, 24),
        "OSNet": (24, -22),
        "DINOv2": (24, -20),
        "CLIP L/14": (-28, 28),
        "CLIP B/32": (-30, 28),
    }
    markers: list[str] = []
    labels: list[str] = []
    for row in rows:
        params = max(number(row["parameter_millions"]), 2.0)
        rank1, recall = number(row["rank1"]), number(row["recall_at_5"])
        name = text(row["short_name"])
        x = x0 + (math.log10(params) - math.log10(2)) / (math.log10(500) - math.log10(2)) * w
        y = y0 + h - rank1 / 0.60 * h
        radius = 13 + (recall - min_r) / max(max_r - min_r, 1e-6) * 15
        color = FAMILY_COLOR.get(text(row["family"]), MUTED)
        if rank1 == best_rank1:
            markers.append(circle(x, y, radius + 7, "none", VIOLET, 2.0))
        markers.append(circle(x, y, radius, color, WHITE, 2.0, 0.92))
        dx, dy = label_offsets.get(name, (24, -20))
        anchor = "start" if dx >= 0 else "end"
        labels += [
            line(
                x + (radius if dx >= 0 else -radius),
                y,
                x + dx - (5 if dx >= 0 else -5),
                y + dy - 4,
                color,
                1.0,
                "3 3",
            ),
            tx(x + dx, y + dy, name, 11.5, INK, anchor, "700"),
            tx(
                x + dx,
                y + dy + 15,
                f"Rank-1 {percent(rank1, 1)} · R@5 {percent(recall, 1)}",
                10.2,
                MUTED,
                anchor,
            ),
        ]
    body += markers + labels

    legend_x = 1064
    body += [
        card(legend_x, y0, 240, 202, WHITE, HAIRLINE, 14),
        tx(legend_x + 20, y0 + 30, "모델 계열", 12, INK, "start", "800"),
    ]
    for index, (color, label) in enumerate(FAMILY_LABEL):
        body += [
            circle(legend_x + 27, y0 + 52 + index * 26, 6.5, color, WHITE, 0),
            tx(legend_x + 42, y0 + 56 + index * 26, label, 10.8, BODY),
        ]
    body += [
        line(legend_x + 20, y0 + 162, legend_x + 220, y0 + 162, HAIRLINE, 1.2),
        tx(legend_x + 20, y0 + 182, "원 크기 = Recall@5", 11.5, INK, "start", "700"),
    ]
    size_legend_y = y0 + 250
    body += [
        card(legend_x, y0 + 216, 240, 178, WHITE, HAIRLINE, 14),
        tx(legend_x + 20, y0 + 244, "원 크기 기준", 12, INK, "start", "800"),
    ]
    for index, sample in enumerate((min_r, (min_r + max_r) / 2, max_r)):
        radius = 13 + (sample - min_r) / max(max_r - min_r, 1e-6) * 15
        cy = size_legend_y + 40 + index * 42
        body += [
            circle(legend_x + 48, cy, radius, FAINT, WHITE, 1.5, 0.55),
            tx(legend_x + 92, cy + 5, f"Recall@5 {percent(sample, 1)}", 11, BODY),
        ]
    body.append(
        pill(
            x0 + w - 14,
            y0 + 16,
            "현재 선택 계열: SOLIDER · Rank-1 47.37%",
            WHITE,
            VIOLET,
            12,
            28,
            14,
            "end",
            "800",
            VIOLET_EDGE,
        )
    )
    return "".join(body)


def sonnet_chart(data: dict[str, JsonValue]) -> str:
    """Sonnet teacher ablation on two different proxies, with separate zoomed axes."""
    attr = as_map(data["attribute_evidence"])
    panels = [
        (
            PAD,
            "PA-100K masked 속성 정확도",
            "공개 속성 데이터셋 test split",
            number(attr["sonnet_pa100k_baseline"]),
            number(attr["sonnet_pa100k"]),
            number(attr["sonnet_pa100k_delta"]) * 100,
            (0.92, 0.96),
            GREEN,
        ),
        (
            716,
            "CCTV proxy group-heldout 속성 정확도",
            "촬영 CCTV proxy · group 단위 held-out",
            number(attr["sonnet_cctv_baseline"]),
            number(attr["sonnet_cctv"]),
            number(attr["sonnet_cctv_delta"]) * 100,
            (0.80, 0.88),
            RED,
        ),
    ]
    body: list[str] = [
        tx(
            PAD,
            172,
            "두 패널은 서로 다른 평가 묶음이며 y축 확대 범위도 다르다 · 값은 masked 속성 정확도(%)",
            12,
            FAINT,
        ),
    ]
    for x, title_text, note, baseline, sonnet_value, delta, (lo, hi), verdict_color in panels:
        w, plot_x, plot_w, plot_y, plot_h = 588, x + 116, 400, 250, 268
        body += [
            card(x, 200, w, 380, WHITE, HAIRLINE, 16),
            tx(x + 24, 232, title_text, 15, INK, "start", "800"),
            tx(x + 24 + text_width(title_text, 15) + 14, 232, note, 11.5, FAINT),
            rect(plot_x, plot_y, plot_w, plot_h, "#FCFDFE", HAIRLINE, 8, 1.0, 1.2),
            tx_rotated(
                x + 46,
                plot_y + plot_h / 2,
                f"정확도 (%) · y축 {lo * 100:.0f}–{hi * 100:.0f} 확대",
                11,
                MUTED,
                "600",
            ),
        ]
        steps = 4
        for index in range(steps + 1):
            value = lo + (hi - lo) * index / steps
            y = plot_y + plot_h - (value - lo) / (hi - lo) * plot_h
            body += [
                line(plot_x, y, plot_x + plot_w, y, GRID if index else HAIRLINE, 1.2),
                tx(plot_x - 10, y + 4, f"{value * 100:.0f}", 11, FAINT, "end"),
            ]
        for index, (label, value, color, soft) in enumerate(
            [
                ("baseline", baseline, SLATE, SLATE_SOFT),
                ("Sonnet label arm", sonnet_value, VIOLET, VIOLET_SOFT),
            ]
        ):
            bar_x = plot_x + 62 + index * 190
            top = plot_y + plot_h - (value - lo) / (hi - lo) * plot_h
            body += [
                rect(bar_x, top, 116, plot_y + plot_h - top, color, radius=6),
                rect(bar_x, top, 116, 4, soft, radius=2),
                tx(bar_x + 58, top - 12, percent(value, 2), 15, color, "middle", "800"),
                tx(bar_x + 58, plot_y + plot_h + 26, label, 12, BODY, "middle", "600"),
            ]
        sign = "＋" if delta >= 0 else "−"
        body += [
            pill(
                x + w / 2,
                plot_y + plot_h + 46,
                f"변화 {sign}{abs(delta):.2f}%p",
                GREEN_SOFT if delta >= 0 else RED_SOFT,
                GREEN if delta >= 0 else RED,
                13,
                30,
                16,
                "middle",
                "800",
                GREEN_EDGE if delta >= 0 else RED_EDGE,
            ),
            pill(
                x + w - 24,
                214,
                "운영 승격 안 함" if delta < 0 else "소폭 상승",
                WHITE,
                verdict_color,
                11,
                24,
                12,
                "end",
                "700",
                RED_EDGE if delta < 0 else GREEN_EDGE,
            ),
        ]
    body += [
        card(PAD, 600, CANVAS_W - PAD * 2, 76, RED_SOFT, RED_EDGE, 14, shadow=False),
        tx(PAD + 24, 630, "해석 주의", 12.5, RED, "start", "800"),
        tx(
            PAD + 110,
            630,
            "Sonnet은 logit KD가 아니라 응답을 구조화한 black-box pseudo-label pilot이다.",
            12.5,
            BODY,
        ),
        tx(
            PAD + 24,
            656,
            "두 값은 모두 속성/CCTV proxy 지표이며 identity Rank-1 후보 검색 수치와 합산하거나 대체할 수 없다. 속성 proxy가 올라도 CCTV proxy가 내려가면 운영 승격 근거가 되지 못한다.",
            11.8,
            MUTED,
        ),
    ]
    return "".join(body)


def zone_chart(data: dict[str, JsonValue]) -> str:
    """Zone routing proxy accuracy with Wilson lower bounds, clearly marked as proxy."""
    zone = as_map(data["zone_evidence"])
    rows = [as_map(row) for row in as_list(zone["route_results"])]
    selected_route = text(zone["selected_route"])
    x0, plot_w, y0, row_h = 330, 700, 254, 96
    lo, hi = 0.80, 1.00
    body: list[str] = [
        card(PAD, 160, CANVAS_W - PAD * 2, 62, GOLD_SOFT, GOLD_EDGE, 14, shadow=False),
        tx(PAD + 22, 186, "PROXY", 12, GOLD, "start", "800"),
        tx(
            PAD + 86,
            186,
            "구역 우선순위 선택용 synthetic 평가다. 실제 관할 CCTV에서 사람을 찾는 정확도가 아니며 identity Rank-1과 다른 축이다.",
            12.5,
            BODY,
        ),
        tx(
            PAD + 86,
            208,
            f"선택 규칙: Wilson 95% 하한 → accuracy → 추론 지연 · validation 표본 {int(number(rows[0]['total']))}건",
            11.5,
            MUTED,
        ),
        legend_row(
            PAD,
            244,
            [
                ("swatch", BLUE, "선택검증 accuracy (%)"),
                ("swatch", SLATE_EDGE, "Wilson 95% 하한 (%)"),
            ],
            12,
        ),
    ]
    plot_top = y0 + 24
    plot_h = len(rows) * row_h
    body.append(rect(x0, plot_top, plot_w, plot_h, "#FCFDFE", HAIRLINE, 10, 1.0, 1.2))
    for index in range(5):
        value = lo + (hi - lo) * index / 4
        x = x0 + plot_w * index / 4
        body += [
            line(x, plot_top, x, plot_top + plot_h, GRID if index else HAIRLINE, 1.2),
            tx(x, plot_top + plot_h + 26, f"{value * 100:.0f}", 11.5, FAINT, "middle"),
        ]
    body.append(
        tx(
            x0 + plot_w / 2,
            plot_top + plot_h + 50,
            "정확도 (%) · x축 80–100 확대",
            12,
            MUTED,
            "middle",
            "700",
        )
    )

    for index, row in enumerate(rows):
        y = plot_top + index * row_h
        route = text(row["route"])
        accuracy, lower = number(row["accuracy"]), number(row["wilson95_lower"])
        selected = route == selected_route
        acc_x = x0 + plot_w * (accuracy - lo) / (hi - lo)
        low_x = x0 + plot_w * (lower - lo) / (hi - lo)
        if selected:
            body.append(rect(x0 - 306, y + 6, plot_w + 316, row_h - 12, BLUE_SOFT, radius=10))
        body += [
            tx(
                x0 - 20,
                y + 40,
                route.replace("_", " "),
                13.5,
                INK if selected else BODY,
                "end",
                "800" if selected else "600",
            ),
            tx(x0 - 20, y + 60, f"최적 모델: {text(row['best_model'])}", 11, FAINT, "end"),
            rect(x0, y + 24, acc_x - x0, 26, BLUE, radius=6),
            line(low_x, y + 18, low_x, y + 56, SLATE, 2.2),
            tx(acc_x + 12, y + 42, percent(accuracy, 2), 13.5, BLUE, "start", "800"),
            tx(low_x, y + 74, f"Wilson 하한 {percent(lower, 2)}", 11, MUTED, "middle"),
        ]
        if selected:
            body.append(
                pill(
                    CANVAS_W - PAD,
                    y + 28,
                    "현재 선택 route",
                    WHITE,
                    BLUE,
                    11,
                    24,
                    12,
                    "end",
                    "800",
                    BLUE_EDGE,
                )
            )

    footer_y = plot_top + plot_h + 76
    body += [
        card(PAD, footer_y, 620, 96, SURFACE, HAIRLINE, 14, shadow=False),
        tx(
            PAD + 22,
            footer_y + 30,
            f"선택: {selected_route.replace('_', ' ')} + {text(zone['selected_model'])}",
            13.5,
            INK,
            "start",
            "800",
        ),
        tx(
            PAD + 22,
            footer_y + 56,
            f"sealed 평가 accuracy {percent(number(zone['sealed_accuracy']), 2)} · Wilson 하한 {percent(number(zone['sealed_wilson95_lower']), 2)}",
            12,
            BODY,
        ),
        tx(PAD + 22, footer_y + 78, "선택검증과 sealed를 분리해 과최적화를 확인했다", 11.5, MUTED),
        card(716, footer_y, CANVAS_W - PAD - 716, 96, RED_SOFT, RED_EDGE, 14, shadow=False),
        tx(738, footer_y + 30, "아직 아닌 것", 13.5, RED, "start", "800"),
        tx(
            738,
            footer_y + 56,
            "projectCctvEvidence · backendContractIntegrated · promotion 모두 false",
            12,
            BODY,
        ),
        tx(
            738,
            footer_y + 78,
            "실운영 승격에는 실제 구역 배치·시간/카메라 held-out·calibration이 필요",
            11.5,
            MUTED,
        ),
    ]
    return "".join(body)


def evidence_status_chart(data: dict[str, JsonValue]) -> str:
    """One screen that separates verified runtime, best measured comparison, and proxies."""
    head = headline(data)
    identity = as_map(data["identity_evidence"])
    zone = as_map(data["zone_evidence"])
    attr = as_map(data["attribute_evidence"])
    rows = [
        (
            "Worker 계약 · API · 재처리",
            "검증됨",
            "코드/테스트 근거",
            "운영 계약 유지",
            GREEN,
            GREEN_SOFT,
            GREEN_EDGE,
        ),
        (
            "CHIRLA strict identity 후보 검색",
            "현재 최고 비교군",
            f"Rank-1 {percent(number(identity['strict_best_rank1']), 2)} · Recall@5 {percent(number(identity['strict_best_recall_at_5']), 2)} · MRR {percent(number(identity['strict_best_mrr']), 2)}",
            f"strict {int(number(identity['strict_query_count']))}개 query · 후보 검색 기준",
            VIOLET,
            VIOLET_SOFT,
            VIOLET_EDGE,
        ),
        (
            "프로젝트 촬영 CCTV",
            "흐름 파일럿",
            f"same-camera temporal proxy · crop {int(number(identity['project_person_crops']))}개",
            "cross-camera 일반화 근거 아님",
            GOLD,
            GOLD_SOFT,
            GOLD_EDGE,
        ),
        (
            "4구역 routing 확률 모델",
            "proxy 최적 선택",
            f"synthetic 선택검증 {percent(number(zone['selection_validation_accuracy']), 2)} · sealed {percent(number(zone['sealed_accuracy']), 2)}",
            "구역 우선순위용 · identity 정확도 아님",
            BLUE,
            BLUE_SOFT,
            BLUE_EDGE,
        ),
        (
            "Sonnet response-level teacher",
            "승격 보류",
            f"속성 proxy ＋{number(attr['sonnet_pa100k_delta']) * 100:.2f}%p · CCTV proxy −{abs(number(attr['sonnet_cctv_delta'])) * 100:.2f}%p",
            "오프라인 라벨 계층으로만 유지",
            SLATE,
            SLATE_SOFT,
            SLATE_EDGE,
        ),
        (
            "자동 신원확정 85% gate",
            "후속 과제",
            "sealed identity 평가 · calibration 미실시",
            "현재 후보 검색 결론과 다른 층위",
            RED,
            RED_SOFT,
            RED_EDGE,
        ),
    ]
    y0, row_h = 236, 74
    body: list[str] = [
        tx(
            PAD,
            172,
            "같은 화면에서 '검증된 것 · 현재 최고 비교군 · proxy · 후속 과제'를 구분한다",
            12,
            FAINT,
        ),
        tx(PAD + 4, 214, "항목", 11.5, FAINT, "start", "700"),
        tx(474, 214, "상태", 11.5, FAINT, "start", "700"),
        tx(700, 214, "근거 · 수치", 11.5, FAINT, "start", "700"),
        tx(1080, 214, "해석 범위", 11.5, FAINT, "start", "700"),
        rect(PAD, y0, CANVAS_W - PAD * 2, len(rows) * row_h, WHITE, HAIRLINE, 14, 1.0, 1.2),
    ]
    for index, (item, status, evidence, scope, accent, soft, edge) in enumerate(rows):
        y = y0 + index * row_h
        if index:
            body.append(line(PAD + 16, y, CANVAS_W - PAD - 16, y, HAIRLINE, 1.0))
        body += [
            rect(PAD, y + 14, 4, row_h - 28, accent, radius=2),
            tx(PAD + 22, y + 44, item, 13.5, INK, "start", "700"),
            pill(474, y + 24, status, soft, accent, 11.5, 26, 13, "start", "800", edge),
            tx(700, y + 40, evidence, 12, BODY),
            tx(1080, y + 40, scope, 11.5, MUTED),
        ]
    conclusion_y = y0 + len(rows) * row_h + 24
    body += [
        card(PAD, conclusion_y, CANVAS_W - PAD * 2, 92, VIOLET_SOFT, VIOLET_EDGE, 16, shadow=False),
        tx(PAD + 24, conclusion_y + 34, "발표 결론", 12.5, MUTED, "start", "800"),
        tx(
            PAD + 116,
            conclusion_y + 34,
            f"hybrid-solider-clip-v1 — 현재 검증 범위에서 가장 좋은 후보 검색 오케스트레이션 (Rank-1 {percent(number(head['best_rank1']), 2)}, 초기 baseline 대비 ＋{number(head['rank1_delta_points']):.2f}%p)",
            14,
            VIOLET,
            "start",
            "800",
        ),
        tx(
            PAD + 24,
            conclusion_y + 66,
            "AI Worker는 관리자에게 시간·bbox·crop 증거와 Top-K 후보를 반환한다. 각 수치는 해당 평가 범위 안에서만 해석하고, 자동 신원확정은 별도 sealed gate에서 다룬다.",
            12,
            BODY,
        ),
    ]
    return "".join(body)


# ---------------------------------------------------------------------------
# Notebook + entry point
# ---------------------------------------------------------------------------

CHART_FILES = [
    "headline_summary.svg",
    "architecture_pipeline.svg",
    "model_orchestration.svg",
    "identity_strict_ranked.svg",
    "model_evolution.svg",
    "identity_model_bubble.svg",
    "sonnet_ablation.svg",
    "zone_proxy_validation.svg",
    "evidence_status.svg",
]


def make_notebook(data: dict[str, JsonValue]) -> None:
    """Create a reproducible notebook that reads the generated evidence snapshot."""
    notebook_path = ROOT / "output" / "jupyter-notebook" / "ai_worker_presentation_evidence.ipynb"
    chart_literal = ", ".join(f"'{name}'" for name in CHART_FILES)
    code = [
        "from pathlib import Path\nimport json\n\nrepo_root = next(path for path in [Path.cwd(), *Path.cwd().parents] if (path / 'output' / 'ai-presentation' / 'presentation_data.json').exists())\ndata = json.loads((repo_root / 'output' / 'ai-presentation' / 'presentation_data.json').read_text(encoding='utf-8'))\nheadline = data['headline']\nidentity = data['identity_evidence']\nzone = data['zone_evidence']\nprint('selected:', headline['selected_orchestration'], '/', headline['role'])\nprint('strict best:', identity['strict_best_method'], identity['strict_best_rank1'], identity['strict_best_recall_at_5'], identity['strict_best_mrr'])\nprint('improvement: +%.2f pp (x%.1f) from %s' % (headline['rank1_delta_points'], headline['rank1_ratio'], headline['baseline_name']))\nprint('zone routing proxy:', zone['selection_validation_accuracy'], 'promotion:', zone['promotion_accepted'])",
        f"from IPython.display import SVG, display\n\nchart_names = [{chart_literal}]\nfor chart_name in chart_names:\n    display(SVG(filename=str(repo_root / 'output' / 'ai-presentation' / chart_name)))",
    ]
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Experiment: AI Worker 발표·학습용 실험 근거\n",
                "\n",
                "이 노트북은 저장된 실험 JSON과 발표용 시각자료를 다시 읽어 수치와 도식을 함께 확인한다. identity 후보 검색 수치와 proxy 수치를 섞지 않는다.\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1. 재현 조건\n",
                "\n",
                "발표 자료 생성기는 `ai-worker/tools/build_ai_presentation.py`이다. 원본 JSON의 SHA-256과 평가 범위는 `presentation_data.json`에 기록된다.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [code[0]],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 2. 시각자료\n",
                "\n",
                "차트 순서는 발표 순서와 같다. 결론 요약 → 시스템 구조 → 모델 오케스트레이션 → 모델 비교 3종 → proxy 실험 2종 → 근거 상태표.\n",
                "\n",
                "- 오케스트레이션 도식은 순차 게이트, 병렬 증거 branch, late fusion 경계, 별도 구역 routing, 오프라인 teacher 계층을 각각 다른 표기로 구분한다.\n",
                "- 버블차트의 원 크기는 Recall@5, 세로축은 strict Rank-1, 가로축은 파라미터 수(로그 축)다.\n",
                "- Sonnet·구역 차트는 proxy이므로 identity Rank-1과 합산하지 않는다.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [code[1]],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 3. 발표 해석\n",
                "\n",
                "현재 운영 선택은 strict 비교군에서 가장 좋은 Top-K 후보 검색 오케스트레이션(`hybrid-solider-clip-v1`)이다. 초기 baseline 대비 +30.53%p, 약 2.8배 개선했으며 관리자에게 시간·bbox·crop 증거를 반환한다. 자동 신원확정은 별도 후속 sealed gate로 관리한다.\n",
            ],
        },
    ]
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    notebook_path.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    """Build evidence snapshot, charts, and the presentation notebook."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    data = build_snapshot()
    (OUTPUT / "presentation_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    provenance = as_map(data["provenance"])
    source_note = (
        f"근거: {text(provenance['cctv_matrix'])} · {text(provenance['sonnet_comparison'])} · "
        f"{text(provenance['zone_comparison'])} (SHA-256은 presentation_data.json)"
    )

    source_note = (
        "근거 파일: cctv_generalization_method_matrix_20260728.json · "
        "solider_ft_sonnet_comparison_20260724.json · "
        "zone_region_model_comparison_20260802.json"
    )
    write_svg(
        OUTPUT / "headline_summary.svg",
        "현재 결론: hybrid-solider-clip-v1",
        "CHIRLA strict 95개 query 기준 현재 검증된 최적 후보 검색 오케스트레이션과 개선폭",
        headline_chart(data),
        820,
        badge="현재 선택 · 후보 검색",
        footer=(
            source_note,
            "단위 표기: % = 정답률, %p = 백분율 포인트 차이. 모든 수치는 저장된 실험 결과에서 그대로 가져왔다.",
        ),
    )
    write_svg(
        OUTPUT / "model_orchestration.svg",
        "AI Worker 모델 오케스트레이션",
        "순차 게이트 · 병렬 증거 branch · late fusion · 별도 구역 routing · 오프라인 teacher를 구분한 실행 구조",
        orchestration_chart(data),
        1130,
        badge="hybrid-solider-clip-v1",
        footer=(
            "모델 하나가 모든 결정을 하지 않는다. 역할별 신호를 track 단위로 늦게 결합해 Top-K 증거를 반환하고, 필수 증거가 없으면 fail closed로 멈춘다.",
            "구역 routing은 synthetic proxy 기반의 카메라 우선순위 경로이며 identity 점수와 합산하지 않는다. 오프라인 teacher 계층은 요청마다 실행하지 않는다.",
        ),
    )
    if CLAUDE_ORCHESTRATION_ASSET.exists():
        (OUTPUT / "model_orchestration.svg").write_text(
            CLAUDE_ORCHESTRATION_ASSET.read_text(encoding="utf-8"), encoding="utf-8"
        )

    write_svg(
        OUTPUT / "architecture_pipeline.svg",
        "EYES:ON U AI Worker 전체 구조",
        "과거 녹화본 분석 경로와 Jetson 실시간 경로를 분리한 운영 흐름",
        architecture_chart(),
        820,
        badge="시스템 구조",
        badge_tone=(SLATE, SLATE_SOFT, SLATE_EDGE),
        footer=(
            "핵심 원칙: AI Worker는 후보를 좁혀 증거를 반환하고, 최종 수사 판단은 관리자·중앙 시스템이 담당한다.",
            "실시간 Jetson 경로와 과거 녹화본 Worker 경로를 분리해 비용·지연·역할을 통제한다.",
        ),
    )
    write_svg(
        OUTPUT / "identity_strict_ranked.svg",
        "사람 식별 후보 검색 성능 비교",
        "CHIRLA strict cross-camera·sequence 분리 평가 · 동일한 95개 query · 단위 %",
        ranked_chart(data),
        880,
        badge="Rank-1 47.37% 공동 최고",
        footer=(
            "Rank-1은 1위 후보가 정답인 비율, Recall@5는 상위 5후보 안에 정답이 들어오는 비율, identity-MRR은 정답 순위 역수의 평균이다.",
            "overlap proxy(카메라·시퀀스 중복 잔존) 결과는 이 비교에 섞지 않았다.",
        ),
    )
    write_svg(
        OUTPUT / "model_evolution.svg",
        "모델 발전 과정: 후보 검색 성능",
        "같은 strict 평가만 다시 정렬해 초기 baseline과 현재 공동 최고 사이의 개선폭을 표시",
        evolution_chart(data),
        980,
        badge="＋30.53%p · 약 2.8배",
        badge_tone=(GOLD, GOLD_SOFT, GOLD_EDGE),
        footer=(
            "이 개선폭은 identity 후보 검색 Rank-1 기준이며, 속성 proxy·구역 routing proxy와 합산하지 않았다.",
            "%p는 백분율 포인트 차이를 뜻한다. 16.84% → 47.37%이므로 ＋30.53%p, 약 2.8배다.",
        ),
    )
    write_svg(
        OUTPUT / "identity_model_bubble.svg",
        "모델 규모와 후보 검색 성능의 균형",
        "가로축 파라미터 수(로그) · 세로축 strict Rank-1 · 원 크기 Recall@5",
        bubble_chart(data),
        760,
        badge="SOLIDER 계열 선택",
        footer=(
            "큰 모델이 항상 좋지 않다. 88M SOLIDER 계열이 428M CLIP L/14보다 strict Rank-1과 Recall@5 모두 높다.",
            "모델 선택은 파라미터 수가 아니라 동일 strict protocol 결과와 AI Worker 역할(후보 검색·증거 반환)을 기준으로 했다.",
        ),
    )
    write_svg(
        OUTPUT / "sonnet_ablation.svg",
        "Sonnet teacher 라벨 ablation",
        "속성 proxy와 CCTV proxy를 분리해 비교 · 두 패널의 y축 확대 범위가 다름",
        sonnet_chart(data),
        760,
        badge="운영 승격 보류",
        badge_tone=(RED, RED_SOFT, RED_EDGE),
        footer=(
            "PA-100K 속성 proxy는 ＋0.31%p 상승했지만 CCTV proxy는 −1.54%p 하락해 운영 모델로 승격하지 않았다.",
            "두 지표 모두 속성 정확도 proxy다. identity 후보 검색 Rank-1을 대신하지 않는다.",
        ),
    )
    write_svg(
        OUTPUT / "zone_proxy_validation.svg",
        "4구역 확률 모델 검증 (routing proxy)",
        "구역 우선순위 선택용 synthetic 평가 · accuracy와 Wilson 95% 하한을 함께 표시",
        zone_chart(data),
        820,
        badge="synthetic proxy",
        badge_tone=(GOLD, GOLD_SOFT, GOLD_EDGE),
        footer=(
            "expected_bayes_8 + logistic을 선택검증 92.39%(Wilson 하한 90.48%)로 골랐고, sealed 평가에서 91.88%를 확인했다.",
            "이 수치는 다음 카메라·구역을 고르는 routing proxy이며 '실종자를 92% 찾는다'는 뜻이 아니다.",
        ),
    )
    write_svg(
        OUTPUT / "evidence_status.svg",
        "발표용 근거 상태표",
        "검증된 구성 · 현재 최고 비교군 · proxy · 후속 과제를 한 화면에서 구분",
        evidence_status_chart(data),
        960,
        badge="근거 구분",
        badge_tone=(GREEN, GREEN_SOFT, GREEN_EDGE),
        footer=(
            source_note,
            "상태 색: 초록=검증됨, 보라=현재 최고 비교군, 금색/파랑=proxy, 회색=보류, 빨강=후속 sealed gate.",
        ),
    )
    make_notebook(data)
    print(f"Generated presentation evidence under {OUTPUT}")


if __name__ == "__main__":
    main()

