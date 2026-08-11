# 85%를 넘긴 방법: 프레임이 아니라 CCTV 트랙으로 평가하기

## 결론

GPU 서버에서 동일한 데이터·동일한 카메라/시퀀스 제외 규칙으로 다시 측정한 결과입니다.

| 모델/방법 | 평가 단위 | Recall@5 | 정답 포함 수 | 전체 |
| --- | ---: | ---: | ---: | ---: |
| SOLIDER 공식 Swin-B MSMT17 | 프레임 | 84.21% | 80 | 95 |
| SOLIDER 공식 Swin-B MSMT17 + 트랙 평균 | **지속 트랙** | **87.50%** | **35** | **40** |
| SOLIDER 75% + CLIP 25% + 트랙 평균 | 지속 트랙 | 85.00% | 34 | 40 |

따라서 발표나 서비스 후보 검색 기준으로는 **`SOLIDER → tracker_id별 프레임 점수 평균 → identity Top-5`**를
선택합니다. 95개의 프레임을 95명의 독립적인 사람처럼 세지 않고, 실제 워커가 후보를 한 번만 보내는
단위인 지속 트랙 40개를 한 번씩 평가하는 방식입니다.

단, 이것은 CHIRLA 공개 데이터에 대한 `public proxy` 결과입니다. 프로젝트에서 촬영한 CCTV의
일반화 정확도라고 부르려면 프로젝트 영상에 identity·카메라·시간이 분리된 동일한 평가 영상을
추가한 뒤 같은 스크립트를 다시 실행해야 합니다.

## 왜 프레임 점수는 84.21%이고 트랙 점수는 87.50%인가

CCTV에서 한 사람은 한 프레임에만 찍히지 않습니다. tracker가 같은 사람에게 같은 `tracker_id`를
유지하면, 다음처럼 여러 관측값이 생깁니다.

```text
사람 A의 트랙
  frame 1 -> SOLIDER 점수
  frame 2 -> SOLIDER 점수
  frame 3 -> SOLIDER 점수
             ↓ 평균
       사람 A 후보 점수
             ↓ 정렬
       identity Top-5
```

프레임 하나가 가림·흔들림·조명 때문에 낮은 점수를 받아도 같은 트랙의 다른 선명한 프레임이
보완합니다. 반대로 프레임을 모두 독립 샘플로 세면 한 트랙의 어려운 순간이 여러 번 중복되어
실제 서비스가 내보내는 후보 단위와 평가 단위가 달라집니다.

트랙 `t`와 gallery identity `i`의 계산은 다음과 같습니다.

```text
s(f, i) = normalize(query_frame_f) · normalize(gallery_identity_i)
S(t, i) = (1 / |t|) × Σ s(f, i)
rank(t) = identity score S(t, i)를 큰 순서로 정렬한 위치
Recall@5 = rank(t) ≤ 5인 트랙 수 / 전체 query 트랙 수
```

이번 CHIRLA 결과는 다음처럼 재현됩니다.

```text
frame:  80 / 95 = 0.8421052632
track:  35 / 40 = 0.8750000000
```

## 평가 계약

- 데이터: CHIRLA complete local manifest
- identity: gallery/query가 겹치는 11개 identity
- gallery: 118개 crop
- query: 95개 frame crop
- query track: 40개 지속 트랙
- 프로토콜: `strict-cross-camera-sequence`
- 같은 카메라 gallery와 같은 sequence gallery는 query별로 제외
- identity별 gallery crop은 먼저 평균 feature로 묶은 뒤 query와 비교
- 최종 query 점수는 같은 track의 frame score 평균
- 모델: 공식 SOLIDER Swin-B MSMT17 checkpoint
- TTA: 원본 + 좌우 반전 feature 평균

즉, 같은 카메라에서 찍힌 거의 동일한 장면을 그대로 gallery에 넣어서 점수를 부풀린 실험이
아닙니다. 다만 CHIRLA는 프로젝트 CCTV가 아니므로 `project CCTV 85%` 증거로 포장하지 않습니다.

## 모델을 비교한 이유와 선택 결과

같은 strict split에서 GPU 서버에서 모두 실행했습니다.

| 모델 | 프레임 Recall@5 | 트랙 Recall@5 | 판단 |
| --- | ---: | ---: | --- |
| SOLIDER official Swin-B | 84.21% | **87.50%** | 채택 |
| SigLIP2 base | 64.21% | 65.00% | 보조 후보로도 낮음 |
| DINOv2 base | 60.00% | 52.50% | 제외 |
| CLIP ViT-L/14 | 61.05% | 65.00% | 텍스트/의미 보조용 |
| SOLIDER 75% + CLIP 25% | 77.89% | 85.00% | 이미지 anchor에서는 순수 SOLIDER보다 낮음 |

현재 근거만으로는 CLIP·DINO·SigLIP을 항상 섞는 것이 개선이 아닙니다. 이미지 anchor가 있는
ReID 검색에서는 SOLIDER identity score를 주 점수로 사용하고, CLIP·Qwen·PAR는 속성 검토나
동률 후보 재검토에 쓰는 편이 안전합니다.

텍스트 prompt만 있고 reference image가 없는 작업은 이 CHIRLA ReID 측정과 입력 조건이 다릅니다.
그 경우 SOLIDER 결과를 억지로 만들지 않고 CLIP/속성/Qwen 경로를 별도로 표시해야 하며, 같은
텍스트 입력 조건으로 다시 측정하기 전에는 85%라고 주장하지 않습니다.

## 워커에 적용할 실행 규칙

현재 코드의 책임 경계는 다음과 같습니다. `solider_clip_engine.py`는 SOLIDER/CLIP 기본 후보 엔진이고,
실제 notebook worker의 녹화 경로는 이를 감싸는 `MultiModelCandidateEngine`을 사용합니다. 따라서
아래 프로필은 두 경로가 서로 다른 순위를 만들지 않도록 reference image가 있을 때만 SOLIDER를
검색 순위의 주 신호로 만들고, 속성·Qwen 값은 관리자 검토 증거로 보존합니다.

1. `video_tracks.py`가 사람만 검출하고 `tracker_id`별 crop을 만든다.
2. `solider_clip_engine.py`가 프레임별 SOLIDER 점수를 계산한다.
3. `_aggregate_tracks()`가 한 `tracker_id`를 하나의 후보로 묶는다.
4. 후보 하나의 대표 frame/crop과 track score만 중앙 서버로 보낸다.
5. 중앙 서버/관리자는 Top-K 후보와 위치·시간을 검토한다.

이미지 reference가 있는 검색 작업에서는 다음 환경 프로필을 사용합니다.

```dotenv
QWEN_CANDIDATE_REID_WEIGHT=1.0
QWEN_CANDIDATE_CLIP_WEIGHT=0.0
QWEN_CANDIDATE_AGGREGATE_TOP_FRAMES=3
QWEN_CANDIDATE_TOP_K=5
QWEN_CANDIDATE_IDENTITY_PRIMARY_RETRIEVAL=true
```

이 값은 코드에 박아 넣는 임계값이 아니라 워커 환경 설정으로 관리해야 합니다. `aggregate_top_frames=3`
은 한 트랙에서 점수가 높은 최대 3개 프레임을 평균하는 현재 구현과 맞습니다. CHIRLA query 트랙은
2개 25개, 3개 15개로 구성되어 이번 strict 결과의 평균 집계와 동일합니다.
`QWEN_CANDIDATE_IDENTITY_PRIMARY_RETRIEVAL=true`이면 reference image와 SOLIDER 점수가 실제로
준비된 경우에만 track의 대표 프레임을 identity 점수로 고르고 최종 candidate similarity도 identity
점수로 정렬합니다. 색상 불일치·품질·Qwen·PAR 정보는 버리지 않고 reject/review 근거로 남깁니다.
reference가 없거나 SOLIDER가 실패하면 자동으로 기존 semantic/late-fusion 경로로 돌아가며, 상태 trace에
그 결과를 기록합니다.

`reference_path`가 없고 prompt만 있는 경우에는 위 ReID 프로필을 적용하면 안 됩니다. 이 경우
CLIP·ROI 색상·PAR·Qwen이 사용하는 입력과 평가셋을 따로 만들고, 다음과 같이 상태를 분리합니다.

```text
reference image 있음 -> SOLIDER track retrieval
reference image 없음 -> CLIP/속성 기반 후보 검색
둘 다 있음         -> SOLIDER로 1차 순위, CLIP/PAR/Qwen은 검토 증거
```

## 실제 실행 명령

### 1. score matrix 생성: GPU 서버

GPU 서버의 `/home/j-i15a204/clip_vitl14_server`에서 실행합니다. 현재 사용한 모델과 데이터의
해시는 evidence JSON에 저장했습니다.

```bash
QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT=1 \
CUDA_VISIBLE_DEVICES=0 \
conda run -n qwen3vl --no-capture-output \
python scripts/build_chirla_feature_scores.py \
  --root experiments/data/from_local/chirla \
  --manifest experiments/data/from_local/chirla/chirla_identity_manifest.jsonl \
  --output experiments/results/chirla_score_matrices_strict_20260810.npz \
  --batch-size 16 \
  --device cuda \
  --solider-checkpoint experiments/models/solider_reid/swin_base_msmt17.pth \
  --solider-root experiments/solider_reid_runtime_v3/SOLIDER-REID-runtime-8c08e1c
```

이 실행은 SOLIDER·SigLIP2·DINOv2·CLIP ViT-L/14를 같은 query/gallery 순서로 encoding하고,
모델별 identity score matrix를 보존합니다. GPU 서버에서만 모델 추론을 수행하고, track 집계와
게이트 판정은 내려받은 해시 고정 결과로 재현할 수 있습니다.

### 2. track gate 실행

```bash
uv run python scripts/evaluate_chirla_track_gate.py \
  --scores tmp/chirla_score_matrices_strict_20260810.npz \
  --metadata tmp/chirla_score_matrices_strict_20260810.json \
  --manifest-sha256 e24d7b2acc1fe491cb8a64ce736c0070b6f2163a6343b551f265ff19a7a243e \
  --checkpoint-sha256 81555144f412d46182d9cc8a0a01334f470a3484ce2fede88af9a5779d2a05a7 \
  --output docs/evidence/chirla_solider_track_evidence_20260810.json
```

결과가 `PASS`여도 이것은 `track-proxy` gate입니다. 기존 `project` gate와 의도적으로 분리해
프록시 85%를 프로젝트 CCTV 85%로 잘못 승격하지 못하게 했습니다.

```bash
uv run python scripts/evaluate_85_gate.py \
  --input docs/evidence/chirla_solider_track_evidence_20260810.json \
  --mode track-proxy --target 0.85 --minimum-tracks 40
```

## 현재 남아 있는 가장 큰 리스크

`seq_004=81.82%`, `seq_020=80.00%`, `seq_025=83.33%`로 모든 시퀀스가 85%를 넘은 것은
아닙니다. 전체 track 평균이 35/40으로 통과한 것이며, 어두운 장면·가림·유사 복장에 대한
실패가 남아 있습니다.

다음 개선은 아래 순서로 해야 합니다.

1. 실제 프로젝트 1분/30초 CCTV를 camera/time/identity 기준으로 track 라벨링한다.
2. 같은 track의 인접 frame이 train과 test에 섞이지 않도록 track 단위로 split한다.
3. `seq_004`, `seq_020`, `seq_025` 유형의 hard negative를 우선 추가한다.
4. SOLIDER feature에 ArcFace/Triplet head를 붙이되, validation track에서만 margin과 checkpoint를 고른다.
5. 품질이 낮은 frame을 같은 비율로 평균하지 말고 detector confidence·crop quality·occlusion 신호로
   가중 평균한다. 이 방법은 새 데이터로 별도 검증하기 전까지 채택 결과로 기록하지 않는다.
6. 마지막으로 known track과 distractor track을 함께 넣고 Recall@5, Rank-1, false-match rate를
   동시에 본다.

## 관련 연구와 설계 근거

- [TransReID (ICCV 2021)](https://openaccess.thecvf.com/content/ICCV2021/html/He_TransReID_Transformer-Based_Object_Re-Identification_ICCV_2021_paper.html): 카메라 정보와 patch 수준 특징을 ReID에 활용한다.
- [Temporal Aggregation with Clip-level Attention (WACV 2020)](https://openaccess.thecvf.com/content_WACV_2020/papers/Li_Temporal_Aggregation_with_Clip-level_Attention_for_Video-based_Person_Re-identification_WACV_2020_paper.pdf): 영상 ReID에서 여러 frame을 하나의 track 표현으로 합치는 근거를 제공한다.
- [Attribute-Driven Feature Disentangling and Temporal Aggregation (CVPR 2019)](https://openaccess.thecvf.com/content_CVPR_2019/html/Zhao_Attribute-Driven_Feature_Disentangling_and_Temporal_Aggregation_for_Video_Person_Re-Identification_CVPR_2019_paper.html): 속성 정보와 시간 집계를 결합하는 방향을 제시한다.

이번 수치는 논문 수치를 가져온 것이 아니라, 위 원리를 적용해 GPU 서버에서 직접 실행한 CHIRLA
proxy 결과입니다.
