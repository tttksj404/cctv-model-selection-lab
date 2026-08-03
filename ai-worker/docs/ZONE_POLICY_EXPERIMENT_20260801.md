# 구역 확률·카메라 선택 정책 실험 결과 (2026-08-01)

## 최종 선택

운영 기본값은 **검증된 모델 점수의 likelihood ratio 변환 + 6상태 posterior +
posterior 가중 카메라 선택 + 정보이득 동점 해소**로 확정했다.

`SOLIDER/Qwen 점수 → calibration base-rate 제거 LR → track 중복 제거 →
zone-1..4/outside/unknown 갱신 → zone posterior × 카메라 운영계수 순위 → EIG tie-break`

여기서 모델 판단과 알고리즘은 다음처럼 섞는다. SOLIDER Re-ID, Qwen/Sonnet 계열의
인상착의 판단, 별도 속성 head는 각각 독립 validation에서 확률 보정을 마친
`reid`·`semantic`·`attribute` 신호로만 들어온다. 각 신호의 calibration base rate를
제거한 log-LR을 reliability 가중 평균하고 track 품질을 곱한다. 모델·보정기·manifest
SHA-256과 검증 표본 수가 있어도 신뢰 레지스트리의 정확한 tuple과 일치하지 않으면
API가 422로 거절한다. 현재 레지스트리는 PRID2011 proxy Re-ID만 개발·테스트 환경에
허용하며, Qwen/Sonnet semantic 신호는 실제 보정 artifact를 등록하기 전까지 차단한다.
따라서 생성형 모델의 문장형 확신이나 원시 similarity가 구역 확률을 직접 덮어쓰지 못한다.
카메라 MATCH/NO_MATCH likelihood는 validation 선택군에서 고정한 신뢰도 `0.40`을
지수로 적용한다. 한 카메라의 오탐·미검출이 독립이고 완전한 증거인 것처럼 posterior를
과도하게 움직이는 것을 막기 위한 보수적 power-likelihood다.

순수 EIG 정책은 유지해 비교했지만 최종 기본값으로 선택하지 않았다. 선택군과 밀봉
테스트군을 다른 seed로 분리했고, 배포 코드가 반환한 `nextCameraId`를 재구현 없이
그대로 실행한 정책이 해결률과 Top-1에서 가장 안정적이었기 때문이다.

## 실제 공개 ReID 근거

GPU 서버에서 회수한 PRID2011 cross-camera sealed 결과는 다음과 같다.

| 지표 | 결과 |
|---|---:|
| known query | 100 |
| distractor query | 148 |
| known Rank-1 | 90.0% |
| known Recall@5 | 95.0% |
| distractor false-match rate | 13.51% |
| 전체 자동판정 정확도 | 79.03% |

따라서 현 모델은 **후보 검색 Top-K**에는 쓸 수 있지만, distractor까지 포함한 자동
동일인 확정 85% 근거는 없다. 이 한계를 숨기기 위해 project CCTV 수치로 바꾸거나
validation 결과를 test 결과로 쓰지 않는다.

원본 근거는
[`prid2011_solider_open_set_v3_revalidated_summary.json`](../experiments/results/evidence/prid2011_solider_open_set_v3_revalidated_summary.json)이며,
해시는 replay 결과 JSON에 기록했다.

## 4구역 paired replay (역사적 v1, 최종 판정에 사용하지 않음)

이 절은 seed `20260801`로 수행한 초기 탐색 기록이다. 아래 최종 v3 replay가 이 결과를
대체했으므로 정책 승격이나 현재 런타임 판정의 근거로 사용하지 않는다.

- 모델 임베딩·공개 ReID 근거 생성: 인증된 Jupyter GPU 서버의 NVIDIA L40S 환경
- 정책 replay: GPU가 필요 없는 deterministic CPU 계산이며 이번 수정본을 로컬에서
  같은 seed로 재생성
- seed: `20260801`
- 독립 episode: 3,000개
- cohort: 정책 선택 1,500개 + 밀봉 테스트 1,500개(서로 다른 seed offset)
- 비교 정책: 고정 대표 카메라, 실제 배포 `nextCameraId`, 순수 EIG
- 상황: 예상 위치 확실/불확실, 현재 관할, 녹화본 또는 관할 밖
- stress: validation 보수값, 저하 카메라, 가림 stress
- 동일 episode의 카메라 상태와 관측 난수를 세 정책에 똑같이 사용

| 정책 | 예산 내 해결 | 최종 상태 Top-1 | 잘못된 구역 집중 | 평균 해결 scan |
|---|---:|---:|---:|---:|
| 고정 대표 카메라 | 60.53% | 78.20% | 0.87% | 4.230 |
| **실제 배포 정책** | **62.07%** | **80.07%** | 0.60% | **4.141** |
| 순수 EIG | 61.93% | 79.67% | **0.53%** | 4.147 |

배포 정책은 밀봉군에서 고정 정책 대비 예산 내 해결 `+1.53%p`, 최종 Top-1
`+1.87%p`, 평균 해결 scan `-0.089`, 잘못된 구역 고확신 `-0.27%p`였다.
순수 EIG의 오집중률은 0.53%로 더 낮지만 해결률·Top-1·평균 scan이 배포 정책보다
각각 근소하게 불리해 기본값에서 제외했다. 선택군에서도 배포 정책은 고정 정책 대비
해결률·오집중률·평균 scan을 모두 개선했으며, 검증기는 선택군 또는 밀봉군에서
오집중률이 baseline보다 악화되면 실패한다.

전체 결과와 12개 cell별 수치는
[`zone_policy_replay_20260801.json`](../experiments/results/zone_policy_replay_20260801.json)에
있다. 이 초기 replay에 대응하는 mission validator 산출물은 별도로 보존하지 않았다.
현재의
[`zone_policy_risk_mission_validation_20260801.json`](../experiments/results/zone_policy_risk_mission_validation_20260801.json)은
seed `20260806` 최종 v3 replay만 검증하며 이 초기 결과와 연결하지 않는다.
라이브 API의 세 가지 실패 가설과 curl 관측값은
[`zone_policy_runtime_audit_20260801.json`](../experiments/results/zone_policy_runtime_audit_20260801.json)에
기록했다.

## Hybrid EIG 확대 실험과 승격 기각 (역사적 v2, 2026-08-02)

이 절의 seed `20260802` 결과도 후보 폭을 넓히기 위한 중간 실험이다. 최종 승격 판정은
아래 seed `20260806` v3 원시 paired 증거 재검산만 사용한다.

`deployed_runtime`의 효용과 EIG를 정규화해 각각 25%, 50%, 75% 비중으로 섞은 세 정책을
추가했다. 같은 episode의 카메라 상태·관측 난수를 여섯 정책에 공유하고, seed를
`20260802`로 바꿔 selection 6,000회와 sealed 6,000회를 다시 실행했다.

| 정책 | sealed 해결률 | sealed Top-1 | 잘못된 구역 집중 | 평균 해결 scan |
|---|---:|---:|---:|---:|
| **기존 배포 정책** | 61.350% | 79.233% | **0.933%** | 4.2067 |
| Hybrid EIG 25% | **61.367%** | **79.350%** | 0.967% | **4.2057** |
| Hybrid EIG 50% | 61.350% | **79.350%** | 0.950% | 4.2043 |
| Hybrid EIG 75% | 61.317% | 79.183% | 0.967% | 4.2063 |
| 순수 EIG | 61.267% | 78.900% | 0.983% | 4.2093 |

selection의 점 추정 순위는 Hybrid EIG 25%가 1위였지만, sealed paired 해결률 차이는
`+0.0167%p`이고 95% 신뢰구간은 `-0.0698%p ~ +0.1031%p`로 0을 포함했다. Top-1,
오집중률, 평균 scan 차이의 신뢰구간도 모두 0을 포함했다. 따라서
`proxyMaterialImprovementOverDeployedConfirmed=false`로 판정하고 **런타임은 기존
`deployed_runtime`을 유지**한다. 작은 점 추정 차이만으로 카메라 정책을 바꾸지 않는 것이
현재 증거에서 가장 안전하다.

확대 artifact는
[`zone_policy_hybrid_replay_large_20260802.json`](../experiments/results/zone_policy_hybrid_replay_large_20260802.json)이며,
각 Hybrid의 기존 배포 정책 대비 paired 차이와 95% 구간을 포함한다.

## 탐지위험·Bayes 목적함수 확대 실험과 런타임 유지

카메라 운영계수에 포함된 freshness·route-centrality와 실제 관측 발생확률의 차이를
검증하기 위해 다음 여섯 후보를 추가했다.

- posterior × sensitivity × recording coverage × health인 기대 탐지 정책
- 오탐 노출을 `0.5`, `1.0`, `2.0` 배로 차감한 위험보정 탐지 정책
- 다음 MATCH/NO_MATCH 후 기대 Bayes Top-1 정확도를 최대화하는 정책
- 다음 관측 후 posterior가 `0.55`를 넘을 기대값을 최대화하는 정책

두 번의 1,500회/봉인군 파일럿 뒤 후보 정의를 동결하고, 독립 seed `20260806`에서
selection 6,000회와 sealed 6,000회를 실행했다. 총 12개 정책은 같은 episode 안에서
카메라 상태와 관측 난수를 공유했다.

| 정책 | sealed 해결률 | sealed Top-1 | 잘못된 구역 집중 | 평균 해결 scan |
|---|---:|---:|---:|---:|
| **기존 배포 정책** | 61.433% | 79.283% | 0.933% | 4.2017 |
| 기대 탐지 | 61.450% | 79.200% | 0.983% | 4.1972 |
| 위험보정 0.5 | 61.433% | 79.117% | 0.967% | 4.1980 |
| 위험보정 1.0 | 61.467% | 78.917% | 0.967% | 4.1975 |
| 위험보정 2.0 | 61.400% | 78.650% | 0.967% | 4.2038 |
| 기대 Bayes Top-1 | 60.083% | 79.150% | 0.983% | 4.2717 |
| 기대 0.55 해소 | 61.033% | 78.933% | **0.900%** | 4.2107 |
| Hybrid EIG 25% | 61.450% | **79.400%** | 0.967% | 4.2012 |
| Hybrid EIG 50% | 61.433% | **79.400%** | 0.950% | 4.1998 |
| Hybrid EIG 75% | 61.383% | 79.217% | 0.967% | 4.2020 |
| 순수 EIG | 61.333% | 78.933% | 0.983% | 4.2052 |
| 고정 대표 카메라 | 59.717% | 77.850% | **0.867%** | 4.3075 |

selection 승자는 Hybrid EIG 25%였지만, selection 자체의 기존 정책 대비 해결률 차이는
`+0.0167%p`이고 paired 95% 신뢰구간은 `-0.0698%p ~ +0.1031%p`였다. selection
Top-1 차이도 `-0.1500%p`, 95% 신뢰구간 `-0.3432%p ~ +0.0432%p`로 승격 조건을
통과하지 못했다.

독립 sealed에서도 해결률 차이는 `+0.0167%p`, paired 95% 신뢰구간은
`-0.0698%p ~ +0.1031%p`였다. Top-1 차이 `+0.1167%p`의 95% 구간도
`-0.0925%p ~ +0.3258%p`로 0을 포함했고, 잘못된 구역 집중은 `+0.0333%p`였다.
승격은 selection과 sealed의 세 조건을 모두 통과해야 하며, 이를 만족한 후보가 없으므로
`selectedRuntimePolicy`는 기존
`lr_hmm_posterior_weighted_coverage_eig_tiebreak`를 유지한다.
CI 경계는 artifact에 반올림 전 `float`로 기록하고 그 원값으로 승격을 판정한다.
따라서 (10^{-7}) 수준의 악화값이 표시용 반올림으로 `0.0`이 되어 통과하는 경로가
없다. validator는 CI뿐 아니라 episode 수, aggregate 지표, operating point와 paired
interval 전체에서 `bool`·숫자 문자열·비유한 값을 숫자로 인정하지 않는다. 원인·프로젝트
CCTV 증거 플래그를 `true`로 변조해도 검증에 실패한다. 생성기와 validator 모두 통계
게이트를 통과한 정책이 실제 런타임 구현 목록에 없으면 기존 배포 정책을 유지하거나
`promoted_policy_has_runtime_implementation=false`로 실패시킨다. 실험용 정책 ID만으로
프로덕션 승격을 통과할 수 없다.

공개 ReID 입력 증거는 JSON 의미 내용을 정렬·정규화한 canonical SHA-256
`1b898f6d4a9bc6fe185e0e38c7cb971a5293df0e997f3b5738681f37b07df152`로 고정한다.
validator는 허용된 `experiments/results/evidence` 경로, 원본 schema/status,
canonical hash와 Rank-1·Recall@5·distractor 지표를 모두 다시 대조한다. Windows의
CRLF와 Git blob의 LF 차이는 더 이상 증거 해시를 바꾸지 않는다.

파일럿과 최종 결과는 각각
[`zone_policy_risk_replay_pilot_20260801.json`](../experiments/results/zone_policy_risk_replay_pilot_20260801.json),
[`zone_policy_bayes_replay_pilot_20260801.json`](../experiments/results/zone_policy_bayes_replay_pilot_20260801.json),
[`zone_policy_risk_replay_large_20260801.json`](../experiments/results/zone_policy_risk_replay_large_20260801.json)에
기록했다. selection paired 비교와 양쪽 신뢰구간 게이트를 포함한 최종 artifact의
canonical JSON SHA-256은
`5f23698edcceb17c3dfd1cd1154bc462a494cc1902babd9e6c5c9e354cd946fc`이다. 승격·안전
게이트 결과는
[`zone_policy_risk_mission_validation_20260801.json`](../experiments/results/zone_policy_risk_mission_validation_20260801.json)에
고정했으며 canonical JSON SHA-256은
`6769ddd94900ffd60d5473e03cb65456e0cba4bf4ff1c7933deb1312df05afb7`이다.

### v3 원시 paired 증거 재검산

최종 replay는 정책별 요약 수치만 신뢰하지 않는다. selection 6,000 episode와 sealed
6,000 episode에서 12개 정책의 결과를 모두 기록한 144,000행을
[`zone_policy_paired_outcomes_20260801.jsonl.zlib`](../experiments/results/evidence/zone_policy_paired_outcomes_20260801.jsonl.zlib)에
보존하고, validator가 이 원시 결과에서 aggregate, 정책 간 paired 95% 신뢰구간,
scenario/operating-point별 지표와 최종 선택 정책을 다시 계산한다. 압축 증거의 고정
SHA-256은
`cb9ab656127bc6d374d7e34f3985722c35f37ba9d235257b16e8993598752f3e`이다.

세 로컬 캡처의 전체 출력 로그 SHA-256은 같았고 실행 시간은 436.862초, 437.492초,
436.614초였다. 다만 첫 두 캡처는 정확한 명령 원문과 실행별 산출물 digest를 보존하지
않았으므로, 이 기록만으로 세 실행의 명령 및 산출물이 모두 동일했다고 주장하지 않는다.
세 번째 캡처는 seed `20260806`의 정확한 명령과 명령 SHA-256을 보존했으며, 이 캡처와
연결된 paired 증거 SHA-256, replay raw SHA-256
`20566f5d3b1c7b438a2b8c026aa36efb5b5be36f3baa528b2dd2f20e64afe0e2`, canonical SHA-256을
검증했다. 명령, 환경, 실행별 출력 digest와 세 번째 캡처의 산출물 digest는
[`zone_policy_replay_run_receipts_20260801.json`](../experiments/results/evidence/zone_policy_replay_run_receipts_20260801.json)에 기록했다. 이 receipt는 저장소에 보존한 로컬 실행 기록이며 보호된 CI의 독립 서명은 아니다.

선정 후보 `hybrid_eig_0_25`의 sealed 해결률은 61.450%, Top-1은 79.400%, 오탐 구역
활성화율은 0.967%였다. 기존 런타임은 각각 61.433%, 79.283%, 0.933%였다. 해결률
차이의 paired 95% 신뢰구간은 `-0.0698%p ~ +0.1031%p`, Top-1 차이의 하한은
`-0.0925%p`, 오탐 구역 활성화율 차이의 상한은 `+0.0795%p`여서 승격 조건을
충족하지 못했다. 따라서 실제 런타임은 계속
`lr_hmm_posterior_weighted_coverage_eig_tiebreak`를 사용한다.

이 결과는 공개 ReID proxy와 결정론적 topology replay에 대한 증거이며 프로젝트 CCTV
일반화 85% 또는 실제 카메라 효용의 인과적 개선 증거는 아니다. 운영 계약은 계속
`operatorReviewRequired=true`, `autoMatchAllowed=false`다.

## 수치의 증거 경계

replay는 공개 ReID 지표의 보수 operating point를 사용한 deterministic Monte Carlo다.
실제 16대 카메라의 동기화 counterfactual 영상이 아니므로 다음 주장을 하지 않는다.

- 프로젝트 CCTV 구역 일반화 85% 달성
- EIG의 인과적 운영 개선 확정
- 자동 동일인 확정 가능

프로젝트 승격 수치는 16대 카메라에서 같은 시간대의 모든 관측을 보존한 뒤, 정책이
선택한 카메라만 시간순으로 공개하는 sealed replay가 생겼을 때 계산한다.

## 해결한 운영 리스크

| 리스크 | 적용한 차단책 |
|---|---|
| raw similarity를 확률로 오인 | calibration base rate와 보정기 provenance 없으면 API 422 |
| 같은 물리 track을 여러 카메라에서 곱함 | upstream multi-camera tracker의 필수 `correlationGroupId`별 한 건만 반영 |
| 2,000건 window 경계에서 같은 track 재적용 | 응답의 서명 대상 dedup digest 상태를 다음 revision에 의무 전달하고 event/track/observation 재사용 억제 |
| 카메라/시간 prior 이중 계산 | 후보 LR에는 appearance·semantic만, 위치·시간은 posterior 단계에만 사용 |
| 관할 밖을 네 구역에 강제 | `outside`, `unknown`을 포함한 6상태 정규화 |
| 카메라 미검출을 확정 부재로 오인 | 검증된 sensitivity·FPR·coverage·health로 약한 음성 likelihood 계산 |
| 고장난 카메라 선택 | unavailable/already-scanned 카메라를 순위에서 제외 |
| 모델이 사람을 자동 확정 | 모든 응답에서 `operatorReviewRequired=true`, `autoMatchAllowed=false` |
| 오래된 구역 명령으로 역전 | `routingRevision <= activeRoutingRevision` 확률 요청 자체를 422로 차단 |
| 위조 SHA 또는 operating point 수치 변조 | 모델·보정기·manifest와 camera sensitivity·FPR·operating-point tuple을 신뢰 레지스트리와 대조 |

남은 성능 리스크는 코드로 숨기지 않고 안전 모드로 봉쇄했다. 즉 모델이 불확실하면
후보를 관리자에게 올리고 네 구역 탐색을 계속하며, 관리자 확정 전에는 젯슨 집중
구역을 바꾸지 않는다.

## 재현 명령

```bash
uv run --offline python scripts/benchmark_zone_probability_policy.py \
  --episodes-per-cell 500 \
  --seed 20260806 \
  --public-reid-result experiments/results/evidence/prid2011_solider_open_set_v3_revalidated_summary.json \
  --paired-evidence-output experiments/results/evidence/zone_policy_paired_outcomes_20260801.jsonl.zlib \
  --output experiments/results/zone_policy_risk_replay_large_20260801.json

uv run --offline python scripts/validate_zone_policy_mission.py \
  --result experiments/results/zone_policy_risk_replay_large_20260801.json \
  --output experiments/results/zone_policy_risk_mission_validation_20260801.json
```

학습·임베딩 추출은 GPU 서버에서 수행하고, LR/HMM/카메라 순위 계산은 CPU 계산량이
작으므로 AI 워커 프로세스에서 실행한다.
