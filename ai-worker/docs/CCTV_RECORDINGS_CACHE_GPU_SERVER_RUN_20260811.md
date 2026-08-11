# CCTV recordings 캐시 전체 GPU 서버 실행 기록

## 실행 입력

- 원본: `ai-worker/artifacts/ai-worker/cache/recordings`
- 입력: MP4 29개, sidecar manifest 29개
- 녹화 object key: 28개 고유, 동일 object key를 가진 window segment 1건은 `evaluationUse=false`로 분리
- 카메라: `camera-01`부터 `camera-07`
- 라벨 상태: sidecar와 crop manifest에 identity 정답 라벨이 없어서 전부 `needs_human_review`

## GPU 서버에서 실행한 단계

1. 원격 JupyterHub GPU 서버에 원본 영상 전체를 업로드했습니다.
2. 서버의 `qwen3vl` CUDA 환경에서 YOLO tracking을 실행했습니다.
   - PyTorch `2.6.0+cu124`
   - NVIDIA L40S 0번 사용 확인
   - `ultralytics 8.4.117`, `lap 0.5.13`
   - `vid_stride=3`, `sample_every_seconds=0.75`, `max_crops_per_track=16`
3. 서버의 SOLIDER 환경에서 Swin-Base MSMT17 checkpoint를 실행했습니다.
   - hflip TTA
   - track feature 1024차원
   - 서버 CUDA 실행 확인

## 서버 결과

| 항목 | 결과 |
| --- | ---: |
| 입력 영상 | 29개 |
| 실제 검출이 발생한 영상 | 26개 |
| 검출 0건 영상 | 3개 |
| source track | 456개 |
| source crop/frame row | 3,541개 |
| 중복 object key 제외 후 평가 후보 track | 438개 |
| 중복 object key 제외 후 평가 후보 crop/frame | 3,432개 |
| SOLIDER track feature | `(456, 1024)` |
| SOLIDER frame feature | `(3541, 1024)` |

검출 0건인 영상도 입력 누락으로 삭제하지 않았고, summary의 영상 목록에 남겼습니다.

## 산출물

- `experiments/data/cctv_real/recordings_cache_20260811_gpu_server/manifest.jsonl`
- `experiments/data/cctv_real/recordings_cache_20260811_gpu_server/manifest.enriched.jsonl`
- `experiments/data/cctv_real/recordings_cache_20260811_gpu_server/review_manifest.summary.json`
- `experiments/data/cctv_real/recordings_cache_20260811_gpu_server/track_review_queue.jsonl`
- `experiments/results/recordings_cache_solider_embeddings_20260811_gpu_server.npz`
- `experiments/results/recordings_cache_solider_embeddings_20260811_gpu_server.json`

`track_review_queue.jsonl`은 456개 track을 한 줄씩 검수하는 큐입니다. 각 row에 대표 crop 경로, 카메라, 날짜, object key, `identityGroupId`, split, 검수 메모 필드가 있습니다.

## 평가 게이트

이번 실행은 전체 CCTV 영상을 사용한 **검출·tracking·임베딩 준비 실행**입니다. identity 정답 라벨이 없으므로 다음 수치는 산출하지 않았습니다.

- Rank-1 / Recall@K
- identity-heldout 일반화 정확도
- 85% 달성 여부
- 파인튜닝 학습 정확도

이는 영상이 부족해서가 아니라 identity adjudication 라벨이 없기 때문입니다. track ID를 identity 정답처럼 사용하면 같은 track의 프레임을 재식별하는 누수 평가가 되므로, 공식 성능 수치로 사용하지 않습니다. `track_review_queue.jsonl`에 독립 검수 라벨을 채운 뒤 카메라·시간 또는 영상 단위 held-out split으로 평가해야 합니다.
