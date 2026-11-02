# Model comparison manual QA

<verdict>PASS</verdict>

최종 canonical 산출물 기준으로 확인했다. 동일한 45개 person-crop proxy(Simuletic 15 + PA-100K 30)를 사용한 유효 측정 모델만 `proxyRuntime` 버블차트에 포함한다. Florence-2 두 후보는 `invalid_runtime`으로 `failedCandidates`에 보존하고, Qwen3.5-9B·Qwen2.5-VL-7B의 공정 base/LoRA 비교는 `pending_remote_auth`로 보류한다.

## manual QA

| 검증 | 결과 | 근거 |
|---|---|---|
| JSON/CSV 구조·행 수 | PASS | 25개 JSON 파싱, proxyRuntime 5개, PA-100K 3개, non-comparable 2개, Qwen pending 4개, CSV 데이터 14행 |
| 동일 입력·속성 계약 | PASS | proxy 45개 입력, 공통 9개 속성, 285개 라벨 필드, 데이터셋 구성 15+30 |
| 최신 유효 모델 | PASS | Qwen3-VL-2B, CLIP ViT-B/32, CLIP ViT-L/14, SigLIP base, BLIP base |
| 실패 후보 분리 | PASS | Florence-2-large 및 Florence-2-large-ft는 `invalid_runtime`; 측정 점수로 차트에 포함하지 않음 |
| 서버 후보·공정 미세조정 분리 | PASS | Qwen3.5-9B·Qwen2.5-VL-7B는 모두 `pending_remote_auth`/미측정이며 x/y=null |
| 노트북 렌더링 | PASS | 15 cells, 7 code cells, 저장된 오류 0개, 한글 메인 PNG 직접 확인 |
| CLI·코드 품질 | PASS | `--help` exit 0, Ruff 통과, 관련 pytest 66개 통과 |

## 최신 proxyRuntime 좌표

| 모델 | 속성 정확도 x | p95 지연 y(초) | 상태 |
|---|---:|---:|---|
| CLIP ViT-L/14 | 41.40% | 4.141 | measured |
| Qwen3-VL-2B | 39.30% | 8.298 | measured |
| CLIP ViT-B/32 | 38.60% | 0.723 | measured |
| SigLIP base | 24.21% | 0.778 | measured |
| BLIP base | 20.35% | 0.468 | measured |

## 해석 경계

- 이 차트는 CCTV 실종자 동일인 식별 정확도가 아니라, 45개 person-crop proxy의 부분 라벨 속성 정확도와 실행 지연 비교다.
- p95는 측정된 요청 지연의 95백분위이며, y축은 낮을수록 빠르다.
- 가장 높은 proxy 속성 정확도는 CLIP ViT-L/14지만 41.40%에 불과하다. 이 결과만으로 85% 이상 또는 운영 배포를 주장할 수 없다.
- Florence 실패·Qwen pending을 measured로 해석하지 않는다.

## 근거 파일

- `experiments/results/model_comparison_bubble_data.json`
- `experiments/results/model_comparison_bubble_coordinates.csv`
- `experiments/model_comparison_bubble_chart.ipynb`
- `experiments/results/model_comparison_proxy_runtime_bubble.png`
- `experiments/results/florence-2-large.json`
- `experiments/results/florence-2-large-ft.json`

EXIT_CODE=0
