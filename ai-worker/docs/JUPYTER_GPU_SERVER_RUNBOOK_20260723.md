# Jupyter GPU 서버 실행 기록

## 서버와 환경

## 학습 실행 정책

- 파인튜닝, 지식 증류, 임베딩 추출처럼 GPU를 사용하는 모든 학습 작업은 `http://70.12.130.105`의 인증된 Jupyter 서버에서 실행한다.
- 이 PC의 RTX 4050은 학습 실행 대상에서 제외한다. 로컬에서는 코드 수정, 정적 검사, 단위 테스트와 결과 문서화만 수행한다.
- 원격 실행은 `qwen3vl` Conda 환경과 `CUDA_VISIBLE_DEVICES`를 명시하고, PID·로그·JSON 산출물·GPU 상태를 함께 기록한다.
- 원격 작업이 진행 중일 때는 Jupyter 터미널을 닫거나 프로세스를 임의로 종료하지 않는다.

- Jupyter 작업공간: `http://70.12.130.105/user/i15a204/lab/workspaces/auto-S`
- 원격 작업 디렉터리: `/home/j-i15a204/clip_vitl14_server`
- GPU: `NVIDIA L40S` 4장, 각 46068 MiB
- Conda 환경: `qwen3vl`
- PyTorch: `2.6.0+cu124`
- CUDA 사용 가능: `True`
- 데이터: PA-100K official parquet, train 80000 / val 10000 / test 10000

## 원격 파인튜닝 재검증

```bash
cd /home/j-i15a204/clip_vitl14_server
nohup env CUDA_VISIBLE_DEVICES=0 conda run -n qwen3vl --no-capture-output \
  python scripts/clip_vitl14_finetune_probe.py \
  --root experiments/data/pa100k_full \
  --checkpoint openai/clip-vit-large-patch14 \
  --train 80000 --val 10000 --test 10000 \
  --bs 128 --epochs 3 \
  --out experiments/results/server_recheck_finetune_20260723.json \
  > experiments/results/server_recheck_finetune_20260723.log 2>&1 &
```

현재 실행 결과는 다음 원격 경로에 남는다.

- 결과 JSON: `experiments/results/server_recheck_finetune_20260723.json`
- 실행 로그: `experiments/results/server_recheck_finetune_20260723.log`
- 원격 점검 파일: `/home/j-i15a204/server_recheck_status4_20260723.txt`

## 판정 규칙

PA-100K에는 CCTV identityGroupId와 trackId가 없으므로 이 실행은 CLIP attribute 파인튜닝 재검증이다. 이 결과를 실제 CCTV identity/track-heldout 90%로 해석하지 않는다.

실제 90% 게이트를 통과하려면 같은 sealed CCTV test manifest에서 다음이 모두 있어야 한다.

- `evaluationEligibility.identityLabelsAvailable=true`
- `evaluationEligibility.trackHeldoutMetricsEligible=true`
- `evaluationEligibility.proxyMetricsReusedAsIdentity=false`
- `measurementStatus=identity_measured_sealed_test`
- sealed manifest와 identity label의 SHA-256, split 방법, metric 구현 식별자
- `top1_accuracy`, `track_exact_match`, `mA`, `InsF1`가 모두 0.90 이상

현재 제공된 MOV 세 편은 로컬에서 48개 검수 전 프레임과 YOLO 사람 후보를 생성했지만, identityGroupId는 비워 두었다. 따라서 현재 CCTV 결과는 `draft_needs_human_review`이며 identity 게이트는 `BLOCKED`가 정상이다.

## 로컬 CCTV 초안 생성

```powershell
uv run --with ultralytics --with opencv-python-headless python scripts/build_cctv_annotation_draft.py `
  --video experiments/data/cctv_real/raw/IMG_3565.mov `
  --video experiments/data/cctv_real/raw/IMG_3567.mov `
  --video experiments/data/cctv_real/raw/IMG_3568.mov `
  --output experiments/data/cctv_real/manifest.draft.jsonl `
  --summary experiments/results/cctv_annotation_draft_20260723.json `
  --frame-root experiments/data/cctv_real/frames `
  --device cpu
```

게이트 검증:

```powershell
uv run python scripts/evaluate_solider_90_gate.py `
  --result experiments/results/cctv_annotation_draft_20260723.json
```

예상 결과는 `BLOCKED: reviewed CCTV identity/track labels are unavailable`이다.

## 원격 검증 기록

`server_recheck_finetune_20260723.json`을 auto-S 인증 터미널에서 회수한 결과:

- 모델: CLIP ViT-L/14 last-two-block partial fine-tune
- 데이터: PA-100K official parquet, train/val/test = 80,000/10,000/10,000
- GPU: NVIDIA L40S
- test mA: `0.78241781539917`
- test micro accuracy: `0.8332769274711609`
- test IoU: `0.5476951003074646`
- 0.85 proxy target: `passed=false`

실제 CCTV identity/track-heldout 수치가 아니므로 이 결과를 identity 정확도로 해석하지 않는다.

## SOLIDER teacher distillation

auto-S에서 다음 기본 arm을 실행한다.

```bash
cd /home/j-i15a204/clip_vitl14_server
nohup env CUDA_VISIBLE_DEVICES=0 conda run -n qwen3vl --no-capture-output \
  python scripts/train_clip_vitl14_distill.py \
  --output experiments/results/server_clip_vitl14_solider_distill_20260723.json \
  --data-root experiments/data/pa100k_full \
  --clip-checkpoint openai/clip-vit-large-patch14 \
  --teacher-checkpoint experiments/models/solider_swin_base.pth \
  --train-rows 80000 --val-rows 10000 --test-rows 10000 \
  --extract-batch-size 32 --head-batch-size 512 \
  --head-epochs 15 --teacher-epochs 12 \
  --distill-alpha 0.35 --temperature 2.0 \
  > experiments/results/server_clip_vitl14_solider_distill_20260723.log 2>&1 &
```

결과와 로그는 원격 서버에 있으며, 완료 후 반드시 JSON의 `best_test.mA`, `passed`, `teacher_metrics`를 회수한다.

## 검수 manifest 결과 생성

프레임 JSONL을 track 단위로 집계하고 identity ranking과 속성 결과를 하나의 gate 입력으로 만든다.

```powershell
uv run python scripts/build_cctv_identity_result.py `
  --manifest experiments/data/cctv_real/manifest.reviewed.jsonl `
  --predictions experiments/results/<model>.predictions.jsonl `
  --attribute-result experiments/results/<model>.attributes.json `
  --model-name <model> `
  --output experiments/results/<model>.cctv_identity_result.json
```

그 뒤 `scripts/evaluate_solider_90_gate.py`를 실행한다. identity 라벨 또는 track 속성 지표가 없으면 숫자를 만들지 않고 `BLOCKED`로 남긴다.
## Remote distillation comparison completed

The authenticated auto-S Jupyter terminal completed both additional qwen3vl experiments:

- alpha=0.35, temperature=2.0: validation-selected arm clip_vitl14_hard; test mA 73.6262%, micro attribute accuracy 76.9062%, InsF1 59.8373%.
- alpha=0.65, temperature=3.0: validation-selected arm clip_vitl14_hard; test mA 73.6262%. The SOLIDER KD arm itself measured validation mA 75.1652% and test mA 71.8700%.
- These are PA-100K attribute proxies, not CCTV identity or track-heldout metrics. Both 85% proxy gates are false.

The consolidated evidence is in experiments/results/remote_gpu_recheck_20260723.json. The current CCTV MOV draft has 48 frame rows collapsed to 3 tracks, but zero reviewed identity labels, so the real 90% gate remains intentionally BLOCKED.
