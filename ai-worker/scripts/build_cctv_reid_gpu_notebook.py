from __future__ import annotations

import json
from pathlib import Path

OUTPUT = Path("output/jupyter-notebook/cctv_reid_gpu_comparison_20260728.ipynb")
JsonValue = str | int | None | list["JsonValue"] | dict[str, "JsonValue"]


def _markdown(source: str) -> dict[str, JsonValue]:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def _code(source: str) -> dict[str, JsonValue]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def main() -> None:
    cells = [
        _markdown(
            """# CCTV 다중 인물 ReID GPU 공정 비교

이 노트북은 사용자가 제공한 다중 인물 MOV와 공개 CHIRLA를 구분해서 다룹니다.

- **프로젝트 MOV**: 3개 영상에서 395개 사람 크롭·57개 tracker fragment를
  추출했습니다. IMG_3617의 10개 안정 트랙은 동일 카메라·동일 영상 시간 분리
  파일럿일 뿐, 일반화 증거가 아닙니다.
- **공개 CHIRLA**: 37명·16카메라·10시퀀스 중 gallery/query가 모두 있는
  11명, query 95개를 평가합니다.
- **엄격 프로토콜**: 각 query에 대해 같은 카메라 **또는** 같은 시퀀스의 gallery를 모두 제외합니다.

따라서 아래 결과는 서로 같은 조건의 공정 비교지만, 프로젝트 자체 교차 카메라
identity 정답이 아니므로 85% 달성으로 포장하지 않습니다.
"""
        ),
        _code(
            """from pathlib import Path
import json
import subprocess
import sys

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Image, display

ROOT = next(
    path
    for path in (Path.cwd(), *Path.cwd().parents)
    if (path / "experiments/results/cctv_generalization_method_matrix_20260728.json").is_file()
)
MATRIX_PATH = ROOT / "experiments/results/cctv_generalization_method_matrix_20260728.json"
AUDIT_PATH = ROOT / "experiments/results/chirla_protocol_audit_20260728.json"
PROJECT_PATH = ROOT / "experiments/results/project_track_heldout_clip_l14_hflip_max_20260728.json"
SOLIDER_RAW_PATH = (
    ROOT / "experiments/results/gpu_raw_20260728/chirla_solider_strict_none_topk3.json"
)
CHART_PATH = ROOT / "experiments/results/cctv_reid_bubble_20260728.png"

matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
project = json.loads(PROJECT_PATH.read_text(encoding="utf-8"))
solider = json.loads(SOLIDER_RAW_PATH.read_text(encoding="utf-8"))
"""
        ),
        _markdown("## 1. 데이터와 프로토콜 감사"),
        _code(
            """pd.DataFrame([
    {"항목": "전체 manifest 행", "값": audit["manifestRows"]},
    {"항목": "gallery/query 공통 identity", "값": audit["galleryQueryIdentityIntersection"]},
    {"항목": "평가 query", "값": audit["eligibleQueryCount"]},
    {
        "항목": "같은 카메라 positive가 있던 identity",
        "값": audit["identitiesWithSameCameraAcrossRoles"],
    },
    {"항목": "같은 카메라 positive가 있던 query", "값": audit["queriesWithSameCameraPositive"]},
    {"항목": "같은 시퀀스 positive가 있던 query", "값": audit["queriesWithSameSequencePositive"]},
    {
        "항목": "엄격 positive가 존재하는 query",
        "값": audit["strictCrossCameraSequenceEligibleQueries"],
    },
])
"""
        ),
        _markdown(
            """기존 gallery/query 방식에서는 95개 query 모두가 같은 시퀀스의
positive를 가지고 있었고, 29개는 같은 카메라 positive도 가지고 있었습니다.
그래서 기존 SOLIDER 64.21%는 **중복 허용 프록시**로만 보존하고,
모델 선택에는 사용하지 않습니다."""
        ),
        _markdown("## 2. 동일 엄격 프로토콜 모델 비교"),
        _code(
            """strict = pd.DataFrame([
    {
        "모델": row["name"],
        "계열": row["family"],
        "Rank-1(%)": round(row["rank1"] * 100, 2),
        "Recall@5(%)": round(row["recallAt5"] * 100, 2),
        "identity-MRR(%)": round((row.get("identityMrr") or 0) * 100, 2),
        "파라미터(M, 근사)": row["parameterMillionsApprox"],
    }
    for row in matrix["methods"]
    if row.get("metricUnit") == "frame"
    and row.get("protocol") == "strict-cross-camera-sequence"
])
strict.sort_values(["Rank-1(%)", "identity-MRR(%)"], ascending=False).reset_index(drop=True)
"""
        ),
        _markdown(
            """`identity-MRR`은 gallery crop을 identity별 한 점수로 먼저 집계한 뒤
정답 identity 순위의 역수를 평균한 값입니다. 원본 JSON의 `metrics.map`은
legacy 필드명이며, 표준 이미지 단위 ReID mAP가 아닙니다."""
        ),
        _code(
            """subprocess.run(
    [sys.executable, "scripts/plot_cctv_reid_bubble.py"],
    cwd=ROOT,
    check=True,
)
display(Image(filename=str(CHART_PATH)))
"""
        ),
        _markdown("## 3. 선택 후보의 query 단위 실패 분석"),
        _code(
            """ranking = pd.DataFrame(solider["query_rankings"])
rank_counts = (
    ranking["rank"]
    .value_counts()
    .sort_index()
    .rename_axis("정답 identity 순위")
    .reset_index(name="query 수")
)
display(rank_counts.head(12))

errors = ranking[ranking["rank"] > 1].copy()
errors["점수 차이"] = (errors["top1_score"] - errors["target_score"]).round(4)
display(
    errors[
        [
            "query_identity",
            "query_camera",
            "query_sequence",
            "rank",
            "top1_identity",
            "점수 차이",
            "query_path",
        ]
    ]
    .sort_values(["rank", "점수 차이"], ascending=[False, False])
    .head(20)
)
"""
        ),
        _markdown("## 4. 프로젝트 파일럿과 공개 엄격 평가를 분리해서 해석"),
        _code(
            """strict_metrics = solider["metrics"]
pd.DataFrame([
    {
        "평가": "프로젝트 MOV 동일 카메라·동일 트랙 시간 분리 파일럿",
        "identity/track 수": "수동 안정 트랙 10개",
        "Rank-1(%)": round(project["metrics"]["rank1"] * 100, 2),
        "일반화 판정": "불가",
    },
    {
        "평가": "CHIRLA 엄격 교차 카메라·시퀀스",
        "identity/track 수": (
            f'{strict_metrics["gallery_identity_count"]}명 / '
            f'query {strict_metrics["query_count"]}개'
        ),
        "Rank-1(%)": round(strict_metrics["rank1"] * 100, 2),
        "일반화 판정": "공개 프록시만 가능",
    },
])
"""
        ),
        _markdown(
            """## 결론

- 프로젝트 MOV 파일럿 100%는 한 영상 안의 트랙 검색 검증이며, 프로젝트 일반화 85% 증거가 아닙니다.
- 모델 비교는 같은 카메라·시퀀스를 모두 제외한 엄격 프로토콜만 사용합니다.
- 현재 배포 설정은 최상위 후보 검색용으로만 준비하고, 자동 `match`는 비활성화합니다.
- Sonnet 5는 속성 라벨 teacher 파일럿까지만 검증되었습니다. CHIRLA identity
  검색에 Sonnet을 적용한 실험은 수행하지 않았으므로 identity 개선 효과는
  미측정입니다.
"""
        ),
    ]
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    for index, cell in enumerate(cells):
        cell["id"] = f"cell-{index:02d}"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()

