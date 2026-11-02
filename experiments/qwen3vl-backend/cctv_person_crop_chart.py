
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = PROJECT_ROOT / "experiments" / "results" / "cctv_person_crop_comparison.json"
OUTPUT_ROOT = PROJECT_ROOT / "experiments" / "results"


def main() -> None:
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    if font_path.is_file():
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font_path).get_name()
        plt.rcParams["axes.unicode_minus"] = False
    data = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    models = data["models"]
    order = np.argsort([item["person_only_crop"]["attribute_accuracy"] for item in models])
    models = [models[index] for index in order]
    labels = [item["model"] for item in models]
    original = np.array([item["original"]["attribute_accuracy"] * 100 for item in models])
    crop = np.array([item["person_only_crop"]["attribute_accuracy"] * 100 for item in models])
    delta = np.array([item["delta"]["attribute_accuracy_pp"] for item in models])
    lower = np.array([item["delta"]["bootstrap_95ci_pp_by_group"][0] for item in models])
    upper = np.array([item["delta"]["bootstrap_95ci_pp_by_group"][1] for item in models])
    y = np.arange(len(labels))

    fig, (left, right) = plt.subplots(1, 2, figsize=(14, 6.8), gridspec_kw={"width_ratios": [1.45, 1]})
    left.barh(y + 0.18, original, height=0.32, color="#94a3b8", label="원본")
    left.barh(y - 0.18, crop, height=0.32, color="#2563eb", label="사람 전체 crop")
    for index, value in enumerate(original):
        left.text(value + 0.5, index + 0.18, f"{value:.1f}%", va="center", fontsize=9)
    for index, value in enumerate(crop):
        left.text(value + 0.5, index - 0.18, f"{value:.1f}%", va="center", fontsize=9)
    left.set_yticks(y, labels)
    left.set_xlim(0, max(max(original), max(crop)) + 9)
    left.set_xlabel("속성 정확도")
    left.set_title("원본과 사람 전체 crop")
    left.grid(axis="x", alpha=0.25)
    left.legend(loc="lower right", frameon=False)

    right.axvline(0, color="#334155", linewidth=1)
    colors = ["#16a34a" if value >= 0 else "#dc2626" for value in delta]
    right.errorbar(
        delta,
        y,
        xerr=[delta - lower, upper - delta],
        fmt="none",
        ecolor="#64748b",
        elinewidth=1.5,
        capsize=3,
        zorder=1,
    )
    right.scatter(delta, y, c=colors, s=75, zorder=2)
    for index, value in enumerate(delta):
        right.text(
            value + (0.45 if value >= 0 else -0.45),
            index,
            f"{value:+.2f}%p",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=9,
        )
    right.set_yticks(y, labels)
    right.set_xlabel("정확도 변화(%p)")
    right.set_title("crop 효과와 그룹 bootstrap 95% CI")
    right.grid(axis="x", alpha=0.25)

    fig.suptitle("CCTV 사람 전체 crop 속성 proxy 비교", fontsize=16, fontweight="bold")
    fig.text(
        0.5,
        0.01,
        "45개 paired 입력 · Simuletic 15 + PA-100K 30 · transformers 5.14.1 · 실제 identity track-heldout 지표 아님",
        ha="center",
        fontsize=9,
        color="#475569",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(OUTPUT_ROOT / "cctv_person_crop_comparison.png", dpi=180, bbox_inches="tight")
    fig.savefig(OUTPUT_ROOT / "cctv_person_crop_comparison.svg", bbox_inches="tight")
    plt.close(fig)

    with (OUTPUT_ROOT / "cctv_person_crop_comparison.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "model",
            "original_accuracy_pct",
            "person_only_crop_accuracy_pct",
            "delta_pp",
            "bootstrap_ci_lower_pp_by_group",
            "bootstrap_ci_upper_pp_by_group",
            "original_p95_s",
            "crop_p95_s",
        ])
        for item in models:
            writer.writerow([
                item["model"],
                item["original"]["attribute_accuracy"] * 100,
                item["person_only_crop"]["attribute_accuracy"] * 100,
                item["delta"]["attribute_accuracy_pp"],
                item["delta"]["bootstrap_95ci_pp_by_group"][0],
                item["delta"]["bootstrap_95ci_pp_by_group"][1],
                item["original"]["latency_s_p95"],
                item["person_only_crop"]["latency_s_p95"],
            ])
    print(json.dumps({"status": "measured", "png": "experiments/results/cctv_person_crop_comparison.png", "models": len(models)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

