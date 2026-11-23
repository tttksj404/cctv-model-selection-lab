# 경험 기록: CCTV 모델 선택 실험 (cctv-model-selection-lab)

- 계열: `cctv-model-selection-lab`(공개 정리본). 같은 CCTV 영상 연구의 비공개 원 작업과 이어지는지 미확인
- 기간: 2026-07 ~ 2026-11 (커밋 2026-07-30 첫 공개 하네스 ~ 2026-11-02 Qwen3-VL 백엔드 비교 추가)
- 인원·구성: 미확인(커밋 작성자는 단일 로컬 계정)
- 본인 역할: 후보 모델 비교, strict ReID 재평가, promotion gate 하네스, GPU 실험 자료 복구·정리. 팀 내 분담은 미확인
- 성격: 연구·실험 프로젝트(실사용자 없음, 운영 승인 안 됨: `productionApproved = false`)
- 최종 갱신: 2026-11-23

## 1. 상황과 판돈
- 무엇 때문에 시작했나: CCTV 영상에서 사람 속성 인식과 동일인 검색을 맡길 모델을 역할별로 골라야 했다. 단일 점수 비교가 아니라 검증 조건을 통과한 결과만 다음 단계로 넘기는 구조가 목표(README).
- 왜 중요했나: 동일인 자동 매칭이 틀리면 잘못된 인물을 지목하는 문제가 생길 수 있어, 자동 판정 허용 기준을 따로 둠(Rank-1 0.85, Recall@5 0.95 등).
- 그때의 제약: 교차 카메라 identity 정답 부재, 원본 CCTV·개인정보 이미지는 공개 불가, GPU 서버 초기화 전 자료 회수 필요(2026-08-14 복구 완전성 기준).

## 2. 본인 몫과 팀 몫
| 한 일 | 본인이 직접 | 다른 사람(역할로만) | 함께 |
|---|---|---|---|
| 평가 하네스·promotion gate(`src/cctv_eval_harness/gate.py`) | 커밋 이력상 로컬 계정 | 미확인 | |
| 속성(PA-100K)·ReID(CHIRLA) 후보 실험 | 미확인(노트북·결과 JSON 보존) | 미확인 | |
| GPU 회수·가중치 10개 LFS 보존 | 커밋 2026-08-14 | | |

## 3. 판단
- 정한 것: 속성 proxy와 ReID를 같은 정확도 칸에 넣지 않고 역할별로 비교. 생성형 모델(Qwen 계열)은 충돌·저신뢰도 검토 보조로만 쓰고 속성 분류기·자동 동일인 판정기를 대체하지 않게 함.
- 정한 사람: 레포 문서상 작성자. 팀 합의 여부 미확인.
- 버린 선택지: 동일 카메라·시퀀스가 섞인 overlap 비교의 더 높은 수치(자동 매칭 근거로 불채택). `invalid_runtime`·`pending` 후보는 0점으로 환산하지 않고 비교에서 제외.
- 판단 근거: strict 조건(같은 카메라·시퀀스 gallery 제외) 재측정에서 SOLIDER-ReID Swin-B Top-3 mean이 Rank-1 0.4737, Recall@5 0.7789, MRR 0.6074로 자동 매칭 기준 미달 → Top-K 후보 검색만 허용, `automaticIdentityMatch = BLOCKED`(`docs/experiment-decision-log.md`).

## 4. 결과와 상대의 변화
- 확인된 결과: 후보 역할 분리표, strict ReID 결과, promotion gate가 proxy 입력에 대해 의도적으로 `NOT_APPROVED`(종료 코드 2)를 반환함.
- 수치(데이터셋별 분리): PA-100K test — CLIP ViT-L/14 부분 파인튜닝 mA 0.7827, SOLIDER PA head mA 0.7567 / InsF1 0.8584, KD 최선 조합 mA 0.7316. CHIRLA strict ReID — SOLIDER Rank-1 0.4526 / Recall@5 0.7579(스냅샷 선택값 0.4737 / 0.7789). 과거 proxy(45 crop·33 group) CLIP 0.414 vs Qwen3-VL-2B 0.393. 서로 합산 불가. 프로젝트 CCTV 일반화 성능 아님.
- 상대의 변화: 해당 없음.
- 안 된 것·남은 문제: 자동 동일인 매칭 기준 미달, 독립 identity heldout·사람 검토 manifest 미구축, GPU 서버 전체 모델 198개(305.813 GiB) 중 10개만 가중치 보존.

## 5. 직접 겪은 장면
미확인(본인 서술 필요). 단서: 2026-08-14 GPU 작업공간 초기화 전 노트북·가중치·결과를 회수·색인한 일, 2026-10-06 깨진 PNG 13개를 원본으로 복구한 일.

## 6. 출처
| 내용 | 출처 | 종류 |
|---|---|---|
| 역할·수치·gate 기준 | `cctv-model-selection-lab:README.md` | 원기록 |
| 판단 경위 | `cctv-model-selection-lab:docs/experiment-decision-log.md`, `docs/promotion_policy.md` | 원기록 |
| 복구 범위 | `cctv-model-selection-lab:gpu-recovery/manifests/recovery_completeness_20260814.md` | 원기록 |
| 일정 | `git log` (11건) | 원기록 |

## 7. 미확인 항목
- 팀 구성과 본인 담당 범위, 프로젝트 이름과 소속 과정.
- 비공개 원 작업·다른 CCTV 레포와의 계열 관계.
- 직접 겪은 장면.
