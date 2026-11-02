# CLIP ViT-L/14 서버 결과 provenance

이 디렉터리의 JSON·CSV는 원격 GPU 서버에서 실행한 결과를 차트용으로 정리한 파생 데이터다. 원격 원천 JSON은 저장소에 복사하지 않았으므로 이 문서는 원천 위치와 검증 범위를 기록하는 provenance record이며, 원천 파일의 SHA-256을 대신하지 않는다.

## server-full

- 원격 원천 ID: `server_full.json`
- 원격 상대 경로: `clip_vitl14_server/experiments/results/server_full.json`
- 조건: PA-100K 80k/10k/10k, SOLIDER teacher head, CLIP hard head, CLIP logit KD
- 로컬 검증: 차트 JSON·CSV·MD 사이의 수치 일치만 확인

## finetune-probe

- 원격 원천 ID: `clip_vitl14_finetune_probe.json`
- 원격 상대 경로: `clip_vitl14_server/experiments/results/clip_vitl14_finetune_probe.json`
- 조건: PA-100K 20k/5k/5k probe, CLIP ViT-L/14 마지막 두 vision block fine-tune
- 로컬 검증: validation 선택 test mA 기록과 probe 비동률 표식 확인

## 공통 제한

- 모든 수치는 PA-100K 속성 proxy이며 CCTV identity/track-heldout 정확도가 아니다.
- 원격 원천 JSON과 SHA-256은 현재 로컬 산출물에 포함하지 않았다.
- 최종 모델 승격 전에는 원격 원천 파일을 보존하고 SHA-256 manifest를 추가해야 한다.
