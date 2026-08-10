# AI Worker 하드코딩·운영 리스크 하드닝

기준일: 2026-08-03

이 문서는 AI Worker에서 **배포 환경에 따라 달라져야 하는 값**과 **프로젝트 프로토콜·알고리즘이 의도적으로 고정하는 값**을 구분한다. 모든 숫자를 무조건 환경변수로 옮기면 잘못된 운영 설정이 모델 동작을 조용히 바꾸므로, 환경 의존 값은 검증된 settings로, 계약 값은 단일 상수로 관리한다.

## 이번에 막은 문제

- 모델 경로·장치·검출 confidence·frame stride·sampling interval·crop margin·모델 가중치·batch size를 `QWEN_CANDIDATE_*` settings로 통합했다. 범위를 벗어난 값과 두 모델 가중치가 모두 0인 설정은 시작 시 실패한다.
- 노트북의 signed 녹화본·증거 파일 크기, 중앙 API URL, API key placeholder를 settings 단계에서 검증한다. 잘못된 `Content-Length`도 다운로드를 시작하지 않고 실패한다.
- 중앙 API의 connection pool·timeout·chunk 크기·transport retry를 `EYESONU_AI_WORKER_*` settings로 통합했다. claim/heartbeat/complete/fail 같은 변경 POST의 기본 transport retry는 `0`이다. 재시도를 켜려면 중앙 API가 idempotency 계약을 보장해야 한다.
- Python worker와 Java backend의 worker path/header/max-size 값을 각 언어 내부의 단일 protocol constant로 모았다. `/api/v1/internal/recording-analysis-jobs`, `X-Worker-Key`, `X-Worker-Claim-Token`, 후보 URL batch 한도를 바꿀 때는 양쪽 contract test를 함께 통과해야 한다.
- 현재 기획의 4개 구역 × 구역당 4개 카메라 배치는 `zone_topology.py`에서만 정의한다. 실제 관할 구조가 바뀌면 이 파일과 API 계약 테스트를 함께 갱신한다.
- 모델 기본 경로에서 개발자의 `/home/...` 절대 경로를 제거하고 저장소 기준 상대 경로(`./models`, `./data`, `./external`)로 바꿨다.
- realtime tracker, minimum box area, attribute score weight도 runtime config로 검증하여 코드 내부의 숨은 실행값을 제거했다.

## 의도적으로 코드에 남긴 값

- `/api/v1/internal/recording-analysis-jobs`, `X-Worker-Key`, `X-Worker-Claim-Token`, RabbitMQ exchange/routing key/queue, 후보·오류 메시지 최대 길이는 중앙 서버와 공유하는 **프로토콜 계약**이다. 환경변수로 바꾸면 worker와 backend가 서로 다른 API를 호출할 수 있으므로 상수로 유지한다.
- zone posterior의 transition prior, camera-selection score weight, decision score weight와 crop geometry는 현재 실험에서 사용하는 **알고리즘 calibration 값**이다. 배포별 설정값으로 숨기지 않고 이름 있는 상수로 유지했으며, 새 데이터로 calibration할 때는 실험 결과와 함께 소스·회귀 테스트를 갱신한다.

## 운영 전 체크

1. `ai-worker/.env.example`을 기준으로 실제 `.env`를 만들거나 `Start-NotebookAiWorker.ps1 -EnvFile <path>`에 별도 dotenv 파일을 넘긴다. 모델 경로·중앙 API 주소·RabbitMQ URL/queue를 환경에 맞게 지정한다.
2. `EYESONU_AI_WORKER_TRANSPORT_RETRIES=0`을 유지한다. 중복 처리 방지가 필요한 변경 요청에는 서버 idempotency key 계약을 먼저 추가한다.
3. 다음 검증을 실행한다.

```powershell
uv run pytest -q
uv run ruff check src tests
uv run basedpyright
uv lock --check
```

4. Java backend도 같은 worker protocol version과 max-size를 사용하는지 `mvnw.cmd test`로 확인한다.
5. 실제 중앙 서버에 대한 claim preflight는 코드 테스트와 별개다. `INVALID_WORKER_KEY` 또는 HTTP `401/403`이면 노트북 코드에서 임의 우회하지 말고 서버 배포의 `WORKER_AUTHENTICATION_KEY`·권한·header 계약을 수정해야 한다.

## 변경 시 금지사항

- timeout, retry, file-size limit, model path를 함수 내부 literal로 다시 추가하지 않는다.
- 변경 POST에 자동 retry를 추가하지 않는다. 서버의 idempotency 보장과 재처리 정책이 먼저다.
- 4×4 토폴로지를 다른 파일에 다시 literal로 복사하지 않는다.
- 정확도·일반화·실서비스 성공률을 테스트 데이터가 아닌 코드 설정만으로 주장하지 않는다.

