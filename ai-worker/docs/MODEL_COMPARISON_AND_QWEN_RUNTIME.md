# 모델·학습방법 비교와 Qwen 서버 런타임 결정

작성일: 2026-07-22
상태: 공정 비교 번들 준비 완료, 원격 GPU 실행과 프로젝트 CCTV 자동판정 승인은 보류

## 결론

- GPU 서버의 1차 후보는 `Qwen/Qwen3.5-9B`로 둔다.
- 이미지·영상 fallback은 `Qwen/Qwen2.5-VL-7B-Instruct`로 고정한다. 두 모델 모두 같은 vLLM OpenAI 호환 API와 `qwen-active` served name을 사용하므로 `QWEN_MODEL_ID` 한 줄만 바꾸어 교체한다.
- 다만 두 Qwen 모델은 아직 프로젝트 CCTV track-held-out 데이터로 측정되지 않았다. 따라서 Qwen3.5-9B가 85% 이상이라고 주장하거나 자동 일치의 최종 판정기로 승인하지 않는다.
- Jetson Nano에는 원본 Grounding DINO를 실시간 주 검출기로 넣지 않는다. NanoOWL/CLIP 기반 임베디드 후보 추출과 경량 detector/tracker를 유지하고, Grounding DINO는 GPU 서버 또는 오프라인 box teacher로 사용한다. Nano에서 DINO-T를 시험할 경우에는 저 FPS smoke와 실제 latency·메모리·drop-frame·person recall 측정으로만 판단한다.
- 현재 백엔드의 자동 일치는 `automaticMatchEnabled=false`로 차단돼 있다.
  PAR/ReID 확률과 시간·카메라·track 일관성 scorer는 Top-K 정렬과
  `검토필요` 판단에만 사용한다. 향후 85% 승격 gate를 통과한 뒤 자동 일치를
  활성화하더라도 deterministic scorer가 담당하고, Qwen은 후보 설명과 속성 충돌
  검토용으로만 유지한다.

## 같은 기준으로 비교한 실험값

두 데이터군은 서로 다른 지표이므로 한 점수로 합치지 않았다.

### CCTV person-crop proxy: x = 속성 정확도, y = p95 지연시간, 버블 = 파라미터 수

| 모델 | 방법 | 속성 정확도 | p95 | 상태 |
|---|---|---:|---:|---|
| Qwen3-VL-2B | 직접 VLM 구조화 JSON | 39.30% | 8.298초 | 로컬 측정 |
| CLIP ViT-B/32 | zero-shot field scoring | 38.60% | 0.723초 | 로컬 측정 |
| CLIP ViT-L/14 | zero-shot field scoring | 41.40% | 4.141초 | 로컬 측정 |
| SigLIP base | zero-shot field scoring | 24.21% | 0.778초 | 로컬 측정 |
| BLIP base | caption + attribute parsing | 20.35% | 0.468초 | 로컬 측정 |

이 proxy에서 CLIP ViT-L/14의 속성 점수가 41.40%로 가장 높고, BLIP base가 p95 0.468초로 가장 빠르다. Qwen3-VL-2B는 39.30%지만 p95가 8.298초다. 현재 유효하게 실행된 다섯 모델 모두 track exact가 0%였고, 이 결과만으로 CCTV 동일인 판정을 승인할 수 없다. Florence-2-large와 Florence-2-large-ft는 현재 로컬 Transformers 런타임에서 `forced_bos_token_id` 초기화 오류로 45개 예시 전부가 `invalid_runtime`이어서 차트에서 제외했다.

### PA-100K 속성 실험: x = mA, y = InsF1, 버블 = 학습 행 수

| 모델·방법 | mA | InsF1 | 상태 |
|---|---:|---:|---|
| SOLIDER Swin-B frozen head | 66.95% | 79.05% | 로컬 subset 측정 |
| SOLIDER Swin-B end-to-end fine-tune | 69.58% | 82.30% | 로컬 subset 측정 |
| CrossPAR | 86.9% | 90.6% | 논문 공개값, 재현 아님 |

CrossPAR 수치는 공개 PA-100K benchmark reference일 뿐 이 프로젝트의 CCTV 결과가 아니다. 현재 로컬 실험에서 동일 metric 기준 85%를 넘은 방법은 없다.

### 직접 순위 비교가 금지된 보조 proxy

| 모델·방법 | 점수 | 지표 | 데이터 |
|---|---:|---|---|
| SOLIDER Swin-B six-field proxy | 79.83% | field top-1 mean | 100-image local proxy |
| CLIP partial fine-tune | 72.67% | six-field multiclass top-1 mean | 100-image local proxy |

이 두 값은 PA-100K의 mA/InsF1이나 CCTV identity accuracy가 아니므로 메인 차트의 점들과 직접 비교하지 않는다.

## 생성된 버블차트와 좌표

- [실행된 비교 노트북](../experiments/model_comparison_bubble_chart.ipynb)
- [CCTV proxy 런타임 버블차트](../experiments/results/model_comparison_proxy_runtime_bubble.png)
- [PA-100K mA·InsF1 버블차트](../experiments/results/model_comparison_pa100k_bubble.png)
- [비교 불가 보조 proxy 버블차트](../experiments/results/model_comparison_noncomparable_bubble.png)
- [전체 x/y/bubble 좌표 CSV](../experiments/results/model_comparison_bubble_coordinates.csv)
- [차트 원본 JSON](../experiments/results/model_comparison_bubble_data.json)

노트북은 15 cells 중 7개 code cell을 top-to-bottom으로 실행했고 error output은 0개다. CSV는 현재 유효한 main chart 5개, PA-100K 보조 3개, non-comparable 2개, pending 4개를 포함해 헤더 제외 14개 좌표를 기록하며, Florence 실패 2건은 `failedCandidates`로 별도 보존한다.

## GPU 서버 Qwen 런타임

다음 파일을 GPU 서버의 deployment 디렉터리에 복사한다.

- `deployment/docker-compose.qwen.yml`
- `deployment/qwen-runtime.env.example`
- `deployment/model-candidates.json`

서버에서:

```bash
cp qwen-runtime.env.example .env
docker compose --env-file .env -f docker-compose.qwen.yml pull
docker compose --env-file .env -f docker-compose.qwen.yml up -d
curl http://127.0.0.1:8000/v1/models
```

Qwen3.5-9B가 matched CCTV 평가에서 탈락하면 `.env`의 모델 ID만 바꾼다.

```bash
sed -i 's#^QWEN_MODEL_ID=.*#QWEN_MODEL_ID=Qwen/Qwen2.5-VL-7B-Instruct#' .env
docker compose --env-file .env -f docker-compose.qwen.yml up -d --force-recreate
curl http://127.0.0.1:8000/v1/models
```

두 모델 모두 `qwen-active`라는 동일 served name을 사용하므로 vLLM API client의 모델 호출 계약을 바꾸지 않고 모델만 교체할 수 있다. 외부에 port를 열 때에는 `127.0.0.1` 바인딩을 유지하고 reverse proxy, 방화벽, API key를 별도로 구성한다.

중요한 통합 경계: 이 compose는 vLLM 서비스의 모델 교체 계약이다. 현재 이 저장소 FastAPI의 `QWEN_PROVIDER=qwen`는 `QWEN_MODEL_PATH`를 읽는 기존 로컬 Transformers provider이므로, compose를 실행해도 FastAPI가 자동으로 Qwen3.5-9B를 사용하지 않는다. FastAPI까지 연결하려면 별도 vLLM HTTP provider adapter를 추가하거나 Spring이 vLLM의 `/v1/chat/completions`를 직접 호출해야 한다.

## 이번 작업에서 실제로 확인하지 못한 것

로컬 PC에는 Docker가 설치되어 있지 않았고, 사용자가 준 Jupyter URL은 인증되지 않은 요청에서 JupyterHub `/hub/login`으로 이동했다. 따라서 이 작업에서 실제 GPU 서버에 가중치를 다운로드하거나 컨테이너를 시작했다고 보고할 수 없다. 위 파일은 서버 인증 세션 또는 SSH/터미널 권한이 연결되면 바로 실행할 수 있는 배포 번들이다.

실제 승격 전에는 Qwen3.5-9B와 Qwen2.5-VL-7B-Instruct를 동일한 CCTV track-held-out split에서 각각 실행해 다음을 기록해야 한다.

`caseId`, `videoId`, `cameraId`, `trackId`, `identityGroupId`, `mA`, `InsF1`, track-level exact, false-match rate, review rate, p50/p95 latency, GPU memory, malformed JSON rate.

이 비교에서 Qwen3.5가 실패하면 즉시 Qwen2.5-VL로 교체하고, 둘 다 85% gate를 통과하지 못하면 Qwen을 억지로 최종 식별기로 쓰지 않고 PAR/ReID와 temporal scorer를 보강한다.

## Qwen2.5 포함 공정 파인튜닝 실험

Qwen2.5와 Qwen3.5는 같은 조건으로 base와 LoRA SFT를 모두 측정한다. 여기서 fine-tuning은 4050 6GB 로컬 GPU에서 수행한 결과가 아니라 GPU 서버에서 실행하는 LoRA 기준이며, full-parameter fine-tuning은 메모리·시간 조건이 달라 별도 실험으로 분리한다.

- 데이터: `experiments/data/qwen_fair/`의 train 70장, validation 15장, test 15장
- 고정 입력: 동일 이미지, 동일 prompt, 동일 6개 필드(`gender`, `age`, `viewpoint`, `accessory`, `sleeve`, `bottom_type`)
- 고정 학습: seed/data seed `20260722`, LoRA rank 8, alpha 16, dropout 0.05, 3 epochs, batch 1, gradient accumulation 8
- 고정 평가: field accuracy, six-field exact match, valid JSON, 필드별 정확도
- fail-closed 검증: 빈·손상 reference, 필드 누락·추가, 이미지 루트 탈출은 즉시 실패하며, 유효 결과에는 reference/prediction SHA-256과 평가 계약이 기록된다.
- 결과 파일: `qwen3_5_9b_fair_base.json`, `qwen3_5_9b_fair_lora.json`, `qwen2_5_vl_7b_fair_base.json`, `qwen2_5_vl_7b_fair_lora.json`

서버에서 먼저 저장소의 데이터 생성기를 실행한다. 서버 경로는 서버의 실제 데이터 위치로 바꾼다.

```bash
python scripts/prepare_qwen_fair_dataset.py \
  --source-manifest /home/j-i15a204/datasets/pa100k/manifest.jsonl \
  --image-root /home/j-i15a204/datasets/pa100k \
  --output-dir /home/j-i15a204/datasets/qwen_fair
```

LoRA 학습은 같은 runner에서 모델 ID와 출력 경로만 바꿔 두 번 실행한다.

```bash
MODEL_ID=Qwen/Qwen3.5-9B \
TRAIN_DATA=/home/j-i15a204/datasets/qwen_fair/qwen_fair_train.jsonl \
VAL_DATA=/home/j-i15a204/datasets/qwen_fair/qwen_fair_validation.jsonl \
OUTPUT_DIR=/home/j-i15a204/outputs/qwen-fair-lora-qwen35 \
DRY_RUN=0 bash training/run_qwen_fair_lora.sh

MODEL_ID=Qwen/Qwen2.5-VL-7B-Instruct \
TRAIN_DATA=/home/j-i15a204/datasets/qwen_fair/qwen_fair_train.jsonl \
VAL_DATA=/home/j-i15a204/datasets/qwen_fair/qwen_fair_validation.jsonl \
OUTPUT_DIR=/home/j-i15a204/outputs/qwen-fair-lora-qwen25 \
DRY_RUN=0 bash training/run_qwen_fair_lora.sh
```

각 base와 LoRA adapter는 동일 test split으로 추론한 뒤 `scripts/score_qwen_fair_results.py`로 점수를 만든다. 추론 출력은 JSONL이며 각 줄은 `response` 또는 `predict` 같은 응답 필드를 가져야 한다.

```bash
MODEL_ID=Qwen/Qwen3.5-9B \
DATASET=/home/j-i15a204/datasets/qwen_fair/qwen_fair_test.jsonl \
RESULT_PATH=/home/j-i15a204/predictions/qwen3_5_9b_fair_base.jsonl \
DRY_RUN=0 bash training/run_qwen_fair_inference.sh

MODEL_ID=Qwen/Qwen3.5-9B \
DATASET=/home/j-i15a204/datasets/qwen_fair/qwen_fair_test.jsonl \
RESULT_PATH=/home/j-i15a204/predictions/qwen3_5_9b_fair_lora.jsonl \
ADAPTERS=/home/j-i15a204/outputs/qwen-fair-lora-qwen35 \
DRY_RUN=0 bash training/run_qwen_fair_inference.sh

MODEL_ID=Qwen/Qwen2.5-VL-7B-Instruct \
DATASET=/home/j-i15a204/datasets/qwen_fair/qwen_fair_test.jsonl \
RESULT_PATH=/home/j-i15a204/predictions/qwen2_5_vl_7b_fair_base.jsonl \
DRY_RUN=0 bash training/run_qwen_fair_inference.sh

MODEL_ID=Qwen/Qwen2.5-VL-7B-Instruct \
DATASET=/home/j-i15a204/datasets/qwen_fair/qwen_fair_test.jsonl \
RESULT_PATH=/home/j-i15a204/predictions/qwen2_5_vl_7b_fair_lora.jsonl \
ADAPTERS=/home/j-i15a204/outputs/qwen-fair-lora-qwen25 \
DRY_RUN=0 bash training/run_qwen_fair_inference.sh

python scripts/score_qwen_fair_results.py \
  --reference /home/j-i15a204/datasets/qwen_fair/qwen_fair_test.jsonl \
  --prediction /home/j-i15a204/predictions/qwen3_5_9b_fair_base.jsonl \
  --output experiments/results/qwen3_5_9b_fair_base.json \
  --model Qwen/Qwen3.5-9B --method base
```

노트북은 네 결과 파일을 자동으로 읽어 `qwen_fair_finetuning_bubble.png/.svg`를 만들고, 결과가 아직 없으면 `pending` 상태만 CSV에 남긴다. 따라서 현재 Qwen 좌표가 비어 있는 것은 누락이 아니라 원격 실행 전이라는 검증 가능한 상태다. PA-100K proxy는 색상·질감·CCTV 동일인 정확도를 측정하지 않으므로 이 차트에서 85%를 넘더라도 실종자 식별 모델의 승격 근거로 사용하지 않는다.

## 참고한 공식 문서

- [Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Qwen2.5-VL-7B-Instruct model card](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct)
- [vLLM Docker deployment](https://docs.vllm.ai/en/v0.22.0/deployment/docker/)
- [Grounding DINO 공식 저장소](https://github.com/IDEA-Research/GroundingDINO)
- [NVIDIA Jetson Nano 사양](https://developer.nvidia.com/embedded/jetson-nano)

## 2026-07-23 광범위 후보 조사와 추가 측정

공식 모델 카드 기준으로 SigLIP2, Qwen2.5-VL-3B, Gemma 3 4B, SmolVLM2-500M, InternVL3-2B, Molmo2-4B, MiniCPM-V 4.5, Phi-3.5 Vision, PaliGemma2, DINOv2까지 후보를 넓혔다. 이 중 같은 CCTV person-crop proxy 계약으로 실행한 결과는 [광범위 후보 문서](../experiments/BROAD_MODEL_CANDIDATES.md)와 [광범위 비교 노트북](../experiments/broad_model_comparison.ipynb)에 남겼다.

| 추가 후보 | 상태 | 결과 |
|---|---|---|
| SigLIP2 Base 224 | valid measured | attribute accuracy 20.35%, p95 4.310초 |
| SigLIP2 Base 384 | valid measured | attribute accuracy 21.75%, p95 8.377초 |
| SmolVLM2-500M | invalid_output_contract | 45장 실행, JSON valid 0%; 차트 제외 |
| Qwen2.5-VL-3B | pending_download_network | 7GB급 checkpoint가 145MB 이후 로컬 Xet 다운로드 정지 |
| Gemma 3 4B, InternVL3-2B, Molmo2-4B, MiniCPM-V 4.5, Phi-3.5 Vision | not measured | custom processor, 인증, 용량, 또는 GPU 서버 실행 필요 |

추가 측정 후에도 동일 계약의 최고는 CLIP ViT-L/14 41.40%이며, 85% 목표를 달성했다고 말할 근거는 없다. 따라서 Qwen을 단독 최종 판정기로 승격하지 않고, GPU 서버에서 PAR/ReID/track scorer와 함께 동일 track-held-out 데이터로 평가해야 한다.
