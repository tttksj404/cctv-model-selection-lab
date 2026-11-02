# CCTV 모델 비교 실험

## 결론

현재 확보 가능한 CCTV형 proxy 데이터와 로컬 GPU에서 같은 입력을 측정한 결과는 다음과 같다.

| 모델 | 속성 정확도 | 이미지 exact | Track exact | 구조화 출력 | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3-VL-2B-Instruct | 39.3% | 0.0% | 0.0% | 55.6% | 5.619초 | 8.298초 |
| CLIP ViT-B/32 | 38.6% | 0.0% | 0.0% | 100.0% | 0.517초 | 0.723초 |
| CLIP ViT-L/14 | 41.4% | 0.0% | 0.0% | 100.0% | 2.095초 | 4.141초 |
| SigLIP base | 24.2% | 0.0% | 0.0% | 100.0% | 0.637초 | 0.778초 |
| BLIP base | 20.4% | 0.0% | 0.0% | 100.0% | 0.365초 | 0.468초 |

따라서 현재 동일 proxy 조건에서 속성 점수 1위는 CLIP ViT-L/14(41.4%)이고, Qwen3-VL-2B는 39.3%로 2위지만 p95 지연시간이 8.298초다. 가장 빠른 BLIP은 p95 0.468초지만 속성 정확도가 낮아 현재 최종 후보로 승격하지 않는다. 이 결과는 CCTV 영상에서 추출한 45개 proxy person crop의 속성 평가이지 실제 신원 식별 정확도가 아니다. Florence 두 실행은 현재 로컬 Transformers 런타임 초기화 오류(`forced_bos_token_id`)로 `invalid_runtime`이어서 차트에서 제외했다. 이전 44.9% 결과는 누락 필드를 `none`으로 잘못 정규화한 값이므로 폐기했다.

메인 비교의 원본은 [버블차트 좌표 JSON](results/model_comparison_bubble_data.json)과 [실행된 노트북](model_comparison_bubble_chart.ipynb)이다. 표의 5개 모델은 모두 `simuletic 15개 + PA-100K 30개 = 45개`, 33개 group, 동일한 10개 필드 스키마와 동일한 p50/p95 계산을 사용한다. 다만 데이터셋의 원래 라벨 범위가 달라 실제 채점 필드는 Simuletic 샘플당 9개, PA-100K 샘플당 5개이며, 각 샘플의 비어 있거나 `unknown`인 필드는 분모에서 제외한다. 따라서 이 차트는 “공통 10개 스키마를 가진 부분 라벨 proxy”이지 “모든 샘플에서 10개 속성을 관측한 평가”가 아니다.

## 데이터와 측정 조건

- Simuletic CCTV-Pedestrian-1K: 고각도 synthetic CCTV person attribute 이미지 15장
- PA-100K: 실제 surveillance crop 30장
- 동일한 10개 필드 스키마: `gender`, `age`, `hair_color`, `viewpoint`, `top_color`, `top_type`, `bottom_color`, `bottom_type`, `footwear`, `accessory`
- Simuletic metadata의 중복 파일명 5개 그룹은 이미지와 라벨 불일치 위험 때문에 제외
- GPU: NVIDIA GeForce RTX 4050 Laptop GPU, CUDA PyTorch 2.11.0+cu128
- Qwen: 자유 JSON 생성 후 필드 정규화
- CLIP: 필드별 zero-shot 후보 점수
- SigLIP: 필드별 zero-shot 후보 점수
- Florence: detailed caption 후 필드 정규화
- BLIP: image caption 후 필드 정규화

지연시간 p95는 모든 모델에 동일하게 `sorted(latencies)[max(0, int(n * 0.95) - 1)]`를 적용한 lower-index 정의다. 다른 percentile 정의와 직접 비교하지 않으며, 실제 승격 실험에서는 이 정의를 고정하거나 표준 nearest-rank로 전체 모델을 일괄 재측정한다.

`structured_valid`는 모델별 출력 경로가 달라 정확도와 같은 의미의 지표가 아니다. Qwen은 자유 JSON을 직접 파싱하므로 형식 실패가 포함되고, CLIP/Florence는 정규화 함수가 항상 구조화된 결과를 만든다.

## 라이선스와 재사용 주의

이 결과는 내부 모델 선택 실험을 위한 증거이며, 데이터나 모델의 재배포 허가를 의미하지 않는다. Simuletic 데이터셋 카드는 전면부 license 표기와 본문 설명의 조건이 서로 다르게 보이므로 실제 학습·배포 전에 카드 원문과 권리 조건을 확인해야 한다. PA-100K와 각 모델도 동일하게 데이터셋 카드·모델 카드·가중치 사용 조건을 확인하고, 특히 증류 데이터와 산출물의 상업적·비상업적 사용 범위를 별도로 검토한다.

## 프로젝트 승격 판정

이 비교의 승격 판정은 `proxy person-attribute benchmark`에 한정된다. 현재 프로젝트의 production 모델을 확정한 것이 아니다.

프로젝트 승격에는 실제 영상 프레임·timestamp·cameraId·trackId·bbox/mask·검토된 identity/속성 라벨이 필요하며, 동일 case/camera/track/identity-group holdout에서 다음을 다시 측정해야 한다.

- identity top-1, recall@K
- false match rate, false reject rate, review rate
- attribute macro-F1, p50/p95 latency, GPU memory
- NanoOWL/CLIP embedded score, historical retrieval, Qwen semantic score, track/temporal/spatial consistency를 결합한 fail-closed decision

그러므로 현재 결과만으로 Qwen을 최종 판단 모델 또는 증류 teacher로 확정하지 않는다. 현재 구성 파일의 기본 운영 방향은 `NanoOWL/CLIP embedded + Qwen3-VL-8B + deterministic fusion`이며, 대형 서버 모델은 인증된 GPU 서버에서 동일 track split으로 측정한 뒤에만 비교표에 추가한다.

## 데이터셋별 해석

이번 신규 모델 실행기는 동일 45개 proxy의 전체 속성 정확도와 지연시간을 차트의 단일 계약으로 기록한다. Simuletic과 PA-100K는 라벨 분포와 촬영 조건이 달라 전체 평균만으로 실제 CCTV 성능을 확정하지 않는다. 특히 PA-100K에는 프로젝트에서 요구하는 색상·질감·복장 세부 라벨이 제한적이다. 실제 승격 때는 사람·영상·track 단위 holdout을 별도로 구성한다.

## 재실행

프로젝트 루트에서 실행한다.

```powershell
uv run --extra-index-url https://download.pytorch.org/whl/cu128 --with torch==2.11.0+cu128 --with torchvision==0.26.0+cu128 --script scripts/run_cctv_model_comparison.py --model qwen3-vl-2b --qwen-path experiments/models/Qwen3-VL-2B-Instruct --output experiments/results/qwen3-vl-2b.json
uv run --extra-index-url https://download.pytorch.org/whl/cu128 --with torch==2.11.0+cu128 --with torchvision==0.26.0+cu128 --script scripts/run_cctv_model_comparison.py --model clip-vit-b32 --output experiments/results/clip-vit-b32.json
uv run --extra-index-url https://download.pytorch.org/whl/cu128 --with torch==2.11.0+cu128 --with torchvision==0.26.0+cu128 --with transformers==4.57.0 --with einops --with timm --script scripts/run_cctv_model_comparison.py --model florence-2-large --florence-path experiments/models/Florence-2-large --output experiments/results/florence-2-large.json
uv run --extra-index-url https://download.pytorch.org/whl/cu128 --with torch==2.11.0+cu128 --with torchvision==0.26.0+cu128 --with transformers==4.57.0 --with einops --with timm --script scripts/run_cctv_model_comparison.py --model florence-2-large-ft --florence-path experiments/models/Florence-2-large-ft --output experiments/results/florence-2-large-ft.json
uv run --with sentencepiece --with protobuf --script scripts/run_cctv_model_comparison.py --model clip-vit-l14 --output experiments/results/clip-vit-l14.json
uv run --with sentencepiece --with protobuf --script scripts/run_cctv_model_comparison.py --model siglip-base --output experiments/results/siglip-base.json
uv run --with sentencepiece --with protobuf --script scripts/run_cctv_model_comparison.py --model blip-base --output experiments/results/blip-base.json
```

실측 JSON에는 `status`, checkpoint, Python, Torch, Transformers, torchvision, CUDA 버전과 source script·manifest·image SHA-256 provenance가 함께 기록된다. 모델 초기화 실패와 한 건 이상의 runtime error도 각각 `invalid_runtime` JSON으로 저장되고 비교 실행은 비정상 종료된다.

노트북은 `experiments/model_comparison_bubble_chart.ipynb`이며, Jupyter에서 위에서부터 실행한다. 결과 JSON을 바꾼 뒤 노트북을 다시 실행하면 동일 proxy 버블차트·CSV가 갱신된다. 최신 실행 결과는 error output 0개, main chart 5개 measured 좌표다. Florence 실패 2건은 `experiments/results/model_comparison_bubble_data.json`의 `failedCandidates`에 보존한다.

## 측정 실패·보류 후보

Florence-2-base는 현재 설치된 `transformers 5.14.1`에서 모델 초기화 중 `Florence2LanguageConfig`에 `forced_bos_token_id`가 없어 실패했다. 이 후보는 measured 점수로 차트에 넣지 않았다. Qwen3-VL-8B-Instruct, InternVL3.5-8B, Molmo2-8B, MiniCPM-V-4.5, Gemma 및 GLM 계열은 후보 목록에는 포함했지만 이번 측정값에는 포함하지 않았다.

Qwen2.5-VL-7B, Qwen3.5-9B의 공정 base/LoRA 결과도 원격 인증·GPU 실행 전이므로 `pending_remote_auth` 상태로 메인 차트에 넣지 않았다.

- 로컬 RTX 4050 6GB에는 대형 모델을 공정하게 올리기 어렵다.
- 사용자 서버 URL `http://70.12.130.105/user/i15a204/lab`는 현재 `/hub/login`으로 redirect되며 인증 정보가 이 작업 환경에 없다.
- 따라서 서버 모델의 실측 결과를 만들어냈다고 보고하지 않는다.

서버 인증이 가능해지면 같은 스크립트 또는 Qwen fair runner에 서버 모델 경로를 연결하고, 대체 모델도 동일한 45장/track split과 동일 JSON 계약으로 측정해야 한다. 이번 표는 “실행 가능한 후보 전체”가 아니라 “현재 환경에서 같은 계약으로 실제 측정이 완료된 후보 전체”라는 의미다.

## 다음 승인 게이트

1. 실제 CCTV 영상에서 동일 인물의 여러 프레임을 묶은 `track_id` 데이터셋을 만든다.
2. identity-positive/negative 쌍과 속성 라벨을 분리해 train/validation/test를 사람 단위로 나눈다.
3. Qwen8B와 대체 VLM의 track-level precision, recall, false accept rate, false reject rate를 측정한다.
4. 이 게이트를 통과한 teacher만 Sonnet API 라벨과 비교해 증류 대상으로 확정한다.

## 출처

- [Simuletic CCTV-Pedestrian-1K](https://huggingface.co/datasets/Simuletic/CCTV-Pedestrian-1K-Person-Attribute-Dataset)
- [PA-100K](https://huggingface.co/datasets/tuandunghcmut/PA-100K)
- [Qwen3-VL-2B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)
- [OpenAI CLIP ViT-B/32](https://huggingface.co/openai/clip-vit-base-patch32)
- [Florence-2-large](https://huggingface.co/microsoft/Florence-2-large)
- [Florence-2-large-ft](https://huggingface.co/microsoft/Florence-2-large-ft)
- [OpenAI CLIP ViT-L/14](https://huggingface.co/openai/clip-vit-large-patch14)
- [Google SigLIP base](https://huggingface.co/google/siglip-base-patch16-224)
- [Salesforce BLIP base](https://huggingface.co/Salesforce/blip-image-captioning-base)

## 2026-07-23 광범위 후보 추가 측정

추가 후보를 같은 45장 계약으로 별도 실행했다. SigLIP2 Base 224는 20.35% attribute accuracy, p50 2.910초, p95 4.310초였고, SigLIP2 Base 384는 21.75%, p50 5.965초, p95 8.377초였다. 두 모델 모두 기존 CLIP ViT-L/14 41.40%를 넘지 못했다. SmolVLM2-500M은 45장 추론은 완료했지만 응답이 JSON이 아닌 단일 토큰으로만 반환되어 structured valid rate 0%였으므로 `invalid_output_contract`로 제외했다. Qwen2.5-VL-3B는 7GB급 checkpoint 다운로드가 145MB 이후 정지해 `pending_download_network`로 남겼다.

광범위 후보의 실행 가능성·실패 원인·비교 불가 모델은 [BROAD_MODEL_CANDIDATES.md](BROAD_MODEL_CANDIDATES.md)에 기록했다. 추가 모델을 포함한 새 버블차트와 실행된 노트북은 [broad_model_comparison.ipynb](broad_model_comparison.ipynb), [broad_model_comparison_proxy_bubble.png](results/broad_model_comparison_proxy_bubble.png), [broad_model_comparison_proxy_coordinates.csv](results/broad_model_comparison_proxy_coordinates.csv)이다.

이번 확장에서도 동일 계약으로 유효하게 측정된 최고 점수는 CLIP ViT-L/14 41.40%다. 이 값은 실제 CCTV identity accuracy가 아니며 85% 배포 gate를 충족하지 않는다. 서버 후보 Gemma 3, InternVL3, Molmo2, MiniCPM-V, Qwen2.5-VL은 GPU 서버에서 같은 계약으로 재측정해야 한다.
