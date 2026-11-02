# SOLIDER CCTV 속성 학습 실험 기록

## 목적

PA-100K로 초기 학습한 SOLIDER Swin-B + 26속성 head에 CCTV와 유사한 보행자 자료를 추가하고, 가중 BCE, Asymmetric Loss, Sonnet 보조 라벨, 라벨 공출현 그래프 정규화를 비교한다. 모든 결과는 PA-100K 공식 split과 Simuletic identity group-heldout split을 함께 기록한다.

## 데이터 확보 및 한계

- 추가 자료: [Simuletic CCTV-Pedestrian-1K](https://huggingface.co/datasets/Simuletic/CCTV-Pedestrian-1K-Person-Attribute-Dataset)
- 카드 기준 고각 CCTV 보행자 이미지와 속성 메타데이터를 사용했다.
- 인증 다운로드 결과: 메타데이터 1,005행, PNG 963개, 누락 37개, 유효 identity group 39개.
- Simuletic의 `top_color`, `bottom_color`, `hair`, `age`, `angle`, `top_type`, `bottom_type`, `footwear`는 현재 PA-100K 26출력 ontology에 직접 매핑하지 않았다. 따라서 아래 속성 정확도는 26속성 중 유효 mask가 있는 필드만 계산한다.
- 데이터 카드의 라이선스 표기가 제목과 본문에서 일치하지 않으므로 연구용 실험 자료로만 사용하고, 상업 배포 전에는 원저작자와 원천 데이터의 라이선스를 별도 확인한다.
- 본 자료는 실제 프로젝트의 실종자 identity/track-heldout 데이터가 아니다. 따라서 아래 85% 이상 수치는 실제 신원 판별 정확도 주장이 아니라 속성 proxy 결과다.

## 공통 평가

- PA-100K: 공식 train/validation/test split, test mA와 instance F1.
- Simuletic: identity 기준 60% train, 20% validation, 20% group-heldout test.
- `Simu group-heldout`: 학습에 등장하지 않은 identity의 속성 정확도.
- `group exact`: 한 identity group의 모든 유효 속성을 동시에 맞힌 비율.
- `image held-out`은 같은 identity의 다른 프레임이 섞일 수 있으므로, 모델 선택의 주 지표는 group-heldout이다.

## 200장 파일럿 결과

| 방법 | PA test mA | PA InsF1 | Simu 전체 | 이미지 held-out | 그룹 held-out | 그룹 exact |
|---|---:|---:|---:|---:|---:|---:|
| base_pa_head | 74.29% | 84.90% | 81.06% | 84.35% | 85.59% | 25.00% |
| mixed_weighted_bce | 75.40% | 85.60% | **93.50%** | **88.70%** | **91.60%** | 25.00% |
| mixed_asl | 75.41% | 85.71% | 89.77% | 88.48% | 89.73% | **37.50%** |
| mixed_asl_sonnet | **75.48%** | **85.77%** | 89.86% | 88.26% | 89.73% | **37.50%** |

## 963장 부분집합 결과

| 방법 | PA test mA | PA InsF1 | Simu 전체 | 이미지 held-out | 그룹 held-out | 그룹 exact |
|---|---:|---:|---:|---:|---:|---:|
| base_pa_head | 74.29% | 84.90% | 82.87% | 86.31% | 87.26% | 35.90% |
| mixed_weighted_bce | 75.22% | 85.88% | **92.22%** | **91.73%** | **93.15%** | **53.85%** |
| mixed_asl | **75.78%** | **85.88%** | 87.95% | 89.11% | 90.91% | 38.46% |
| mixed_asl_sonnet | 75.49% | 85.60% | 87.70% | 89.02% | 90.45% | 35.90% |

## 추가 방법 결과

| 방법 | PA test mA | PA InsF1 | Simu 전체 | 이미지 held-out | 그룹 held-out | 그룹 exact |
|---|---:|---:|---:|---:|---:|---:|
| mixed_asl_graph | 75.49% | 85.95% | 87.88% | 89.26% | 90.86% | 38.46% |
| backbone_finetune | **82.81%** | **89.80%** | 88.06% | **90.23%** | 92.23% | 51.28% |

`mixed_asl_graph`는 ML-GCN 논문 아이디어에서 출발한 공출현 정규화 ablation이지만, 이번 데이터에서는 weighted BCE보다 좋아지지 않았다. `backbone_finetune`은 PA-100K test 보존 성능과 Simuletic 일반화가 함께 상승했지만, group-heldout 속성 정확도만으로 frozen mixed weighted BCE를 넘지는 못했다.

원자료는 [963장 summary JSON](results/solider_simuletic_method_sweep_partial963_summary_20260727.json)에 저장했다. 기존 200장과 963장 결과를 한 번에 보는 버블차트 입력은 [bubble data JSON](results/solider_simuletic_method_sweep_bubble_data.json), 재현용 노트북은 [bubble chart notebook](simuletic_method_sweep_bubble_chart.ipynb)이다.

## 논문 기반 추가 방법

1. Asymmetric Loss: 다중 레이블에서 쉬운 음성 샘플의 영향이 과도해지는 문제를 줄였다. 963장 group-heldout에서는 weighted BCE보다 낮았지만 PA test mA는 가장 높았다.
2. Sonnet response-level 보조 라벨: API 응답을 26개 라벨로 정규화해 보조 BCE로 사용했다. logit KD가 아니며, 해당 API 학습 사용 권한과 데이터 정책은 별도 확인 대상이다. 963장에서는 weighted BCE를 개선하지 못했다.
3. 라벨 공출현 그래프 정규화: ML-GCN 계열의 아이디어를 작은 ablation으로 추가했다. PA-100K train 라벨의 공출현 transition을 만들고 Simuletic 유효 라벨에 약한 graph consistency loss를 적용한다. 이는 full ML-GCN 구현이 아니라 재현 가능한 비교용 변형이며, GPU 2에서 별도 실행 중이다.
4. 전체 백본 파인튜닝: head만 학습하는 실험과 분리해 SOLIDER Swin-B 전체를 PA-100K weighted BCE + Simuletic masked ASL로 미세조정한다. GPU 0에서 실행 중이다.

## 현재 판단

- 현 단계의 속성 proxy만 보면 963장 `mixed_weighted_bce`가 group-heldout 93.15%, group exact 53.85%로 가장 실용적인 후보다.
- PA-100K 보존 성능과 Simuletic 일반화 사이에는 trade-off가 있다. frozen head 기준 `mixed_asl`은 PA test mA가 75.78%로 가장 높지만 Simuletic group-heldout은 90.91%다. 백본까지 미세조정하면 PA test mA 82.81%, InsF1 89.80%까지 올라간다.
- Sonnet을 추가한다고 자동으로 좋아지지 않는다. 현재 실험에서는 weighted BCE가 Sonnet 보조학습보다 우수하다.
- 운영 후보는 두 가지로 남긴다. 속성 proxy 최대치는 `mixed_weighted_bce`, PA-100K 보존과 백본 적응을 중시하는 후보는 `backbone_finetune`이다. 실제 CCTV identity held-out에서 다시 비교하기 전에는 하나를 최종 확정하지 않는다.
- 실제 프로젝트 최종 모델을 확정하려면 실제 여러 identity의 gallery, 시간·카메라가 분리된 held-out CCTV, distractor, track label이 필요하다. 현재 MOV manifest는 identity label이 없어 production gate를 통과하지 못한다.

## 실행 흔적

- 원격 작업 디렉터리: `~/qwen3vl-backend/gpu_distill_transfer`
- GPU 0: `experiments/results/solider_simuletic_backbone_finetune_partial963.log`
- GPU 1: `experiments/results/solider_simuletic_method_sweep_partial963.json`
- GPU 2: `experiments/results/solider_simuletic_method_sweep_graph_partial963.log`
- 원격 환경: PyTorch 2.6.0+cu124, L40S 4장, CUDA 사용 가능.
