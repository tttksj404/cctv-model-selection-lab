# 실제 프로젝트 CCTV에서 85%를 넘긴 방법

작성일: 2026-08-10

## 1. 먼저 숫자의 뜻을 고정했다

이 문서의 85%는 **한 프레임의 정답 분류율**이 아니다. AI 워커가 실제 운영에서 하는 일은 한 사람의 여러 프레임을 하나의 `track`으로 묶은 뒤, 관리자가 볼 후보를 Top-K로 만드는 것이다.

따라서 주 지표를 다음처럼 고정했다.

```text
track Recall@5
= 한 track의 정답 identity가 상위 5개 후보 안에 들어온 track 비율
```

예를 들어 11개 query track 중 10개가 Top-5 안에 들어오면 10/11 = 90.91%다. 이번 실제 측정에서는 11개 모두 들어가 11/11 = 100.00%였다. 이것은 Rank-1과 다른 지표다. Rank-1은 첫 번째 후보가 바로 정답인지 보는 값이고, Recall@5는 관리자가 확인할 후보 목록에 정답이 들어갔는지를 보는 값이다.

## 2. 실제 프로젝트 CCTV 평가셋

기존에 있던 `IMG_3617.mov`, `IMG_3618.mov`, `IMG_3620.mov`의 사람 crop을 다시 확인하여, 영상이 바뀌어도 같은 사람으로 볼 수 있는 track만 수동으로 묶었다.

| 항목 | 값 |
|---|---:|
| identity | 8명 |
| 전체 track fragment | 25개 |
| gallery crop | 90장 |
| query crop | 70장 |
| query track | 11개 |
| gallery 영상 | IMG_3617 |
| query 영상 | IMG_3618, IMG_3620 |
| 분할 | 카메라와 sequence 모두 분리 |

즉, 같은 영상의 바로 옆 프레임을 train/test로 나눈 것이 아니다. gallery는 IMG_3617에서만 만들고, query는 다른 영상인 IMG_3618/IMG_3620에서 만들었다. 같은 `track_id`의 프레임이 gallery와 query에 동시에 들어가지 않도록 했다.

단, 현재 identity 묶음은 1명의 수동 검수자가 만들었다. 따라서 아래 결과는 실제 프로젝트 영상에 대한 강한 파일럿 근거이지, 독립 검수까지 끝난 최종 서비스 인증은 아니다. 발표나 서비스 판정 전에 두 번째 검수자가 8명의 매칭을 다시 확인해야 한다.

## 3. GPU 서버에서 비교한 모델

모든 모델을 같은 crop, 같은 gallery/query 분할, 같은 hflip TTA, 같은 gallery 평균 방식으로 실행했다.

| 모델 | track Rank-1 | track Recall@5 | MRR | 판정 |
|---|---:|---:|---:|---|
| SOLIDER Swin-B MSMT17 | 81.82% | **100.00%** | **90.91%** | 채택 |
| SigLIP2 Base | 36.36% | **100.00%** | 66.67% | 보조 검증 |
| CLIP ViT-L/14 | 45.45% | **100.00%** | 60.15% | 의미 보조 |
| DINOv2 Base | 27.27% | 72.73% | 51.68% | 탈락 |

SOLIDER를 고른 이유는 Top-5만 맞춘 것이 아니라, 첫 후보가 맞는 비율과 MRR도 네 모델 중 가장 높았기 때문이다. DINOv2는 실제 cross-video track에서 85%를 넘지 못했으므로 기본 검색기로 채택하지 않는다.

### sequence별 SOLIDER 결과

| query sequence | track 수 | Rank-1 | Recall@5 |
|---|---:|---:|---:|
| IMG_3618 | 1 | 100.00% | 100.00% |
| IMG_3620 | 10 | 80.00% | 100.00% |

전체 프로젝트 cross-video track Recall@5는 11/11 = **100.00%**로 85% 기준을 넘었다. 이 데이터에서의 point estimate 기준으로는 목표를 통과했다.

### 방향을 바꾼 민감도 확인

한쪽 방향의 우연한 결과인지 확인하기 위해 같은 수동 매칭을 사용하되, 이번에는 `IMG_3618/IMG_3620`을 gallery로 놓고 `IMG_3617`을 query로 놓아 다시 GPU 추론했다. 이 검사는 같은 8명의 라벨을 재사용하므로 독립적인 새 데이터셋으로 세면 안 되지만, 영상 방향이 바뀌었을 때 모델이 무너지는지는 확인할 수 있다.

| 방향 | query track | SOLIDER Rank-1 | SOLIDER Recall@5 | 최악 rank |
|---|---:|---:|---:|---:|
| IMG_3617 gallery → IMG_3618/3620 query | 11 | 81.82% | **100.00%** | 2 |
| IMG_3618/3620 gallery → IMG_3617 query | 14 | 50.00% | **100.00%** | 4 |

두 방향 모두 Top-5 후보 안에 정답이 들어갔다. 따라서 현재 운영 목표인 “관리자 후보 목록에 정답을 포함”하는 85% 게이트에는 두 방향 모두 통과한다. 다만 Rank-1은 방향과 장면 변화에 민감하므로 최종 판단을 SOLIDER 하나의 첫 점수로 자동 확정하지 않고, Top-K 후보·Qwen 속성 검증·관리자 검토를 유지한다.

## 4. 모델 하나만 믿지 않고 오케스트레이션하는 이유

각 모델이 잘하는 것이 다르다.

```text
실종자 인상착의
        │
        ├─ 속성 정규화: 색상·상의·하의·안경·가방을 고정된 단어로 변환
        │
        ├─ SOLIDER: 사람 identity 후보 검색의 주 신호
        │       └─ reid_embedding / reid_score
        │
        ├─ CLIP 또는 SigLIP: 문장 의미와 전체 인상착의 보조 점수
        │       └─ clip_score
        │
        ├─ track 집계: 프레임 여러 장을 한 후보로 합침
        │       └─ 평균 점수 + 상위 프레임 evidence
        │
        ├─ Qwen3-VL: 색상·복장·가려짐·후보 품질을 설명하고 충돌을 표시
        │       └─ qwen_score / uncertainty / review_required
        │
        └─ 최종 scorer: 규칙과 confidence로 일치·검토필요·불일치 결정
```

중요한 점은 Qwen이 영상의 모든 crop을 처음부터 검색하는 구조가 아니라는 것이다. 검색은 SOLIDER가 맡고, Qwen은 이미 좁혀진 후보가 신고 내용과 맞는지 확인한다. 그래서 Qwen을 4bit로 바꾸거나 API가 지연되어도 1차 후보 검색 전체가 멈추지 않는다.

현재 워커의 evidence 계약은 다음과 같다.

```python
evidence = {
    "track_id": track_id,
    "reid_embedding": solider_embedding,
    "reid_score": solider_score,
    "clip_score": clip_score,
    "attr_vector": attributes,
    "qwen_score": qwen_score,
    "uncertainty": uncertainty,
    "review_required": review_required,
}
```

reference image가 있으면 SOLIDER를 identity-primary ranking으로 사용하고, reference image가 없거나 SOLIDER가 준비되지 않은 경우에만 기존 late-fusion fallback을 사용한다. 이 설정은 `QWEN_CANDIDATE_IDENTITY_PRIMARY_RETRIEVAL=true`로 켤 수 있다.

## 5. 점수를 합치는 실제 원리

모델마다 score 범위가 달라서 바로 더하면 안 된다. 먼저 query별 평균과 표준편차로 정규화한다.

```python
import numpy as np

def zscore(score_matrix):
    mean = score_matrix.mean(axis=1, keepdims=True)
    std = score_matrix.std(axis=1, keepdims=True)
    return (score_matrix - mean) / np.maximum(std, 1e-6)

solider = zscore(solider_scores)
siglip = zscore(siglip_scores)
final_search_score = 0.7 * solider + 0.3 * siglip
```

다만 이번 85% 판정의 공식 주 결과는 특정 test셋에서 비율을 고른 fusion 결과가 아니라 **SOLIDER 단독의 고정 설정**이다. test셋에 맞춰 fusion weight를 고르면 숫자가 부풀 수 있기 때문이다. fusion은 후보 순위를 더 세밀하게 정렬하는 연구용 보조 단계로 남겼다.

### 5-1. ArcFace/Batch-Hard Triplet 헤드의 별도 실험

SOLIDER backbone을 다시 학습하기 전에, 외부 공개 MEVID 데이터로 학습한 작은 metric head를 SOLIDER embedding 뒤에 붙여 보았다. 이 head는 다음 순서로 동작한다.

```python
def metric_head(x, log_scale, down, up):
    # x: SOLIDER가 뽑은 1024차원 벡터
    x = normalize(x * np.exp(np.clip(log_scale, -0.7, 0.7)))
    residual = np.tanh(x @ down.T) @ up.T
    return normalize(x + residual)

raw_score = gallery_embedding @ query_embedding.T
head_score = metric_head(gallery) @ metric_head(query).T
final_score = alpha * zscore(raw_score) + (1 - alpha) * zscore(head_score)
```

실험에서 `alpha`를 query 전체에 맞춰 한 번에 고른 것이 아니라, identity 하나를 통째로 빼고 나머지 identity로만 `alpha`를 정한 뒤 빠진 identity를 평가하는 OOF 방식도 실행했다. 즉, 평가 대상 identity의 query 결과를 보고 가중치를 고르지 않았다.

| 평가 방향 | SOLIDER 원본 | 외부 metric head | identity-OOF fusion |
|---|---:|---:|---:|
| IMG_3617 → IMG_3618/3620, track Recall@5 | 100.00% (11/11) | 100.00% (11/11) | **100.00% (11/11)** |
| IMG_3618/3620 → IMG_3617, track Recall@5 | 100.00% (14/14) | 100.00% (14/14) | **100.00% (14/14)** |

앞 방향에서는 외부 head가 Rank-1을 81.82%에서 90.91%로 올렸고, OOF fusion도 90.91%였다. 반대 방향에서는 Rank-1 개선이 50.00%에서 57.14%에 그쳤다. 따라서 이 head를 “모든 CCTV에서 검증된 최종 모델”이라고 포장하지 않고, **Top-5 후보를 놓치지 않는 주 게이트는 통과했지만 1위 자동 확정용으로는 보류한 연구 arm**으로 기록한다. 실제 워커의 기본 검색기는 누수 없는 SOLIDER identity-primary 경로를 유지하고, 더 많은 identity를 확보한 뒤 head를 OOF로 재검증해 승격한다.

## 6. track 집계가 중요한 이유

CCTV 한 사람은 한 프레임으로 끝나지 않는다. 한 track에서 70장의 crop이 나오면 70개의 후보를 서버로 보내지 않고, track 하나를 하나의 후보로 보낸다.

```python
def aggregate_track(frame_scores):
    # 여러 프레임의 흔들림과 가림을 줄인다.
    identity_score = frame_scores.mean(axis=0)
    evidence_frames = frame_scores.argsort(axis=0)[-3:]
    return identity_score, evidence_frames
```

운영에서는 평균 score만 저장하지 말고, 상위 3개의 선명한 프레임도 함께 저장해야 한다. 평균 하나만 저장하면 한 순간의 가림 때문에 후보 전체가 낮아질 수 있고, 상위 evidence만 사용하면 한 번의 오검출이 전체 후보를 망칠 수 있다. 그래서 `mean score + top evidence + uncertainty`를 함께 유지한다.

실제 저장 embedding으로 `mean`, `median`, `max`, `top-2/3/5/10`, softmax temperature pooling을 모두 재생했다. 모든 방법에서 양방향 track Recall@5는 100%로 같았다. 반대 방향에서 외부 head와 median을 함께 쓰면 보조 Rank-1이 57.14%에서 64.29%로 좋아졌지만, 한 방향의 소수 track에 맞춘 변화라서 기본 검색기의 고정 설정으로 승격하지 않았다. 즉, 현재 85% 게이트를 올리는 핵심은 프레임을 억지로 한 장 고르는 것이 아니라 **track을 하나의 후보로 묶고 Top-5를 유지하는 것**이다.

## 7. 파인튜닝과 증류를 실제로 하는 방법

현재 프로젝트 crop 수는 identity 8명, query track 11개라서 SOLIDER 전체 backbone을 바로 파인튜닝하면 외우기 쉽다. 따라서 순서는 아래가 안전하다.

### 7-1. 데이터가 더 모인 뒤의 학습 분할

최소한 다음 구조로 늘린다.

```text
identity 20명 이상
identity마다 카메라 3대 이상
identity마다 시간대 2개 이상
gallery와 query는 camera·시간·track 모두 분리
distractor는 identity별로 최소 3명
```

분할은 `identity-heldout`을 최우선으로 한다. 같은 사람의 같은 옷을 train과 test에 동시에 넣으면 85%가 쉽게 나오지만 실제 실종자 탐색 일반화 증거가 되지 않는다.

### 7-2. SOLIDER head 학습 손실

처음에는 backbone을 고정하고 projection/head만 학습한다. 이후 검증셋에서 개선이 확인될 때만 마지막 Swin stage를 조금 열어 준다.

```python
identity_loss = arcface(embedding, identity_label)
metric_loss = batch_hard_triplet(embedding, identity_label, margin=0.30)
attribute_loss = (
    bce(hat_upper_color, upper_color)
    + bce(hat_lower_color, lower_color)
    + bce(hat_glasses, glasses)
    + bce(hat_bag, bag)
)

loss = (
    1.00 * identity_loss
    + 0.50 * metric_loss
    + 0.20 * attribute_loss
)
```

ArcFace는 같은 identity를 각도상 가깝게 만들고, Batch-Hard Triplet은 가장 헷갈리는 다른 사람을 멀리 보낸다. 속성 보조 손실은 embedding에 상의·하의·안경·가방 정보가 사라지지 않게 한다. 속성 정답 라벨이 없으면 이 손실을 켜면 안 되고 `unknown`으로 제외해야 한다.

### 7-3. Sonnet teacher 증류의 올바른 위치

Sonnet은 crop의 색상·복장·가려짐 설명을 만들어 주는 teacher로는 쓸 수 있다. 하지만 Sonnet의 텍스트 답변을 그대로 SOLIDER의 identity embedding 정답으로 쓰면 안 된다. 그래서 teacher 출력은 다음처럼 구조화한다.

```json
{
  "upper_color": {"value": "gray", "confidence": 0.91},
  "lower_color": {"value": "black", "confidence": 0.88},
  "glasses": {"value": true, "confidence": 0.77},
  "occlusion": {"value": "partial", "confidence": 0.84}
}
```

학생 모델은 이 값을 hard label이 아니라 soft target으로 받는다.

```python
teacher_prob = teacher_attribute_probability
student_prob = student_attribute_logits.sigmoid()
distill_loss = kl_div(student_prob.log(), teacher_prob)
loss = identity_loss + 0.2 * attribute_loss + 0.1 * distill_loss
```

teacher confidence가 0.7보다 낮거나 `unknown`이면 distillation loss에서 제외한다. 이렇게 해야 Sonnet이 잘못 본 색상을 학생 모델이 확신하며 외우는 문제가 줄어든다. Sonnet API가 없는 동안에는 공개 PAR 라벨과 수동 검수로 먼저 학습하고, API가 생긴 뒤 동일한 crop에 teacher label만 추가한다.

## 8. 이번 결과의 결론과 남은 게이트

이번 GPU 실험으로 다음은 확인했다.

- 실제 프로젝트 영상끼리 camera·sequence를 나눈 track Recall@5 point estimate: **100.00% (11/11)**
- 동일 분할에서 SOLIDER Rank-1: **81.82% (9/11)**
- SOLIDER가 CLIP·SigLIP·DINOv2보다 Rank-1/MRR이 높음
- DINOv2는 실제 project cross-video track Recall@5가 72.73%로 85% 미달
- 외부 MEVID ArcFace/Batch-Hard Triplet head는 앞 방향 Rank-1을 **90.91% (10/11)**까지 높였지만, 반대 방향은 **57.14% (8/14)**라서 자동 1위 확정 모델로 승격하지 않음
- identity 하나씩 제외하는 OOF fusion에서도 앞 방향·반대 방향 track Recall@5는 각각 **100.00% (11/11), 100.00% (14/14)**로 유지됨
- 검색 모델은 SOLIDER, 의미/속성 확인 모델은 CLIP·SigLIP·Qwen으로 분리하는 구성이 합리적

아직 남은 검증은 세 가지다.

1. 현재는 8 identity라서 10 identity 이상 독립 검수 게이트를 추가해야 한다.
2. identity 라벨을 두 번째 사람이 재검수해야 한다.
3. 11 query track만으로 100%의 95% 신뢰구간을 85% 이상으로 만들 수는 없다. 11/11의 Wilson 95% 하한은 약 74.12%다. 더 많은 camera·시간·distractor track을 넣어야 한다.

따라서 **현재 결과는 “실제 프로젝트 cross-video 후보검색 Recall@5 85%를 넘겼다”는 재현 가능한 point-estimate 증거**다. 특히 방향을 바꿔도 Top-5 안에 정답 track이 남아 있어, 관리자 후보 목록과 Qwen 속성 검증으로 넘기는 현재 서비스 구조에 맞는다. 다만 이것을 “모든 CCTV 상황에서 85%를 보장한다”라고 바꾸어 말하면 안 된다. 다음 승격은 10명 이상·두 번째 검수자·독립 시간대·distractor track을 추가한 뒤 같은 gate를 다시 통과하는 것이다.

## 9. 원격 GPU 재현 명령

비밀키 없이 재현할 때의 핵심 명령은 다음과 같다.

```bash
conda run --no-capture-output -n qwen3vl \
  python scripts/build_project_cross_camera_feature_scores_20260810.py \
  --root /home/j-i15a204/experiments/data/project_cross_camera_bundle_20260810 \
  --manifest /home/j-i15a204/experiments/data/project_cross_camera_bundle_20260810/project_cross_camera_manifest.jsonl \
  --output experiments/results/project_cross_camera_20260810/project_cross_camera_scores.npz \
  --solider-checkpoint experiments/models/solider_reid/swin_base_msmt17.pth \
  --solider-root experiments/solider_reid_runtime_v3/SOLIDER-REID-runtime-8c08e1c \
  --batch-size 16 --device cuda
```

외부 metric head와 OOF 검증은 검색 결과를 다시 만들지 않고 저장된 embedding으로 재현한다.

```bash
python evaluate_project_metric_head_20260810.py \
  --embeddings tmp/project_solider_embeddings_20260810.npz \
  --metadata tmp/project_solider_embeddings_20260810.json \
  --metric-head tmp/mevid_public_metric_head_guarded_20260731.npz \
  --output tmp/project_metric_head_probe_20260810.json

python analyze_project_metric_head_oof_20260810.py \
  --forward-embeddings tmp/project_solider_embeddings_20260810.npz \
  --forward-metadata tmp/project_solider_embeddings_20260810.json \
  --reverse-embeddings tmp/project_solider_embeddings_reverse_20260810.npz \
  --reverse-metadata tmp/project_solider_embeddings_reverse_20260810.json \
  --metric-head tmp/mevid_public_metric_head_guarded_20260731.npz \
  --output tmp/project_metric_head_oof_20260810.json
```

OOF는 다음처럼 계산한다. `heldoutIdentity`의 query 행은 가중치 선택에 사용하지 않고, 나머지 identity의 track Recall@5 → Rank-1 → MRR 순서로 가장 좋은 `alpha`를 고른다. 그 뒤에야 held-out identity를 한 번 평가한다.

```python
for heldout_identity in identities:
    train_rows = query_identity != heldout_identity
    test_rows = query_identity == heldout_identity
    alpha = choose_alpha(
        raw_scores[train_rows],
        metric_head_scores[train_rows],
        query_identity[train_rows],
    )
    heldout_score = alpha * raw_z[test_rows] + (1 - alpha) * head_z[test_rows]
    report(heldout_score, query_identity[test_rows])
```

검증 시에는 결과 JSON의 `protocol`이 `strict-cross-camera-sequence`인지, query track 수와 identity 수가 기대값인지, 그리고 score matrix SHA-256이 기록된 값과 같은지 먼저 확인한다. 숫자만 출력되고 분할·해시·track provenance가 없으면 85% 근거로 사용하지 않는다.

## 10. 실제로 85%를 유지하기 위한 실행 순서

이 순서를 지키면 학습 데이터가 늘어날 때도 같은 방식으로 모델을 바꿔 비교할 수 있다.

1. **라벨을 먼저 고정한다.** 사람별 `identityGroupId`, 영상별 `sequenceId`, 카메라별 `cameraId`, 연속 관측별 `trackId`를 만든다. 같은 사람의 여러 프레임을 서로 다른 사람으로 세지 않는다.
2. **분할을 먼저 만든다.** gallery와 query가 같은 영상·같은 시간·같은 track을 공유하지 않게 한다. query identity를 학습에 넣지 않는 identity-heldout 평가를 별도로 만든다.
3. **학습 전에 원본 SOLIDER를 측정한다.** SOLIDER, CLIP, SigLIP, DINO를 같은 crop·hflip·track pooling으로 실행하고, Recall@5·Rank-1·MRR을 모두 저장한다.
4. **학습은 작은 head부터 시작한다.** 처음에는 SOLIDER backbone을 고정하고 256/512차원 projection head만 학습한다. `ArcFace + Batch-Hard Triplet`을 쓰되, 같은 identity의 서로 다른 카메라/시간 track을 positive로, 가장 헷갈리는 다른 identity를 hard negative로 고른다.
5. **속성 학습은 별도 보조 손실로 둔다.** 상의색·하의색·안경·가방처럼 검수된 라벨만 `BCE/ASL`로 학습한다. 속성 라벨이 없는 행은 loss에서 제외하고, 속성 점수를 identity 점수로 몰래 대체하지 않는다.
6. **Sonnet은 response-level teacher로만 넣는다.** Sonnet이 반환한 구조화 속성 JSON을 사람 검수와 비교하고, confidence가 낮은 응답은 제외한다. Sonnet 문장 자체를 identity 정답이나 logit으로 사용하지 않고, student 속성 head의 soft target에 작은 가중치로 넣는다.
7. **검증셋에서만 pooling·fusion을 고른다.** `mean/max/top-k`, SOLIDER·SigLIP 결합 비율을 query 결과에 맞춰 고르면 누수가 생긴다. identity별 OOF 선택 또는 사전 고정된 가중치만 통과시킨다.
8. **통과 조건은 고정한다.** 주 게이트는 `track Recall@5 >= 0.85`, 보조 게이트는 Rank-1·MRR·distractor false match rate다. 같은 테스트셋에서만 잘 맞춘 fusion은 발표/배포 모델로 승격하지 않는다.
9. **현장에서는 단계별로 실행한다.** SOLIDER가 후보 Top-5를 만들고, track의 상위 evidence crop만 Qwen에 전달한다. Qwen은 색상·복장·가림·불확실성을 검증하고, 최종 scorer는 `reid_score + attr_score + qwen_score`와 uncertainty를 함께 기록한다. 낮은 margin이나 충돌이면 자동 일치가 아니라 `review_required=true`로 둔다.

현재 데이터에서는 이미 1~3단계와 GPU 비교가 끝났고, SOLIDER의 실제 project cross-video Recall@5 point estimate가 100%다. 4단계의 full backbone fine-tuning을 바로 실행하지 않은 이유는 identity 8명만으로 backbone을 업데이트하면 일반화가 아니라 촬영 장면을 외우는 결과가 될 가능성이 높기 때문이다. 최소 10명 이상, 두 번째 검수자, 다른 시간대의 distractor를 추가한 뒤 같은 gate에서 학습 arm을 승격해야 한다.
