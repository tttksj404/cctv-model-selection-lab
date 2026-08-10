from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

STRICT_PROTOCOL = "strict-cross-camera-sequence"
SHORT_LABELS = {
    "CLIP ViT-B/32 mean (strict)": "CLIP-B/32",
    "CLIP ViT-L/14 mean (strict)": "CLIP-L/14",
    "DINOv2 mean (strict)": "DINOv2-B",
    "SigLIP2 top-3 mean (strict)": "SigLIP2-B top3",
    "OSNet mean (strict)": "OSNet",
    "FastReID SBS top-3 mean + hflip (strict)": "FastReID SBS+TTA",
    "SOLIDER top-3 mean + hflip (strict)": "SOLIDER top3+TTA",
    "SOLIDER mean + hflip (strict)": "SOLIDER mean+TTA",
    "SOLIDER max + hflip (strict)": "SOLIDER max+TTA",
    "SOLIDER top-3 mean (strict)": "SOLIDER top3",
}


class ChartDataError(ValueError):
    pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot the strict CCTV ReID comparison")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("experiments/results/cctv_generalization_method_matrix_20260728.json"),
    )
    parser.add_argument(
        "--png",
        type=Path,
        default=Path("experiments/results/cctv_reid_bubble_20260728.png"),
    )
    parser.add_argument(
        "--svg",
        type=Path,
        default=Path("experiments/results/cctv_reid_bubble_20260728.svg"),
    )
    return parser.parse_args()


def _color(family: str) -> str:
    if family.startswith("solider"):
        return "#C58A00"
    if "reid" in family:
        return "#285F8F"
    return "#8FA9BD"


def main() -> None:
    args = _parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    rows = [
        row
        for row in matrix["methods"]
        if row.get("metricUnit") == "frame"
        and row.get("protocol") == STRICT_PROTOCOL
        and isinstance(row.get("rank1"), (int, float))
        and isinstance(row.get("recallAt5"), (int, float))
        and isinstance(row.get("parameterMillionsApprox"), (int, float))
    ]
    if len(rows) < 6:
        raise ChartDataError("엄격 프로토콜로 비교 가능한 모델이 최소 6개 필요합니다")

    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    figure, axis = plt.subplots(figsize=(14, 9), dpi=160)
    axis.set_facecolor("#FAFBFC")
    figure.patch.set_facecolor("white")

    label_offsets = {
        "SOLIDER max+TTA": (8, -20),
        "SOLIDER top3+TTA": (-112, 8),
        "SOLIDER mean+TTA": (8, 8),
        "SOLIDER top3": (-105, -20),
        "CLIP-L/14": (8, -20),
        "SigLIP2-B top3": (8, 8),
        "FastReID SBS+TTA": (8, 8),
        "OSNet": (8, -20),
        "CLIP-B/32": (8, 8),
        "DINOv2-B": (8, 8),
    }
    for row in rows:
        label = SHORT_LABELS.get(row["name"], row["name"])
        x = float(row["rank1"]) * 100
        y = float(row["recallAt5"]) * 100
        parameters = float(row["parameterMillionsApprox"])
        size = 55 + math.sqrt(parameters) * 23
        color = _color(str(row["family"]))
        axis.scatter(
            x,
            y,
            s=size,
            color=color,
            edgecolor="#26343F",
            linewidth=0.8,
            alpha=0.88,
            zorder=3,
        )
        ci_low = row.get("rank1Ci95Low")
        ci_high = row.get("rank1Ci95High")
        if isinstance(ci_low, (int, float)) and isinstance(ci_high, (int, float)):
            axis.errorbar(
                x,
                y,
                xerr=[[x - float(ci_low) * 100], [float(ci_high) * 100 - x]],
                fmt="none",
                ecolor="#52616B",
                elinewidth=0.8,
                capsize=2,
                alpha=0.55,
                zorder=2,
            )
        axis.annotate(
            label,
            (x, y),
            xytext=label_offsets.get(label, (7, 7)),
            textcoords="offset points",
            fontsize=8.4,
            color="#1F2A33",
        )

    rank1_values = [float(row["rank1"]) * 100 for row in rows]
    recall5_values = [float(row["recallAt5"]) * 100 for row in rows]
    x_min = max(0.0, min(rank1_values) - 8)
    y_min = max(0.0, min(recall5_values) - 8)
    axis.axvline(85, color="#303A42", linestyle="--", linewidth=1.2)
    axis.text(85.4, 99.2, "목표 Rank-1 85%", fontsize=9, color="#303A42", rotation=90, va="top")
    axis.set_xlim(x_min, 90)
    axis.set_ylim(y_min, 100)
    axis.set_xlabel("CHIRLA 엄격 교차 카메라·시퀀스 Rank-1 (%)", fontsize=11)
    axis.set_ylabel("CHIRLA 엄격 교차 카메라·시퀀스 Recall@5 (%)", fontsize=11)
    figure.suptitle(
        "CCTV 인물 재식별 모델 공정 비교",
        x=0.055,
        y=0.985,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    figure.text(
        0.055,
        0.938,
        (
            "동일 11개 gallery/query identity·95개 query, "
            "각 query에서 같은 카메라 또는 같은 시퀀스 후보 제외"
        ),
        fontsize=10,
        color="#52616B",
    )
    axis.grid(True, color="#DCE3E8", linewidth=0.7, alpha=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color("#7A8790")
    axis.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="범용 임베딩",
                markerfacecolor="#8FA9BD",
                markeredgecolor="#26343F",
                markersize=9,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="전용 ReID",
                markerfacecolor="#285F8F",
                markeredgecolor="#26343F",
                markersize=9,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="SOLIDER-ReID",
                markerfacecolor="#C58A00",
                markeredgecolor="#26343F",
                markersize=9,
            ),
        ],
        loc="lower right",
        frameon=False,
    )
    best = max(
        rows,
        key=lambda row: (
            float(row["rank1"]),
            float(row.get("identityMrr") or 0),
            row.get("tta") == "none",
        ),
    )
    figure.text(
        0.01,
        0.01,
        (
            "주의: 프로젝트 자체 교차 카메라 identity 정답이 아닌 공개 CHIRLA "
            "프록시 결과이며, 85% 달성을 증명하지 않습니다."
        ),
        fontsize=9,
        color="#52616B",
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.90))
    args.png.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.png, bbox_inches="tight")
    figure.savefig(args.svg, bbox_inches="tight")
    print(
        json.dumps(
            {
                "protocol": STRICT_PROTOCOL,
                "rows": len(rows),
                "best": best["name"],
                "bestRank1Percent": round(float(best["rank1"]) * 100, 2),
                "png": str(args.png),
                "svg": str(args.svg),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

