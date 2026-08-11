# EyesOnU 평가 지표 정합성 및 개선 판정

작성일: 2026-08-11

## 결론

현재 숫자들은 모두 실제 파일에 기록된 값이지만, 같은 정확도를 뜻하지는 않는다. `Recall@5`, 엄격한 `Rank-1`, 공개 데이터셋 proxy, 속성 분류 정확도를 한 줄의 “전체 정확도”로 합치면 안 된다.

발표에서 객관적으로 확정할 수 있는 표현은 다음과 같다.

- 프로젝트 CCTV 후보 검색은 **Recall@5 100% point estimate**이다. 정방향 11/11, 영상 방향을 뒤집은 검증 14/14다. 다만 identity 8명, 단일 프로젝트 촬영 세트, 수작업 adjudicator 1명이며, 95% Wilson 하한은 각각 74.12%, 78.47%다.
- 프로젝트 identity 최우선 일치는 정방향 **Rank-1 81.82%(9/11)**, 역방향 **50.00%(7/14)**다. 따라서 100%를 identity 정확도라고 부를 수 없다.
- CHIRLA 공개 데이터는 **track-level Recall@5 87.50%(35/40)**로 기록되어 있다. 이는 프로젝트 CCTV가 아닌 공개 proxy다.
- v4 속성 모델은 성별·상의색·하의색·소매 길이의 평균 **88.50%**다. 15장 속성 분류 평가이며, CCTV identity 검색 지표가 아니다.
- 발표 자료의 “외부 실험 Recall@5 85%”는 현재 checkout의 원본 로그가 없어 `user_reported_external`로만 기록되어 있다. 원본 로그와 분모가 확보되기 전에는 검증 완료 수치로 표시하면 안 된다.

## 수치 대조표

| 주장 | 분자/분모 | 지표 단위 | 현재 판정 |
| --- | ---: | --- | --- |
| 외부 실험 85% | 확인 불가 | Recall@5라고 보고됨 | 원본 로그 미검증 |
| 프로젝트 CCTV 정방향 | 11/11 | track Recall@5 | 제한된 point estimate |
| 프로젝트 CCTV 역방향 | 14/14 | track Recall@5 | 방향성 확인용 point estimate |
| 프로젝트 CCTV 정방향 | 9/11 | strict track Rank-1 | 81.82%, 방향성 민감 |
| 프로젝트 CCTV 역방향 | 7/14 | strict track Rank-1 | 50.00%, 자동 1위 판정에 부적합 |
| CHIRLA 공개 proxy | 35/40 | track Recall@5 | 87.50%, 프로젝트 일반화 증거 아님 |
| v4 PAR | 속성별 평균 | attribute classification | 88.50%, identity와 별도 |

## GPU 실험에서 실제로 높아진 부분

MEVID 공개 데이터로 학습한 ArcFace·batch-hard triplet metric head를 붙인 probe는 프로젝트 CCTV 정방향 Rank-1을 **81.82%에서 90.91%(10/11)**로 올렸다. 그러나 역방향은 **50.00%에서 57.14%(8/14)**에 그쳤고, 실험 기록도 `promotionApproved=false`다.

Track frame pooling도 비교했다. `metric head + median`은 역방향 Rank-1 **64.29%**까지 보였지만 방향과 소수 샘플에 민감하다. 모든 pooling 방식에서 프로젝트 Recall@5는 이미 100%였으므로 Recall@5 자체는 더 높일 수 없다. 이 결과를 일반화 성능 향상으로 승격하지 않고, 현재 운영 후보 검색에는 mean pooling을 유지한다.

Sonnet 증류도 별도로 비교했다. PA-100K 속성 지표는 93.27%에서 94.32%로 +1.05%p 올라갔지만, CCTV group-heldout proxy는 85.64%에서 83.08%로 -2.56%p 내려갔다. 따라서 Sonnet 증류가 identity 검색을 높였다고 말할 근거는 없다.

## 왜 서로 다른 숫자가 나오는가

1. `Recall@5`는 정답 identity가 후보 5개 안에 들어갔는지를 본다. 1등인지까지 보지 않는다.
2. `Rank-1`은 후보 1등이 정확한지를 본다. 비슷한 사람을 2~5등에 넣어도 실패다.
3. frame 단위 평가와 여러 프레임을 합친 track 단위 평가는 난이도가 다르다.
4. 카메라·시간·영상 방향이 바뀌면 같은 사람의 외형이 달라진다.
5. v4 PAR은 색상·성별·소매 같은 속성을 맞추는 별도 분류 문제다. identity를 직접 검증하지 않는다.

## 최종 발표 권장 표기

```text
프로젝트 CCTV 후보 검색: Recall@5 100% (11/11, 제한된 cross-video point estimate)
프로젝트 strict identity Rank-1: 81.82% 정방향 / 50.00% 역방향
공개 CHIRLA track proxy: Recall@5 87.50% (35/40)
v4 PAR 속성 분류 평균: 88.50% (15장 속성 평가)
외부 Recall@5 85%: 원본 로그 확인 전에는 검증 전 수치로 별도 표기
```

이렇게 쓰면 100%를 과장하지 않으면서도 후보 검색 단계의 성과와 identity 1위 판정의 한계를 동시에 보여줄 수 있다.

## 다음 개선의 우선순위

Recall@5를 100%보다 높이는 것은 불가능하므로, 다음 목표는 Rank-1과 오탐·미탐이다.

1. 동일 인물을 최소 2개 카메라와 2개 시간대에서 촬영하고, distractor를 포함한 identity-heldout test를 만든다.
2. 정방향·역방향을 모두 고정하고, 최소 2명의 독립 검수자가 track identity를 판정한다.
3. train/validation/test identity를 분리한 뒤 metric head, hard-negative mining, camera-aware augmentation, track-level temporal pooling을 한 번에 하나씩 비교한다.
4. 최종 승격 조건은 untouched test에서 Rank-1, Recall@5, false-match rate, miss rate와 95% 신뢰구간 하한을 함께 통과하는 것으로 둔다.

현재 증거만으로는 metric head가 정방향 Rank-1을 높일 가능성은 확인됐지만, 일반화된 85% 이상 identity 판정 모델로 확정할 단계는 아니다. 추가 촬영 데이터 없이 숫자만 높이는 것은 평가 누수 또는 과적합을 만들 수 있다.

## 근거 파일

- `docs/evidence/project_cctv_cross_camera_gate_20260810.json`
- `docs/evidence/chirla_solider_track_evidence_20260810.json`
- `output/ai-presentation/external_recall5_result.json`
- `output/ai-presentation/v4_par_evidence.json`
- `experiments/results/cctv_generalization_method_matrix_20260728.json`
- `experiments/results/solider_ft_sonnet_comparison_20260724.json`
