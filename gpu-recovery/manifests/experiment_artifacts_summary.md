# CCTV AI 실험·가중치·파라미터 인덱스

이 문서는 GPU 서버에서 회수한 CCTV 작업을 다시 실행하거나 발표 자료를 만들 때, 어떤 설정과 결과 파일을 봐야 하는지 한 곳에 정리한 색인이다. 수치는 각 결과 JSON의 기록을 그대로 옮겼으며, 서로 다른 데이터셋의 수치를 하나의 정확도로 합치지 않는다.

## 업로드 상태

| 구분 | GitHub 보존 상태 | 확인 방법 |
| --- | --- | --- |
| 모델 선택·평가 코드 | 업로드됨 | `gpu-recovery/cctv/` |
| 학습·추론 설정과 실행 스크립트 | 업로드됨 | `gpu-recovery/cctv/**/configs`, `scripts`, `experiments` |
| 실험 로그·JSON 결과·그래프 | 업로드됨 | `gpu-recovery/cctv/**/experiments/results`, `runs` |
| 평가 계약·승격 기준 | 업로드됨 | `configs/model_selection_snapshot.json`, `configs/promotion_gate.json` |
| 선택 가중치·런타임 산출물 | 업로드됨, Git LFS | `gpu-recovery/weights/`, `manifests/weight_artifacts_20260811.json` |
| GPU 서버 전체 모델 목록 | 목록·크기·경로만 보존 | `manifests/model_inventory_20260811.json` |
| 원본 CCTV·사람 crop·개인 식별 이미지 | 공개 저장소에서 제외 | 별도 비공개 데이터 저장소 필요 |

## 모델별 역할과 보존 경로

| 역할 | 모델/구성 | 보존 경로 |
| --- | --- | --- |
| 인물 후보 검색·ReID | SOLIDER ReID Swin-B/MSMT17 | `cctv/clip_vitl14_server/experiments/SOLIDER-REID-runtime-8c08e1c` |
| 사람 속성 보조 출력 | SOLIDER Swin-B + PA-100K 26-attribute head | `cctv/clip_vitl14_server/experiments/results/orchestration_solider_pa100k_20260810.json` |
| CLIP 학생 모델 | CLIP ViT-L/14 partial fine-tune | `cctv/clip_vitl14_server/experiments/results/*clip_vitl14*finetune*` |
| 지식 증류 | CLIP ViT-L/14 student ← SOLIDER PAR teacher | `cctv/clip_vitl14_server/experiments/results/*distill*` |
| 엣지 검출 | AGV grid YOLO, ONNX/PT export | `cctv/agv-grid/`, `weights/edge/` |
| 구역 확률 | v7 logistic safe artifact | `cctv/codex-zone-region-20260802-final/`, `weights/zone-policy/` |
| 의미·속성 검토 | Qwen backend vertical slice | `cctv/qwen3vl-backend-final/`, `cctv/codex-zone-region-20260802-final/src/qwen_backend/` |

## ReID 학습·평가 파라미터

기준 설정 파일: `cctv/clip_vitl14_server/experiments/SOLIDER-REID-runtime-8c08e1c/configs/msmt17/swin_base.yml`

| 항목 | 값 |
| --- | --- |
| backbone | `swin_base_patch4_window7_224` |
| 입력 크기 | 학습·검증 모두 `384 x 128` |
| 손실 | softmax + triplet sampler, `METRIC_LOSS_TYPE=triplet` |
| margin | `NO_MARGIN=True`인 soft triplet |
| sampler | `softmax_triplet`, `NUM_INSTANCE=4` |
| optimizer | SGD, momentum은 기본 설정값 사용 |
| batch / worker | `IMS_PER_BATCH=64`, `NUM_WORKERS=8` |
| 학습 | 최대 120 epoch, warmup 20 epoch, cosine warmup |
| learning rate | `0.0008`, bias는 `BIAS_LR_FACTOR=2` |
| weight decay | weight와 bias 모두 `1e-4` |
| augmentation | horizontal flip `0.5`, random erasing `0.5`, padding `10` |
| 추론 | batch `256`, feature normalization 사용, re-ranking 사용 안 함 |
| 평가 TTA | 별도 결과에서 horizontal flip 평균·최대·Top-K 집계를 각각 비교 |

## 속성 학습·파인튜닝·증류 조합

모든 PA-100K 결과는 공식 train/val/test 분할을 사용했지만 identity·track ID가 없다. 따라서 아래 값은 속성 proxy 지표이며 CCTV identity 정확도로 해석하지 않는다.

| 실험 | 핵심 파라미터 | test 지표 | 판정 |
| --- | --- | ---: | --- |
| CLIP partial fine-tune probe | ViT-L/14 마지막 2개 block, 20k/5k/5k, 3 epoch | mA `0.7791` | 0.85 목표 미달 |
| CLIP partial fine-tune | ViT-L/14 마지막 2개 block, 80k/10k/10k, 5 epoch | mA `0.7827` | 0.85 목표 미달 |
| SOLIDER PA head | frozen Swin-B, 26 attributes, 30 epoch, ratio-weight BCE | mA `0.7567`, InsF1 `0.8584` | 속성 보조 head |
| CLIP ← SOLIDER KD | `alpha=0.15`, `temperature=1.5`, teacher 12 epoch | KD mA `0.7256` | 0.85 목표 미달 |
| CLIP ← SOLIDER KD | `alpha=0.35`, `temperature=2.0`, teacher 12 epoch | KD mA `0.7316` | 0.85 목표 미달 |
| CLIP ← SOLIDER KD | `alpha=0.65`, `temperature=3.0`, teacher 12 epoch | KD mA `0.7187` | 0.85 목표 미달 |

원본 결과 파일:

- `cctv/clip_vitl14_server/experiments/results/clip_vitl14_finetune_probe.json`
- `cctv/clip_vitl14_server/experiments/results/orchestration_clip_vitl14_finetune_5ep_20260810.json`
- `cctv/clip_vitl14_server/experiments/results/orchestration_solider_pa100k_20260810.json`
- `cctv/clip_vitl14_server/experiments/results/orchestration_clip_solider_distill_a015_t15_20260810.json`
- `cctv/clip_vitl14_server/experiments/results/server_clip_vitl14_solider_distill_20260723.json`
- `cctv/clip_vitl14_server/experiments/results/server_clip_vitl14_solider_distill_alpha065_temp30_20260723.json`

## 엄격 ReID 결과

CHIRLA는 프로젝트 CCTV가 아니라 공개 proxy이며, gallery/query를 카메라·시퀀스 기준으로 분리한 결과만 비교한다.

| 모델·집계 | query | identity | Rank-1 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| SOLIDER ReID Swin-B, hflip, gallery Top-5 mean | 95 | 11 | `0.4526` | `0.7579` | `0.5924` |
| 저장소 선택 스냅샷의 엄격 후보 평균 | 기록값 | 기록값 | `0.4737` | `0.7789` | `0.6074` |

자동 identity match 승격 기준은 `Rank-1 >= 0.85`, `Recall@5 >= 0.95`, false-match rate `<= 0.05`이다. 현재 결과는 후보 검색용으로만 보존하며 자동 확정 모델로 승격하지 않는다.

## 선택 가중치와 해시

실제 파일 크기·SHA-256·원본 위치는 `manifests/weight_artifacts_20260811.json`에 기계 판독 가능한 형태로 기록했다. 현재 Git LFS로 올린 선택 산출물은 10개, 총 약 2.371 GiB이다.

| 묶음 | 포함 내용 |
| --- | --- |
| SOLIDER | pretrained Swin-B, MSMT17 ReID weight, CHIRLA fine-tuned checkpoint |
| Edge | AGV grid best/last PT, best ONNX, YOLOv5s, YOLO11n |
| Zone | v7 logistic joblib와 안전한 JSON export |

## 재현 순서

```powershell
git lfs pull
python -m pip install -e .
python -m pytest -q tests --disable-warnings --maxfail=1
```

그 다음 각 실험의 manifest validator를 먼저 실행하고, 데이터·체크포인트·분할의 SHA-256을 결과 JSON에 남긴 뒤 장시간 학습을 실행한다. 원본 CCTV가 필요한 실험은 GitHub checkout만으로 실행되지 않으며, 비공개 `CCTV_DATA_ROOT`와 나머지 모델 저장소를 별도로 복원해야 한다.

## 중요한 해석 경계

- 파인튜닝·증류 수치는 PA-100K 속성 proxy이고, 엄격 ReID 수치는 CHIRLA 공개 proxy다.
- 프로젝트 CCTV의 cross-camera identity label이 없는 결과를 일반화 정확도로 바꾸어 쓰지 않는다.
- GitHub 공개 저장소에는 원본 사람 영상·crop·credential을 넣지 않는다.
- GPU 서버 전체 모델 inventory는 198개, 305.813 GiB로 확인됐지만 현재 브랜치에는 선택 가중치만 업로드되어 있다. 나머지는 private object storage 또는 재다운로드 절차가 필요하다.
