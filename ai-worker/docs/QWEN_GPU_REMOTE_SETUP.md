# GPU 서버 Qwen review 연결

## 먼저: 기존 노트북 Qwen 로더 재사용

바탕화면 바로가기의 카메라 실행 파일은 `qwen3vl-backend/.venv`의
`eyesonu-realtime.exe`이며, 그 화면 자체는 YOLO·CLIP·SOLIDER 실시간 경로다. 같은
프로젝트의 기존 Qwen 비교 실행기가 사용하던 Qwen 부분은
`Qwen3VLForConditionalGeneration`과 `AutoProcessor`를 직접 로드하는 방식이다.

현재 `ai-worker`의 로컬 Qwen provider가 이 로더 방식을 그대로 사용하도록 맞췄다.
따라서 `qwen_vl_utils`나 별도 HTTP 서버가 없어도 노트북의 녹화 crop을 Qwen review에
넣을 수 있다. 모델은 lazy-load되고 프로세스 생명주기 동안 캐시된다.

노트북의 비공개 env 파일에는 다음 값만 활성화한다.

```env
QWEN_PROVIDER=qwen
QWEN_MODEL_PATH=C:/Users/SSAFY/Desktop/2학기/qwen3vl-backend/experiments/models/Qwen3-VL-2B-Instruct
QWEN_MODEL_VERSION=Qwen3-VL-2B-Instruct-legacy-loader
QWEN_MAX_NEW_TOKENS=128
QWEN_DEVICE_MAP=auto
```

`--env-file`은 워커 시작 시 한 번만 읽는다. 이미 실행 중인 워커는 기존 설정을
계속 사용하므로, 처리 중인 job이 없는 것을 확인한 뒤 워커를 정상 재시작해야 위
설정이 반영된다.

현재 워커는 중앙 서버의 영상·lease·evidence 계약을 그대로 유지하고, 위 Qwen은
상위 후보 crop의 속성·의미 검토 단계에서만 호출한다. Qwen이 실패해도 후보 생성
결과를 Qwen 결과로 위조하지 않고 `unavailable`/`failed` trace를 남긴다.

## 결론

중앙 서버는 변경하지 않고, 노트북의 `ai-worker`가 상위 후보 crop을 GPU 서버의
OpenAI-compatible `/v1/chat/completions`로 보내는 구성이 가능하다. Qwen은 전체
영상 탐색기가 아니라 상위 후보의 색상·복장·헤어·액세서리 의미 검토기로 사용한다.

현재 워커에는 이 remote adapter가 들어갔지만, `70.12.130.105`에서 노트북이
접근할 수 있는 vLLM `/v1/models` endpoint는 아직 응답하지 않았다. JupyterLab URL은
개발 환경 접속 주소이지 Qwen 추론 API가 아니므로, 서버에서 별도 vLLM endpoint를
실행해야 한다.

## 서버 실행

`qwen3vl-backend/deployment/docker-compose.qwen.yml`을 GPU 서버에 복사한 뒤,
서버에서 다음을 준비한다.

```env
QWEN_MODEL_ID=Qwen/Qwen3.5-9B
QWEN_SERVED_MODEL_NAME=qwen-active
QWEN_MAX_MODEL_LEN=8192
QWEN_GPU_MEMORY_UTILIZATION=0.90
QWEN_MAX_NUM_SEQS=2
QWEN_BIND_HOST=127.0.0.1
QWEN_PORT=8000
```

```bash
docker compose --env-file .env -f docker-compose.qwen.yml up -d
curl http://127.0.0.1:8000/v1/models
```

노트북에서 직접 접근할 때는 방화벽으로 포트를 무작정 공개하지 말고 SSH tunnel이나
인증된 reverse proxy를 사용한다.

```bash
ssh -L 18000:127.0.0.1:8000 <gpu-server-user>@<gpu-server-host>
```

노트북 워커 설정은 다음과 같다.

```env
QWEN_CANDIDATE_QWEN_REVIEW_PROVIDER=remote
QWEN_CANDIDATE_QWEN_REMOTE_BASE_URL=http://127.0.0.1:18000/v1
QWEN_CANDIDATE_QWEN_REMOTE_MODEL=qwen-active
QWEN_CANDIDATE_QWEN_REMOTE_API_KEY=<GPU 추론 서버 전용 키>
QWEN_CANDIDATE_QWEN_REMOTE_TIMEOUT_SECONDS=90
```

중앙 서버의 Device Key나 Worker Key를 GPU 추론 API 인증키로 재사용하지 않는다.

## 양자화 선택

GPU 서버 VRAM이 충분하면 비양자화 `float16/bfloat16` 모델을 우선 측정한다. 양자화
모델은 메모리와 지연에 유리하지만 작은 글자·질감·액세서리에서 일부 성능 저하가
가능하다. 다만 Qwen은 상위 후보 검토기이므로 전체 identity 성능은 SOLIDER/PAR,
색상 게이트, track fusion과 함께 평가해야 한다. 동일한 identity/track-heldout
split에서 비양자화와 4-bit를 각각 비교하기 전에는 어느 쪽이 프로젝트에서 더
정확하다고 단정하지 않는다.
