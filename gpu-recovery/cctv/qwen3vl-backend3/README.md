# Qwen3-VL backend vertical slice

Spring Boot가 호출할 수 있는 후보 속성 검증 API의 첫 계약입니다. 기본 provider는 `mock`이며, GPU 서버에서 `QWEN_PROVIDER=qwen`으로 바꾸면 `<redacted-local-path> 첫 분석 요청 때만 읽습니다.

```powershell
uv sync
uv run pytest
uv run uvicorn qwen_backend.main:app --app-dir src --host 127.0.0.1 --port 8080
```

API는 지금 서버 로컬 이미지 경로만 받습니다. MinIO `imageKey` 또는 multipart 업로드는 Spring/MinIO 계약이 확정된 뒤 이 provider 경계 앞에 붙입니다. Sonnet teacher는 아직 호출하지 않으며, `fixtures/teacher_labels.jsonl`은 구조 확인용 redacted fixture일 뿐 학습 truth가 아닙니다.

## GPU server

기존 `qwen3vl` Conda 환경을 재사용합니다. Docker, root 권한, 공식 Qwen clone, 모델 파일 변경은 필요하지 않습니다.

```bash
cd <redacted-local-path>
conda run -n qwen3vl python -m uvicorn qwen_backend.main:app --app-dir src --host 127.0.0.1 --port 18080
```

