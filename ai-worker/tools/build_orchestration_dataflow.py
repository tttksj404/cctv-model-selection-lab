#!/usr/bin/env python3
"""Build the presentation diagram that exposes model-to-model data contracts."""

from __future__ import annotations

import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SVG = ROOT / "tools" / "assets" / "claude_model_orchestration.svg"
OUTPUT_SVG = ROOT / "output" / "ai-presentation" / "model_orchestration.svg"
ROOT_SVG = REPO / "ai_worker_orchestration.svg"
PRESENTATION_SVG = REPO / "eyeson-u-ai-presentation-assets" / "svg" / "claude_ai_worker_orchestration.svg"

BG = "#f7f9fc"
INK = "#172033"
MUTED = "#58657a"
BORDER = "#dbe2ee"
BLUE = "#2563c7"
BLUE_SOFT = "#eaf1fb"
GREEN = "#2e8b57"
GREEN_SOFT = "#eaf7ef"
ORANGE = "#d98217"
ORANGE_SOFT = "#fff5e8"
PURPLE = "#6d4cc2"
PURPLE_SOFT = "#f0ebff"
GRAY = "#8d99aa"
GRAY_SOFT = "#f1f3f6"
RED = "#c9506e"
RED_SOFT = "#fff0f3"


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def text(x: float, y: float, value: str, *, size: int = 16, color: str = INK,
         weight: int = 400, anchor: str = "start", family: str = "") -> str:
    font = family or "Pretendard, 'Noto Sans KR', Arial, sans-serif"
    return (
        f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}px" '
        f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(value)}</text>'
    )


def multiline(x: float, y: float, lines: list[str], *, size: int = 16,
              color: str = INK, weight: int = 400, gap: int = 23,
              anchor: str = "start") -> str:
    font = "Pretendard, 'Noto Sans KR', Arial, sans-serif"
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else gap}px">{esc(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}px" '
        f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{spans}</text>'
    )


def rect(x: float, y: float, w: float, h: float, *, fill: str = "#fff",
         stroke: str = BORDER, radius: int = 14, width: int = 1,
         dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash_attr}/>'
    )


def line(x1: float, y1: float, x2: float, y2: float, *, color: str = BLUE,
         width: int = 3, marker: str = "blue", dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    marker_attr = f' marker-end="url(#arrow-{marker})"' if marker != "none" else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
        f'stroke-width="{width}"{dash_attr}{marker_attr}/>'
    )


def path(d: str, *, color: str = BLUE, width: int = 3, marker: str = "blue",
         dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    marker_attr = f' marker-end="url(#arrow-{marker})"' if marker != "none" else ""
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"'
        f'{dash_attr}{marker_attr}/>'
    )


def pill(x: float, y: float, label: str, *, color: str = BLUE,
         fill: str = "#fff", size: int = 14, width: int | None = None) -> str:
    w = width or max(88, 10 * len(label) + 22)
    return (
        rect(x, y - 17, w, 27, fill=fill, stroke=color, radius=7, width=1)
        + text(x + 10, y + 2, label, size=size, color=color, weight=600)
    )


def node(x: float, y: float, w: float, h: float, title: str, subtitle: str,
         body: list[str], *, fill: str = "#fff", stroke: str = BORDER,
         accent: str = BLUE, title_size: int = 20) -> str:
    h = max(h, 190)
    out = [rect(x, y, w, h, fill=fill, stroke=stroke, width=2)]
    out.append(rect(x, y, 8, h, fill=accent, stroke=accent, radius=4, width=0))
    out.append(text(x + 24, y + 32, title, size=title_size, weight=750))
    out.append(text(x + 24, y + 58, subtitle, size=15, color=accent, weight=650))
    out.append(line(x + 24, y + 76, x + w - 20, y + 76, color="#edf0f5", width=1, marker="none"))
    out.append(multiline(x + 24, y + 105, body, size=15, color=INK, gap=23))
    return "".join(out)


def model_card(x: float, y: float, w: float, h: float, title: str,
               receive: str, send: str, *, accent: str = GREEN) -> str:
    out = [rect(x, y, w, h, fill=GREEN_SOFT, stroke=accent, radius=12, width=2)]
    out.append(text(x + 16, y + 29, title, size=18, weight=750))
    out.append(text(x + 16, y + 55, "받음", size=13, color=accent, weight=750))
    out.append(text(x + 62, y + 55, receive, size=14, color=INK, weight=550))
    out.append(text(x + 16, y + 80, "보냄", size=13, color=accent, weight=750))
    out.append(text(x + 62, y + 80, send, size=14, color=INK, weight=550))
    return "".join(out)


def build_svg() -> str:
    out: list[str] = []
    out.append(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" '
        'viewBox="0 0 1920 1080" font-family="Pretendard, Noto Sans KR, Arial, sans-serif">'
    )
    out.append("<defs>")
    for name, color in (("blue", BLUE), ("green", GREEN), ("orange", ORANGE), ("gray", GRAY)):
        out.append(
            f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
    out.append("</defs>")
    out.append(rect(0, 0, 1920, 1080, fill=BG, stroke=BG, radius=0, width=0))

    # Header and the requested performance story.
    out.append(text(56, 58, "AI Worker 오케스트레이션", size=40, weight=800))
    out.append(text(56, 93, "모델 간 정보를 교환해 단일 모델의 한계를 넘는 CCTV 실종자 후보 탐색", size=20, color=MUTED))
    out.append(text(56, 126, "핵심 메시지: 단일 모델 최고 44%  →  증거 오케스트레이션 + 파인튜닝 조합 77%", size=22, color=BLUE, weight=750))

    out.append(rect(1325, 28, 228, 116, fill="#fff1f0", stroke="#e2a19b", radius=14, width=2))
    out.append(text(1347, 54, "단일 모델 최고", size=16, color="#a34740", weight=700))
    out.append(text(1347, 106, "44%", size=50, color="#a34740", weight=800))
    out.append(text(1450, 106, "baseline", size=15, color=MUTED, weight=600))
    out.append(line(1558, 86, 1600, 86, color=ORANGE, width=4, marker="orange"))
    out.append(pill(1545, 66, "오케스트레이션", color=ORANGE, fill=ORANGE_SOFT, size=12, width=128))
    out.append(rect(1604, 28, 260, 116, fill=GREEN_SOFT, stroke=GREEN, radius=14, width=2))
    out.append(text(1626, 54, "오케스트레이션 + 파인튜닝", size=16, color=GREEN, weight=700))
    out.append(text(1626, 106, "77%", size=50, color=GREEN, weight=800))
    out.append(text(1733, 106, "실험 결과", size=15, color=MUTED, weight=600))
    out.append(line(56, 148, 1864, 148, color="#e3e8f0", width=2, marker="none"))

    # Runtime title and stage labels.
    out.append(text(56, 178, "RUNTIME · 모델 간 데이터 계약이 보이는 추론 경로", size=18, color=INK, weight=800))
    out.append(pill(1430, 178, "실선 = 실제 추론 데이터", color=BLUE, fill=BLUE_SOFT, size=13, width=170))

    # Runtime input and gate nodes.
    out.append(node(56, 200, 240, 170, "ProfileNormalizer", "프로필 계약", [
        "입력: 인상착의·시간·카메라", "출력: canonical_profile JSON", "query text embedding", "attribute constraints",
    ], fill="#fff", accent=ORANGE))
    out.append(node(330, 200, 240, 170, "Recording Segment", "영상 계약", [
        "입력: camera / time range", "출력: frame[t]", "camera_id + timestamp", "recording metadata",
    ], fill="#fff", accent=BLUE))
    out.append(node(604, 200, 240, 170, "YOLO + ByteTrack", "사람 게이트", [
        "입력: frame[t]", "출력: person bbox", "track_id + tracklet", "crop + blur/occlusion quality",
    ], fill="#fff", accent=ORANGE))

    # Main arrows before branches.
    out.append(line(296, 285, 330, 285, color=ORANGE, width=3, marker="orange"))
    out.append(pill(285, 262, "profile JSON", color=ORANGE, fill=ORANGE_SOFT, size=12, width=105))
    out.append(line(570, 285, 604, 285, color=BLUE, width=3, marker="blue"))
    out.append(pill(560, 262, "frame[t] + time", color=BLUE, fill=BLUE_SOFT, size=12, width=125))
    out.append(line(844, 285, 878, 285, color=BLUE, width=3, marker="blue"))
    out.append(pill(804, 180, "track_crop + bbox + track_id", color=BLUE, fill=BLUE_SOFT, size=12, width=220))

    # Parallel evidence group.
    out.append(rect(878, 196, 430, 380, fill="#fff", stroke=BORDER, radius=16, width=2))
    out.append(text(902, 228, "병렬 증거 생성", size=22, weight=800))
    out.append(text(902, 253, "같은 crop을 서로 다른 관점의 증거로 변환", size=15, color=MUTED))
    out.append(model_card(902, 276, 190, 104, "SOLIDER ReID", "crop / tracklet", "reid_embedding", accent=GREEN))
    out.append(model_card(1110, 276, 190, 104, "CLIP ViT-L/14", "crop + text", "clip_score", accent=GREEN))
    out.append(model_card(902, 400, 190, 104, "ROI + SOLIDER-PAR", "crop / mask", "attr_vector + conf", accent=GREEN))
    out.append(model_card(1110, 400, 190, 104, "Frame Quality", "frame / bbox", "quality_mask", accent=BLUE))
    # Control/config flows from profile normalizer to the branches.
    out.append(path("M178,370 C178,430 1020,170 1190,276", color=ORANGE, width=2, marker="orange", dash="7 5"))
    out.append(pill(520, 402, "text_embedding", color=ORANGE, fill=ORANGE_SOFT, size=12, width=124))
    out.append(path("M205,370 C270,505 820,550 902,452", color=ORANGE, width=2, marker="orange", dash="7 5"))
    out.append(pill(490, 515, "attribute_constraints", color=ORANGE, fill=ORANGE_SOFT, size=12, width=154))

    # Track-level aggregator and fusion.
    out.append(node(1345, 200, 250, 170, "Temporal Aggregator", "track 단위 집계", [
        "입력: per-frame evidence", "대표 embedding", "attribute consensus", "quality + evidence_count",
    ], fill=BLUE_SOFT, accent=BLUE))
    out.append(node(1345, 402, 250, 174, "Availability-aware", "Late Fusion", [
        "입력: track_evidence", "결측 모델은 mask 처리", "score + uncertainty", "review_reason",
    ], fill=PURPLE_SOFT, stroke="#c9b9f5", accent=PURPLE))
    # Branch outputs into aggregator.
    out.append(line(1308, 350, 1345, 350, color=GREEN, width=3, marker="green"))
    out.append(pill(1140, 548, "embedding + score + attrs + quality", color=GREEN, fill=GREEN_SOFT, size=12, width=248))
    out.append(line(1470, 390, 1470, 402, color=GREEN, width=3, marker="green"))
    out.append(pill(1195, 392, "track_evidence", color=GREEN, fill=GREEN_SOFT, size=12, width=120))
    # Fusion to candidate package and central review.
    out.append(node(1640, 200, 224, 170, "Top-K 후보", "ranked evidence", [
        "입력: score_uncertainty", "순위 + representative crop", "bbox sequence", "camera / time / zone",
    ], fill=RED_SOFT, stroke="#e4a9b8", accent=RED, title_size=22))
    out.append(node(1640, 402, 224, 174, "Central Server", "관리자 검토", [
        "candidate_packet", "확인 / 승인 / 기록", "관리자 결과와", "Jetson event를 merge",
    ], fill=BLUE_SOFT, accent=BLUE, title_size=22))
    out.append(path("M1595,488 C1620,488 1610,285 1640,285", color=PURPLE, width=3, marker="blue"))
    out.append(pill(1435, 390, "score + uncertainty", color=PURPLE, fill=PURPLE_SOFT, size=12, width=146))
    out.append(line(1752, 390, 1752, 402, color=BLUE, width=3, marker="blue"))
    out.append(pill(1762, 390, "candidate_packet", color=BLUE, fill=BLUE_SOFT, size=12, width=140))
    # The candidate package detail callout.
    out.append(rect(1530, 592, 334, 88, fill="#fff", stroke=BORDER, radius=10, width=1))
    out.append(text(1548, 617, "candidate_packet", size=16, weight=750, color=BLUE))
    out.append(multiline(1548, 640, ["candidate_id · camera_id · zone_id · time", "score · bbox sequence · crop ref", "evidence summary · uncertainty · reason"], size=13, color=MUTED, gap=17))

    # Model contract table, readable at presentation scale.
    out.append(text(56, 622, "모델별 정보 교환표", size=18, weight=800))
    table = [
        (56, "SOLIDER ReID", "crop/tracklet", "reid_embedding", "Temporal Aggregator", GREEN),
        (498, "CLIP ViT-L/14", "text_embedding + crop", "clip_score", "Temporal Aggregator", GREEN),
        (940, "ROI + SOLIDER-PAR", "crop/mask", "attr_vector + confidence", "Temporal Aggregator", GREEN),
        (1382, "Aggregator → Fusion", "per-frame evidence", "track_evidence → score", "Top-K 후보", PURPLE),
    ]
    for x, title, receive, send, consumer, accent in table:
        out.append(rect(x, 646, 410, 142, fill="#fff", stroke=BORDER, radius=12, width=1.5))
        out.append(text(x + 18, 674, title, size=17, weight=750, color=INK))
        out.append(text(x + 18, 703, "받음", size=13, weight=750, color=accent))
        out.append(text(x + 70, 703, receive, size=14, weight=550, color=INK))
        out.append(text(x + 18, 731, "보냄", size=13, weight=750, color=accent))
        out.append(text(x + 70, 731, send, size=14, weight=550, color=INK))
        out.append(text(x + 18, 759, "다음 소비자", size=13, weight=750, color=accent))
        out.append(text(x + 112, 759, consumer, size=14, weight=550, color=MUTED))

    # Offline teacher lane: it creates artifacts, not per-request runtime inference.
    out.append(rect(56, 820, 1300, 150, fill=GRAY_SOFT, stroke="#c7ccd6", radius=14, width=2, dash="10 7"))
    out.append(text(80, 850, "OFFLINE TEACHER LANE · 요청마다 직접 호출하지 않음", size=18, weight=800, color=MUTED))
    teachers = [(80, "Grounding DINO", "box labels"), (300, "SAM2.1", "mask / track labels"), (520, "Florence-2", "attribute labels"), (740, "Sonnet", "review / pseudo-label")]
    for x, title, caption in teachers:
        out.append(rect(x, 872, 196, 70, fill="#fff", stroke="#aeb7c4", radius=10, width=1.5, dash="6 5"))
        out.append(text(x + 14, 900, title, size=16, weight=750))
        out.append(text(x + 14, 924, caption, size=13, color=MUTED))
    out.append(path("M952,907 L1075,907", color=GRAY, width=2, marker="gray", dash="8 6"))
    out.append(pill(970, 885, "labels", color=GRAY, fill="#fff", size=12, width=70))
    out.append(rect(1080, 858, 240, 92, fill="#fff", stroke="#aeb7c4", radius=10, width=2))
    out.append(text(1096, 886, "학습 artifact", size=17, weight=750, color=MUTED))
    out.append(multiline(1096, 912, ["weights", "thresholds + calibration"], size=14, color=INK, gap=21))
    out.append(path("M1200,858 C1200,790 1070,770 1030,576", color=GRAY, width=2, marker="gray", dash="8 6"))
    out.append(pill(1100, 792, "weights / calibration", color=GRAY, fill="#fff", size=12, width=166))
    out.append(text(56, 994, "회색 점선은 런타임 모델에 반영되는 학습 산출물이고, 실선은 녹화본 분석 중 실제 오가는 데이터다.", size=15, color=MUTED, weight=600))

    # Jetson event bridge into central review.
    out.append(rect(1382, 820, 482, 150, fill=ORANGE_SOFT, stroke="#e0a34f", radius=14, width=2, dash="10 7"))
    out.append(text(1406, 850, "Jetson 실시간 이벤트", size=18, weight=800, color="#b06a10"))
    out.append(multiline(1406, 885, ["실시간 후보: candidate_key + camera_id + timestamp", "중앙 서버가 같은 후보 검토 단계로 merge", "녹화본 후보와 실시간 후보를 한 화면에서 비교"], size=14, color=INK, gap=22))
    out.append(path("M1620,820 C1620,740 1752,740 1752,576", color=ORANGE, width=3, marker="orange", dash="10 6"))
    out.append(pill(1635, 746, "candidate_key + event", color=ORANGE, fill="#fff", size=12, width=150))

    # Legend.
    out.append(line(56, 1025, 1864, 1025, color="#e3e8f0", width=2, marker="none"))
    out.append(line(80, 1050, 120, 1050, color=BLUE, width=3, marker="none"))
    out.append(text(132, 1056, "영상/메타데이터", size=14, color=MUTED))
    out.append(line(300, 1050, 340, 1050, color=GREEN, width=3, marker="none"))
    out.append(text(352, 1056, "임베딩/특징 증거", size=14, color=MUTED))
    out.append(line(565, 1050, 605, 1050, color=ORANGE, width=3, marker="none"))
    out.append(text(617, 1056, "프로필·설정·실시간 제어", size=14, color=MUTED))
    out.append(line(875, 1050, 915, 1050, color=GRAY, width=2, marker="none", dash="8 6"))
    out.append(text(927, 1056, "오프라인 teacher → 학습 artifact", size=14, color=MUTED))
    out.append(text(1450, 1056, "설명 포인트: 서로 다른 증거를 만들고 late fusion에서 결합", size=14, color=INK, weight=700))

    out.append("</svg>")
    return "\n".join(out) + "\n"


def remove_dense_candidate_callout(svg: str) -> str:
    """Keep candidate_packet in the server card/arrow and remove the crowded duplicate."""
    svg = re.sub(r'<rect x="1530" y="592"[^>]*/>', "", svg)
    svg = re.sub(r'<text x="1548" y="617"[\\s\\S]*?</text>', "", svg)
    svg = re.sub(r'<text x="1548" y="640"[\\s\\S]*?</text>', "", svg)
    return svg


def main() -> None:
    svg = remove_dense_candidate_callout(build_svg())
    for target in (SVG, OUTPUT_SVG, ROOT_SVG, PRESENTATION_SVG):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8")
    # Keep an explicit dataflow-named copy next to the presentation artifacts.
    named = PRESENTATION_SVG.with_name("claude_ai_worker_orchestration_dataflow.svg")
    named.write_text(svg, encoding="utf-8")
    print(f"generated {len(svg):,} bytes")
    for target in (SVG, OUTPUT_SVG, ROOT_SVG, PRESENTATION_SVG, named):
        print(target)


if __name__ == "__main__":
    main()

