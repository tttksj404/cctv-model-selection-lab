# AI Worker 발표 시각자료

이 폴더의 SVG와 JSON은 저장소에 보존된 실험 결과에서 생성됐다.

| 파일 | 용도 |
|---|---|
| `tools/assets/claude_model_orchestration.svg` | Claude CLI가 생성한 ASCII-safe SVG 원본; 재생성 스크립트가 발표 산출물로 복사 |
| `architecture_pipeline.svg` | 중앙 서버–RabbitMQ–AI Worker–MinIO/S3–대시보드·Jetson 구조 |
| `model_orchestration.svg` | YOLO→ByteTrack→CLIP/SOLIDER/속성/보조 계층→late fusion→Top-K 오케스트레이션 |
| `identity_model_bubble.svg` | CHIRLA strict Rank-1 × 모델 규모, 버블 크기=Recall@5 |
| `identity_strict_ranked.svg` | strict identity 모델 순위와 현재 선택 모델 |
| `model_evolution.svg` | 같은 평가에서 초기 baseline부터 현재 모델까지의 발전 폭 |
| `sonnet_ablation.svg` | PA-100K와 CCTV proxy Sonnet ablation 분리 비교 |
| `zone_proxy_validation.svg` | 4구역 synthetic proxy route별 accuracy/Wilson 하한 |
| `evidence_status.svg` | verified / proxy / measured / not promoted 상태표 |
| `presentation_data.json` | 원본 수치 snapshot, 평가 범위, SHA-256 provenance |

재생성:

```powershell
cd ai-worker
python tools/build_ai_presentation.py
```

해석과 발표용 대본은 [`docs/AI_PRESENTATION_AND_STUDY_APPENDIX.md`](../../docs/AI_PRESENTATION_AND_STUDY_APPENDIX.md)에 있다.

