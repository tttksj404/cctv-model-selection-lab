# 오케스트레이션 GPU 실험 결과 기록

작성일: 2026-08-10  
실행 환경: `.env.txt`로 인증한 JupyterHub GPU 서버  
원격 작업 디렉터리: `/home/j-i15a204/clip_vitl14_server`

## 이 기록이 말하는 범위

이번 실험은 모델 업그레이드 후보를 비교하기 위한 **PA-100K 보조 속성 분류 실험**이다. PA-100K에는 사람의 identity, CCTV track, 카메라/시간 분리 이벤트가 없으므로 아래 수치는 실종자 identity 검색 정확도가 아니다. 특히 아래 `mA`, `InsF1`, `instance_acc`를 프로젝트의 Rank-1, Recall@5 또는 자동 일치율로 바꾸어 말하지 않는다.

프로젝트용 최종 승격은 별도의 `pair-evidence-v2` 계약으로 진행한다. 그 계약은 query/gallery track, identity, 사건·영상·시간·카메라 provenance를 요구하고, validation에서 arm을 고른 뒤 selected arm의 test를 한 번만 평가한다.

## 실제 GPU에서 새로 실행한 후보

### SOLIDER Swin-B + PA-100K 속성 head

- 결과 파일: `experiments/results/orchestration_solider_pa100k_20260810.json`
- 데이터: 공식 train/val/test, `80,000 / 10,000 / 10,000`행
- backbone: SOLIDER Swin-B frozen backbone
- 학습: 26개 속성 linear head, 30 epochs, SOLIDER ratio2weight BCE
- GPU: NVIDIA L40S
- PyTorch: `2.6.0+cu124`
- checkpoint SHA-256: `20c1105ac7b58f444092d9e3b589150e107a7320a34f321353276ff5c5a9f3d1`

| split | mA | InsF1 | instance accuracy | label macro-F1 |
|---|---:|---:|---:|---:|
| train | 82.50% | 88.72% | 80.87% | 71.65% |
| validation | 78.54% | 85.66% | 76.01% | 63.81% |
| test | 75.67% | 85.84% | 76.31% | 60.79% |

결론: SOLIDER head는 속성 보조 분기 후보로는 유효하지만, 이 결과만으로 CCTV identity 일반화 85%를 증명하지 않는다.

## 기존 동일 서버 산출물과의 비교

아래 비교도 모두 PA-100K 속성 proxy 지표다. 데이터 계약이 다른 수치를 한 그래프에 섞어 identity 성능처럼 표현하지 않는다.

| 후보 | 선택 기준 | test mA | 해석 |
|---|---|---:|---|
| 신규 CLIP ViT-L/14 partial fine-tune 5 epoch (`orchestration_clip_vitl14_finetune_5ep_20260810`) | epoch 2 validation mA | **78.27%** | 신규 GPU 재현 proxy 최고; epoch 3 이후 validation/test 모두 하락 |
| CLIP ViT-L/14 partial fine-tune (`server_recheck_finetune_20260723`) | validation mA | 78.24% | 현재 확인된 PA-100K proxy 최고 기록 |
| CLIP ViT-L/14 hard arm (`server_clip_vitl14_solider_distill_20260723`) | validation arm | 73.63% | SOLIDER와의 단순 결합이 proxy에서 개선을 보장하지 않음 |
| SOLIDER KD (`server_clip_vitl14_solider_distill_20260723`) | validation arm | 73.16% | distillation이 자동으로 개선되지 않음 |
| CLIP ViT-L/14 hard arm, alpha 0.65/temp 3 (`server_clip_vitl14_solider_distill_alpha065_temp30_20260723`) | validation arm | 73.63% | 해당 증류 설정의 proxy 결과 |
| SOLIDER KD, alpha 0.65/temp 3 | validation arm | 71.87% | teacher 지식 추가가 오히려 하락 |
| 신규 CLIP ViT-L/14 + SOLIDER KD, alpha 0.15/temp 1.5 (`orchestration_clip_solider_distill_a015_t15_20260810`) | validation mA로 arm 선택 | 72.72% | 신규 GPU 증류 재현; hard arm 72.72%가 KD arm 72.56%보다 높아 KD를 채택하지 않음 |
| 신규 SOLIDER Swin-B + PA head (`orchestration_solider_pa100k_20260810`) | validation mA | 75.67% | 신규 GPU 재현 실험; identity가 아닌 속성 proxy |

기존 CLIP 기록이 신규 SOLIDER head보다 test mA 기준으로 높지만, 이 차이를 곧바로 “CLIP이 실종자 검색에 더 정확하다”라고 결론 내리지 않는다. 다음 선택은 실제 CCTV track-heldout pair evidence에서 해야 한다.

## CLIP 5 epoch 실행 상태

동일 서버에서 다음 후보도 별도 출력 경로로 실행했다.

```bash
CUDA_VISIBLE_DEVICES=1 conda run -n qwen3vl --no-capture-output \
  python scripts/clip_vitl14_finetune_probe.py \
  --root experiments/data/pa100k_full \
  --checkpoint openai/clip-vit-large-patch14 \
  --train 80000 --val 10000 --test 10000 \
  --bs 128 --epochs 5 \
  --out experiments/results/orchestration_clip_vitl14_finetune_5ep_20260810.json
```

최종 JSON이 생성되기 전에는 수치를 기록하거나 후보 승격을 하지 않는다. 중간 로그만으로 학습 성공을 판단하지 않는 이유는 weight loading 이후 DataLoader, GPU 메모리, checkpoint 저장 단계에서 실패할 수 있기 때문이다. 이번 실행은 최종 JSON이 생성되었고, JSON SHA-256은 `548a5303418d2038f1bee227f7b9f0e2b0485aa5617dac4a31b9ce6b2c285b29`이다.

epoch별 validation/test mA는 `0.80447/0.77882`, `0.80593/0.78272`, `0.79904/0.78095`, `0.79397/0.76798`, `0.78682/0.75671`이다. 따라서 2 epoch arm을 validation 기준으로 보존하고, 이후 epoch을 무조건 오래 학습하는 방식은 채택하지 않는다.

## 추가 증류 실행 상태

기존 alpha 0.35/temperature 2.0 및 alpha 0.65/temperature 3.0 기록과 비교하기 위해, GPU2에서 다음 저강도 증류 arm을 별도 실행했다.

```bash
CUDA_VISIBLE_DEVICES=2 conda run -n qwen3vl --no-capture-output \
  python scripts/train_clip_vitl14_distill.py \
  --output experiments/results/orchestration_clip_solider_distill_a015_t15_20260810.json \
  --data-root experiments/data/pa100k_full \
  --clip-checkpoint openai/clip-vit-large-patch14 \
  --vendor-root experiments/vendor/SOLIDER-PersonAttributeRecognition \
  --teacher-checkpoint experiments/models/solider_swin_base.pth \
  --train-rows 80000 --val-rows 10000 --test-rows 10000 \
  --extract-batch-size 8 --head-batch-size 1024 \
  --head-epochs 15 --teacher-epochs 12 \
  --distill-alpha 0.15 --temperature 1.5
```

최종 JSON이 생성되었고 JSON SHA-256은 `914dfcc29f0e00f9028624d245d5e2281ba863568b6a0423e4cc459fa55d8a91`이다. 공식 PA-100K `80,000 / 10,000 / 10,000` split, NVIDIA L40S, PyTorch `2.6.0+cu124`에서 실행했다. validation mA로 선택된 arm은 `clip_vitl14_hard`이며, selected test 결과는 다음과 같다.

| arm | validation mA | test mA | test InsF1 | test label macro-F1 |
|---|---:|---:|---:|---:|
| CLIP ViT-L/14 hard | 76.16% | **72.72%** | 61.04% | 43.22% |
| CLIP ViT-L/14 + SOLIDER KD | 76.02% | 72.56% | 59.06% | 42.70% |

teacher의 PA-100K test mA는 79.29%였지만, student에 SOLIDER 지식을 섞은 결과는 hard arm보다 `0.16%p` 낮았다. 따라서 이번 설정에서는 증류가 개선 방법이 아니며, teacher 성능을 student가 자동으로 물려받는다고 볼 수 없다. gate(`target_mA=0.85`)는 실패했고, 이 수치는 CCTV identity/track-heldout 정확도가 아닌 속성 분류 proxy라는 경고가 결과 JSON에 남아 있다.

## 현재 결정

1. 운영 runtime을 이 실험 결과만으로 교체하지 않는다.
2. CLIP·SOLIDER·PAR·Qwen을 하네스로 감싼 후보 비교 계층은 유지한다.
3. validation에서 조합을 고르고 test를 한 번만 보는 현재 루프를 사용한다.
4. 현재 PA-100K proxy 기준 선택 후보는 5 epoch CLIP partial fine-tune의 epoch 2 arm이며, 신규 KD arm은 채택하지 않는다. 이 결정은 운영 runtime 교체 승인이 아니다.
5. 실제 프로젝트 데이터에 대해 `cross_camera_event_heldout`와 distractor를 채운 뒤에만 identity 성능을 발표 수치로 채택한다.
6. Sonnet teacher는 API/CLI 결과가 실제 동일 split의 수치로 남을 때만 별도 arm으로 넣는다. 이름이나 사용 사실만으로 성능 향상을 가정하지 않는다.

## 재현 증거

결과 JSON에는 데이터 행 수, split 설명, seed, GPU, PyTorch 버전, checkpoint SHA-256, train/validation/test 지표가 함께 저장되어야 한다. 원격 인증값과 cookie는 저장소·문서·로그에 기록하지 않는다.

원격 결과를 회수한 요약 manifest는 `docs/evidence/orchestration_gpu_evidence_20260810.json`에 보관한다. 이 manifest에는 원격 결과 파일의 SHA-256과 주요 지표만 담고, 인증값·cookie·개인정보는 담지 않는다.

## 2026-08-10 추가: 영상 검색의 85% 게이트는 track 단위로 검증

PA-100K 속성 분류 지표와 CCTV 후보 검색 지표는 같은 숫자로 비교할 수 없다. CCTV 워커는 한 사람의 여러 프레임을 하나의 지속 `tracker_id` 후보로 묶어 서버에 보내므로, 후보 검색의 운영 단위도 그 track이어야 한다. GPU 서버에서 CHIRLA 공개 proxy의 `strict-cross-camera-sequence` 분할을 사용해 이 단위를 별도로 측정했다.

| 측정 단위 | SOLIDER 공식 Swin-B MSMT17 | 결과 |
|---|---:|---:|
| 독립 프레임 Recall@5 | 80/95 | 84.21% |
| 지속 query track Recall@5 | 35/40 | **87.50%** |

계산은 `각 프레임 feature와 gallery identity의 cosine score → 같은 track의 score 평균 → identity Top-5` 순서다. 따라서 87.50%는 95개 프레임을 임의로 합쳐 만든 수치가 아니라, 40개 지속 track 후보 중 35개가 Top-5 안에 정답 identity를 포함했다는 의미다. `ai-worker/docs/evidence/chirla_solider_track_evidence_20260810.json`에 score matrix·metadata·manifest·checkpoint SHA-256과 track별 영수증을 저장했다.

동일 분할에서 SigLIP2, DINOv2, CLIP ViT-L/14 및 SOLIDER+CLIP 조합도 비교했다. track Recall@5는 각각 65.00%, 52.50%, 65.00%, 85.00%였으므로 이미지 reference가 있는 현재 후보 검색에는 SOLIDER를 1차 순위 모델로 채택하고, CLIP·PAR·Qwen은 속성·검토 증거로 남긴다. 이 결론은 실제 프로젝트 CCTV의 일반화 보장이 아니다. 프로젝트 영상에서 camera/time 분리 track 라벨과 distractor를 확보하면 같은 gate를 다시 실행해야 한다.
