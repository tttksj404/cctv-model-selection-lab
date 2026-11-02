
from __future__ import annotations

import argparse
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _safe_notebook_output(value: Path) -> Path:
    candidate = (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value.resolve()
    experiments_root = PROJECT_ROOT / "experiments"
    if candidate.parent != experiments_root or candidate.suffix.lower() != ".ipynb" or not candidate.stem.startswith("cctv_person_crop_comparison"):
        raise SystemExit("--output must be a cctv_person_crop_comparison*.ipynb file directly under experiments")
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(description="사람 전체 크롭과 원본 CCTV 입력을 비교하는 한글 노트북을 생성합니다.")
    parser.add_argument("--output", type=Path, default=Path("experiments/cctv_person_crop_comparison.ipynb"))
    parser.add_argument("--execute", action="store_true", help="생성한 노트북을 현재 프로젝트 커널로 실행합니다.")
    args = parser.parse_args()

    cells = [
        nbf.v4.new_markdown_cell("\n".join([
            "# CCTV 사람 전체 크롭 입력 비교",
            "",
            "**목적:** 사람 주변의 바닥, 벽, 차량, 다른 사람 같은 방해물이 속성 판정에 영향을 주는지 확인한다. 같은 45개 이미지, 같은 target, 같은 모델 런타임에서 원본 입력과 person_only 입력을 paired 비교했다.",
            "",
            "**핵심 결론:** 크롭은 CLIP ViT-L/14와 ViT-B/32에서는 후보지만 모든 모델에 공통으로 유리하지 않다. 따라서 현재 proxy 결과만으로 전체 백엔드의 기본 입력을 크롭으로 바꾸지 않고, CLIP ViT-L/14 검색 branch에서만 person crop을 검증 후보로 둔다.",
        ])),
        nbf.v4.new_code_cell("\n".join([
            "import hashlib",
            "import json",
            "from pathlib import Path",
            "",
            "comparison = json.loads(Path('experiments/results/cctv_person_crop_comparison.json').read_text(encoding='utf-8'))",
            "def sha256_file(path):",
            "    digest = hashlib.sha256()",
            "    with path.open('rb') as handle:",
            "        for chunk in iter(lambda: handle.read(1024 * 1024), b''):",
            "            digest.update(chunk)",
            "    return digest.hexdigest()",
            "",
            "for item in comparison['models']:",
            "    provenance = item['provenance']",
            "    assert provenance['original_result_sha256'] == sha256_file(Path('experiments/results') / provenance['original_result'])",
            "    assert provenance['crop_result_sha256'] == sha256_file(Path('experiments/results') / provenance['crop_result'])",
            "assert comparison['provenance']['analysis_script']['sha256'] == sha256_file(Path(comparison['provenance']['analysis_script']['path']))",
            "assert comparison['provenance']['crop_manifest']['sha256'] == sha256_file(Path(comparison['provenance']['crop_manifest']['path']))",
            "assert comparison['provenance']['crop_summary']['sha256'] == sha256_file(Path(comparison['provenance']['crop_summary']['path']))",
            "assert comparison['provenance']['build_script']['sha256'] == sha256_file(Path(comparison['provenance']['build_script']['path']))",
            "assert Path('experiments/results/cctv_person_crop_comparison.png').is_file()",
            "print('provenance_freshness: PASS')",
        ])),
        nbf.v4.new_code_cell("\n".join([
            "import json",
            "from pathlib import Path",
            "import pandas as pd",
            "",
            "comparison = json.loads(Path('experiments/results/cctv_person_crop_comparison.json').read_text(encoding='utf-8'))",
            "rows = []",
            "for item in comparison['models']:",
            "    rows.append({",
            "        '모델': item['model'],",
            "        '원본 속성 정확도(%)': item['original']['attribute_accuracy'] * 100,",
            "        '사람 전체 crop 정확도(%)': item['person_only_crop']['attribute_accuracy'] * 100,",
            "        '변화(%p)': item['delta']['attribute_accuracy_pp'],",
            "        '그룹 bootstrap 95% CI(%p)': str([round(value, 2) for value in item['delta']['bootstrap_95ci_pp_by_group']]),",
            "        '원본 p95(s)': item['original']['latency_s_p95'],",
            "        'crop p95(s)': item['person_only_crop']['latency_s_p95'],",
            "        '판정': item['default_candidate'],",
            "    })",
            "summary_df = pd.DataFrame(rows).sort_values('사람 전체 crop 정확도(%)', ascending=False)",
            "summary_df.round(2)",
        ])),
        nbf.v4.new_markdown_cell("\n".join([
            "## 실험 계약",
            "",
            "- 데이터: Simuletic 15개와 PA-100K 30개, 총 45개 paired 입력과 33개 identity/group 단위.",
            "- 입력: 원본 이미지와 동일 이미지에서 Faster R-CNN person box + 5% margin으로 생성한 사람 전체 crop.",
            "- 판정: target에 값이 있는 속성만 micro attribute accuracy로 채점.",
            "- 모델: CLIP ViT-L/14, CLIP ViT-B/32, SigLIP base, BLIP base, Qwen3-VL-2B.",
            "- 공정성: 원본과 crop 모두 transformers 5.14.1로 실행.",
            "- 불확실성: 이미지 단위가 아닌 dataset-group cluster bootstrap 10,000회.",
            "- 제한: 현재는 CCTV identity track-heldout 라벨이 아니라 속성 proxy이며, 실제 사람 2명 독립 주석과 adjudication이 아직 없다.",
        ])),
        nbf.v4.new_code_cell("\n".join([
            "from IPython.display import Image, display",
            "",
            "display(Image(filename='experiments/results/cctv_person_crop_comparison.png'))",
        ])),
        nbf.v4.new_markdown_cell("\n".join([
            "## 모델별 결과 해석",
            "",
            "CLIP ViT-L/14는 전체 micro 정확도가 원본보다 상승했지만, 이 효과가 실제 identity 성능 상승을 의미하지는 않는다. PA-100K처럼 입력 자체가 이미 사람 중심인 데이터에서는 crop 이득이 작거나 사라질 수 있다. 반대로 Qwen3-VL-2B는 crop에서 속성 정확도와 structured valid rate가 함께 낮아졌으므로 백엔드 의미 분석의 기본 입력은 원본을 유지한다.",
            "",
            "따라서 person_only는 전역 기본값이 아니라, 임베디드/검색 CLIP branch의 후보 생성 입력으로 먼저 A/B 검증한다. 낮은 detector score나 작은 crop에서는 원본을 유지하는 fallback을 둔다.",
        ])),
        nbf.v4.new_code_cell("\n".join([
            "dataset_rows = []",
            "for item in comparison['models']:",
            "    for dataset, delta in item['delta']['dataset_accuracy_pp'].items():",
            "        dataset_rows.append({'모델': item['model'], '데이터셋': dataset, '변화(%p)': delta})",
            "pd.DataFrame(dataset_rows).pivot(index='모델', columns='데이터셋', values='변화(%p)').round(2)",
        ])),
        nbf.v4.new_code_cell("\n".join([
            "field_rows = []",
            "for item in comparison['models']:",
            "    for field, delta in item['delta']['field_accuracy_pp'].items():",
            "        field_rows.append({'모델': item['model'], '속성': field, '변화(%p)': delta})",
            "pd.DataFrame(field_rows).pivot(index='모델', columns='속성', values='변화(%p)').round(2)",
        ])),
        nbf.v4.new_code_cell("\n".join([
            "crop_generation_df = pd.DataFrame([",
            "    {'데이터셋': dataset, **values}",
            "    for dataset, values in comparison['crop_generation']['person_score'].items()",
            "])",
            "crop_generation_df.round(3)",
        ])),
        nbf.v4.new_markdown_cell("\n".join([
            "## 기본 입력 정책과 다음 gate",
            "",
            "현재 proxy 기준 기본 정책은 다음과 같다.",
            "",
            "1. CLIP ViT-L/14 검색 branch: person crop을 후보로 유지하되, 원본+crop late fusion과 함께 재검증한다.",
            "2. Qwen 백엔드 branch: 원본을 기본 입력으로 유지하고, 필요할 때 person crop을 보조 입력으로 전달한다.",
            "3. detector score가 낮거나 crop 면적이 비정상적으로 작으면 원본으로 fallback한다.",
            "4. 실제 CCTV track-heldout identity 라벨이 확보되면 identity top-1, false accept/reject, track-level attribute consistency, latency를 동일 track split에서 다시 측정한다.",
            "",
            "최종 production default 변경은 실제 CCTV identity gate를 통과한 뒤에만 허용한다.",
        ])),
    ]
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11+"},
        "dependencies": {
            "python": ">=3.11",
            "packages": ["nbformat", "nbclient", "ipykernel", "pandas", "matplotlib", "numpy"],
        },
    }
    output = _safe_notebook_output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.execute:
        NotebookClient(notebook, timeout=600, kernel_name="python3").execute(cwd=str(PROJECT_ROOT))
    nbf.write(notebook, output)
    print(output)


if __name__ == "__main__":
    main()
