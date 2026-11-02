from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager

project_root = Path.cwd().parent if Path.cwd().name == "experiments" else Path.cwd()
results_root = project_root / "experiments" / "results"
font_candidates = [
    Path("C:/Windows/Fonts/malgun.ttf"),
    Path("C:/Windows/Fonts/NotoSansKR-Regular.ttf"),
]
font_path = next((path for path in font_candidates if path.exists()), None)
if font_path:
    font_manager.fontManager.addfont(str(font_path))
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
plt.rcParams["axes.unicode_minus"] = False
colors = {
    "teacher/reference": "#1565c0",
    "edge candidate": "#2e7d32",
    "server VLM": "#c62828",
    "retrieval candidate": "#6a1b9a",
    "caption candidate": "#ef6c00",
}
fig, ax = plt.subplots(figsize=(11, 7), constrained_layout=True)
chart_rows = globals().get("rows", [])
for row in chart_rows:
    ax.scatter(
        row["속성 proxy 정확도(%)"],
        row["p95 지연(s)"],
        s=500 + row["파라미터(B)"] * 450,
        color=colors[row["역할"]],
        alpha=0.78,
        edgecolor="white",
        linewidth=1.2,
        label=row["역할"],
    )
    ax.annotate(
        row["모델"],
        (row["속성 proxy 정확도(%)"], row["p95 지연(s)"]),
        xytext=(7, 7),
        textcoords="offset points",
        fontsize=10,
    )
ax.axvline(
    85, color="#777777", linestyle="--", linewidth=1.2, label="정식 identity gate 85% (참고선)"
)
ax.set_yscale("log")
ax.set_xlabel("속성 proxy 정확도 (%)")
ax.set_ylabel("p95 지연시간 (초, 로그 축)")
ax.set_title("동일 proxy 계약 기준 CCTV 후보 모델 비교")
ax.grid(True, which="both", alpha=0.22)
handles, labels = ax.get_legend_handles_labels()
unique = dict(zip(labels, handles, strict=True))
ax.legend(unique.values(), unique.keys(), loc="upper left", frameon=False)
ax.text(
    0.01,
    -0.16,
    "버블 크기: 대략적인 파라미터 규모(B). "
    "85% 선은 identity 점수가 아니라 proxy 차트의 참고선이다.",
    transform=ax.transAxes,
    fontsize=9,
)
plt.savefig(results_root / "cctv_model_selection_bubble_chart.png", dpi=180)
plt.savefig(results_root / "cctv_model_selection_bubble_chart.svg")
plt.show()
