# 실험 의사결정 로그

## 1. 역할별 비교로 시작

속성 proxy와 ReID는 같은 정확도 칸에 넣지 않았습니다. 속성 후보는 공통 속성 schema와 group-heldout 조건에서 비교했고, ReID는 같은 카메라·같은 시퀀스 gallery를 제외하는 strict 조건에서 별도로 비교했습니다.

| 비교 범위 | 후보 | 관측값 | 해석 |
| --- | --- | --- | --- |
| 현재 local 속성 proxy | PA-100K 100-image subset | 6개 필드별 top-1 평균 `0.7267` | external mA·InsF1, CCTV identity, track-level 성능과 동등하지 않음 |
| historical 45 crop·33 group 속성 proxy | CLIP ViT-L/14 | attribute score `0.414`, p95 `4.141s` | 현재 선택 기준이 아닌 과거 proxy 후보 비교 |
| 같은 historical proxy | Qwen3-VL-2B | attribute score `0.393`, p95 `8.298s` | 생성형 결과의 구조·지연시간을 함께 확인한 비교값 |
| strict cross-camera·sequence ReID | SOLIDER-ReID Swin-B Top-3 mean | Rank-1 `0.4737`, Recall@5 `0.7789`, MRR `0.6074` | Top-K 후보 검색만 허용, 자동 identity match는 차단 |

`invalid_runtime`, `invalid_output`, `pending` 상태는 점수 0으로 바꾸지 않습니다. 실행되지 않았거나 출력 계약을 만족하지 못한 후보는 측정 후보 표에서 분리하고, 원인과 다음 검증 조건을 남깁니다.

## 2. 이전보다 엄격한 결과를 채택

동일 카메라·시퀀스가 섞인 overlap 비교에서는 더 높은 수치가 있었지만, 그것을 자동 매칭 근거로 사용하지 않았습니다. strict 조건으로 다시 측정한 SOLIDER 결과가 현재 기준이며, Rank-1 `0.85`, Recall@5 `0.95`, false-match 조건을 모두 만족하는 독립 heldout 검증 전까지 `automaticIdentityMatch = BLOCKED`입니다.

현재 runtime도 `provisional`이며 `productionApproved = false`입니다. 사람 검토 identity 정답은 원래 source track에서만 유효하고, cross-camera identity ground truth는 없습니다. 따라서 Top-K retrieval-only 제한을 runtime에서 유지하고, 생성형 모델을 primary classifier나 자동 fallback으로 두지 않습니다.

## 3. 다음 루프

1. 동일인을 교차 카메라 또는 이벤트에서 독립 검토한 manifest를 만든다.
2. group·track·시간 누수를 검사하고, test split에는 augmentation을 허용하지 않는다.
3. 후보 하나의 변경만 적용해 strict ReID와 속성 track-level 지표를 다시 측정한다.
4. 사람 검토와 provenance를 포함한 evidence를 gate에 넣는다.
5. 통과하지 못하면 수치를 해석해 다음 후보·규칙·데이터 계약으로 되돌린다.
