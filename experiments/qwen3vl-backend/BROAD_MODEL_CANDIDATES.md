# CCTV 사람 속성 모델 광범위 후보 조사

기준일: 2026-07-23

## 비교 계약

주 비교표는 기존과 같은 45개 사람 크롭을 사용한다.

- Simuletic 15장, PA-100K 30장
- 33개 그룹
- 샘플별 관측 가능 라벨만 채점
- 속성 정확도, 이미지 exact match, track exact match, p50/p95 latency를 동일 계산
- 이 proxy는 CCTV 동일인 식별 정확도가 아니다

## 후보 상태

| 후보 | 역할 | 상태 | 사유 |
|---|---|---|---|
| SigLIP2 Base 224 | zero-shot vision encoder | 측정 완료 | attribute accuracy 20.35%, p95 4.310초 |
| SigLIP2 Base 384 | zero-shot vision encoder | 측정 완료 | attribute accuracy 21.75%, p95 8.377초 |
| Qwen2.5-VL-3B | 서버 VLM | 다운로드 보류 | 7GB급 가중치가 145MB 이후 로컬 Xet 전송 정지 |
| Gemma 3 4B IT | 서버 VLM | invalid_runtime | Hugging Face 접근 권한 제한으로 로컬 추론 불가 |
| SmolVLM2 500M Video | 경량 VLM | invalid_output_contract | 45개 실행은 완료했지만 JSON 구조화 출력 0건 |
| InternVL3-2B | 서버 VLM | invalid_runtime | 현재 Transformers 런타임에서 InternVLConfig 인식 실패 |
| Molmo2-4B | 서버 VLM | 실행 대기 | custom code와 최신 Transformers 계약 필요 |
| MiniCPM-V 4.5 int4 | 서버 VLM | 실행 대기 | custom chat API와 6.5GB checkpoint |
| Phi-3.5 Vision | 서버 VLM | 실행 대기 | custom code, 구형 vision API |
| PaliGemma2 3B | fine-tuning 중심 VLM | 비교 보류 | Google model terms/auth 및 task head 계약 필요 |
| DINOv2 Base | feature extractor | 비교 불가 | zero-shot 속성 출력 head가 없으므로 검색/ReID 별도 평가 대상 |
| Grounding DINO / SAM2 | detection/segmentation | 비교 불가 | box/mask/tracking 출력이며 사람 속성 분류 모델이 아님 |

## 현재 결론

이 표의 후보 수가 많아도 동일 계약으로 실제 실행된 값만 모델 버블차트의 measured 영역에 넣는다. 실패한 초기화·다운로드 보류는 정확도 0으로 변환하지 않는다. 서버에서 Qwen2.5, Gemma, InternVL, Molmo를 실행할 때도 이 계약과 동일한 45장/33그룹/필드 분모를 사용해야 한다. 현재 measured 최고는 CLIP ViT-L/14 41.40%이며 SigLIP2 384도 21.75%로 이를 넘지 못했다.

## 공식 모델 카드

- [SigLIP2 Base 224](https://huggingface.co/google/siglip2-base-patch16-224)
- [SigLIP2 Base 384](https://huggingface.co/google/siglip2-base-patch16-384)
- [Qwen2.5-VL-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct)
- [Gemma 3 4B IT](https://huggingface.co/google/gemma-3-4b-it)
- [SmolVLM2 500M Video Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM2-500M-Video-Instruct)
- [InternVL3-2B](https://huggingface.co/OpenGVLab/InternVL3-2B)
- [Molmo2-4B](https://huggingface.co/allenai/Molmo2-4B)
- [MiniCPM-V 4.5](https://huggingface.co/openbmb/MiniCPM-V-4_5)
- [Phi-3.5 Vision](https://huggingface.co/microsoft/Phi-3.5-vision-instruct)
- [DINOv2 Base](https://huggingface.co/facebook/dinov2-base)
