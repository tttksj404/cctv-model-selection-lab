# EYES:ON U AI Worker

`ai-worker`는 중앙 AI 처리 서버에서 과거 영상을 검색하고, 개발용 USB 카메라에서
인상착의 기반 후보 탐색을 검증하는 Python 워커입니다. 모델 구현은 교체 가능한
경계 뒤에 두어 SOLIDER, CLIP, Qwen 계열 모델을 바꾸더라도 백엔드 계약을 유지합니다.

제품의 핵심 임무는 중앙 서버가 지정한 구간의 **과거 녹화본 후보 검색**입니다.
AI Worker는 후보 근거를 반환하고, 중앙 서버가 이를 시간순 경로로 구성해 다음
카메라의 녹화본 분석 작업을 계획·등록합니다. Jetson Orin Nano는 별도로 관할 4개
화면의 실시간 탐지를 맡습니다. 현재 코드는 Jetson 후보의
`JETSON_REALTIME / URGENT` 저장·조회 계약까지 준비했으며 관리자 화면 배지는
후속 연결 범위입니다.
역할과 작업 등록 알고리즘은
[AI Worker 핵심 임무](docs/AI_WORKER_CORE_MISSION.md)를 기준으로 합니다.

현재 실시간 데모는 사람의 신원을 확정하지 않습니다. YOLO 추적 결과에
CLIP ViT-L/14와 색상 규칙을 적용해 `인상착의 유사도 높음`, `인상착의 재검토`,
`인상착의 유사도 낮음`을 표시하는 후보 선별 도구입니다. 화면의 유사도점수는 보정된
확률이 아닌 휴리스틱 증거 점수입니다.

## 바로 실행

Windows와 NVIDIA GPU 기준입니다. Python 3.11 이상과
[uv](https://docs.astral.sh/uv/)가 필요합니다.

```powershell
cd ai-worker
uv sync --extra realtime --frozen
New-Item -ItemType Directory -Force models
# 검증된 yolo11n.pt 파일을 models/yolo11n.pt에 배치
uv run --extra realtime eyesonu-realtime
```

기본 프로필은 다음 인상착의입니다.

> 회색 반팔, 검은색 바지, 안경, 넘긴 머리

실행 후 조작:

- `Q` 또는 `ESC`: 종료
- `S`: 현재 대시보드 화면 저장
- 기본 저장 위치: `artifacts/realtime_demo/latest.jpg`
- 자동 저장은 기본적으로 꺼져 있음

다른 카메라나 YOLO 가중치를 지정할 수 있습니다.

```powershell
uv run --extra realtime eyesonu-realtime `
  --camera-index 1 `
  --yolo-weights models/yolo11n.pt `
  --auto-save-interval 30 `
  --evidence-path artifacts/realtime_demo/camera-1.jpg
```

현재 프로필의 속성 정의와 CLIP 프롬프트는
`src/qwen_backend/realtime_models.py`의 `AppearanceProfile.default_demo()`에 함께
있습니다. 화면 문구만 바꾸고 프롬프트를 그대로 두는 불일치를 막기 위해 실시간 CLI는
부분적인 프로필 덮어쓰기를 허용하지 않습니다.

자세한 판정 의미와 운영 제한은
[실시간 USB 카메라 인상착의 유사도 가이드](docs/REALTIME_WEBCAM_DEMO.md)를 참고하세요.

## 중앙 AI 처리 서버 실행

환경 변수는 `.env.example`을 기준으로 별도 `.env`에 넣습니다. 실제 키와 인증 정보는
저장소에 커밋하지 않습니다.

```powershell
uv sync --frozen
$env:QWEN_INTERNAL_API_KEY = "<secret-store에서 주입>"
uv run uvicorn qwen_backend.main:app --host 127.0.0.1 --port 8080
```

`/health`를 제외한 모든 API는 provider 종류와 무관하게 `X-Internal-API-Key`를
요구한다. 키가 없으면 보호 API는 `503`, 키가 틀리거나 누락되면 `401`로 닫힌다.
외부 인터페이스 바인딩은 중앙 백엔드 프록시·방화벽·TLS가 준비된 별도 연동 작업에서만
허용한다.

## 노트북 상주 AI Worker 실행

추론을 이 노트북에서 수행하려면 `.env.example`의 `EYESONU_AI_WORKER_*` 항목을 실제
중앙 백엔드 URL·워커 키·로컬 모델 경로에 맞게 설정한다. 워커는 중앙 서버에서 작업을
claim하고 signed 녹화 URL을 내려받은 뒤 로컬 `CandidateRuntimeEngine`을 실행하고,
lease heartbeat와 구조화된 결과를 중앙 서버로 반납한다.

```powershell
uv sync --extra realtime --frozen
uv run eyesonu-ai-worker --once
uv run eyesonu-ai-worker --log-level INFO
```

노트북에 이미 받은 `ai.env.txt`를 그대로 사용할 때는 복사하거나 키를 출력할 필요 없이
다음처럼 경로만 넘긴다. 이 파일에는 중앙 서버 URL·Worker Key뿐 아니라 RabbitMQ URL과
queue도 있어야 한다.

```powershell
.\scripts\Start-NotebookAiWorker.ps1 `
  -EnvFile C:\Users\SSAFY\Desktop\ai.env.txt `
  -Once
```

`CENTRAL_API_BASE_URL`/`CENTRAL_API_WORKER_KEY`와 `RABBITMQ_URL`/`RABBITMQ_QUEUE`는
기존 노트북 설정 파일 호환 이름이며, `EYESONU_AI_WORKER_*` 이름도 동일하게 지원한다.

중앙 워커 계약의 endpoint, lease, 실패 재시도와 로컬 경로 비노출 정책은
[노트북 상주 AI Worker 실행 계약](docs/NOTEBOOK_AI_WORKER_RUNTIME.md)을 참고한다.
RabbitMQ 기반 수신·lease·증거 업로드의 운영 계약은
[RabbitMQ 노트북 AI Worker 전송 계약](docs/RABBITMQ_NOTEBOOK_WORKER_TRANSPORT.md)을 참고한다.

아래 구역 확률 API는 기본 `qwen_backend.main:app`에 등록되지 않는 별도 비교 연구
앱입니다. 개발용 신뢰 레지스트리와 4×4 요청 계약만 확인하며, research 앱 자체가
production 환경에서는 시작을 거절합니다.

```powershell
$env:QWEN_PROBABILITY_EVIDENCE_SIGNING_KEY = "development-only-key-at-least-32-characters"
uv run uvicorn qwen_backend.research_app:app --host 127.0.0.1 --port 8081
uv run python scripts/sample_zone_probability_request.py |
  curl.exe -sS -X POST http://127.0.0.1:8081/v1/search-routing/probability `
    -H "Content-Type: application/json" `
    -H "X-Internal-API-Key: $env:QWEN_INTERNAL_API_KEY" --data-binary "@-"
```

같은 키를 연구 앱 프로세스에도 주입해야 한다. 연구용 키는 저장소나 요청 본문에
넣지 않고 별도 secret store에서 주입한다.

중앙 AI 워커의 기본 흐름은 다음과 같습니다.

1. 백엔드가 사건번호와 MinIO/S3 객체 정보를 전달합니다.
2. 워커가 입력 영상을 로컬 작업 디렉터리로 가져옵니다.
3. 모델 어댑터가 사람 트랙과 후보점수를 계산합니다.
4. 후보 crop, 프레임 시점, 바운딩 박스와 모델 메타데이터를 반환합니다.
5. 백엔드가 결과를 DB와 프론트 후보 검토 화면에 연결합니다.

API와 저장소 연동 계약은 다음 문서에 정리되어 있습니다.

- [AI Worker 핵심 임무와 중앙 작업 등록 계약](docs/AI_WORKER_CORE_MISSION.md)
- [AI 검색 런타임 연동](docs/AI_SEARCH_RUNTIME_INTEGRATION.md)
- [모델 선택과 증류 결정](docs/MODEL_SELECTION_AND_DISTILLATION_DECISION.md)
- [SOLIDER 서버 속성 통합](docs/SOLIDER_SERVER_ATTRIBUTE_INTEGRATION.md)

다음 자료는 운영 임무가 아닌 구역 확률 비교 연구 기록입니다.

- [구역별 과거 영상 탐색 실험](docs/ZONE_CAMERA_SEARCH_ROUTING.md)
- [구역별 확률·카메라 선택 실험](docs/ZONE_MISSING_PERSON_PROBABILITY.md)
- [구역 정책 실험 결과](docs/ZONE_POLICY_EXPERIMENT_20260801.md)
- [합성 proxy 모델 비교](docs/ZONE_REGION_MODEL_EXPERIMENT_20260802.md)
- [연결 없는 검증 대시보드](dashboard/README.md)

## 검증

```powershell
uv run --extra realtime pytest -q
uv run --extra realtime ruff check src tests
uv run --extra realtime basedpyright
uv lock --check
```

구역 대시보드는 현재 mock-only로 고정되어 중앙 백엔드·Jetson·AI Worker API를 호출하지
않습니다. `cd dashboard; npm.cmd test; npm.cmd run build`로 응답 불변식과 화면 빌드를
별도로 검증합니다. 향후 연결은 브라우저에서 내부 API를 직접 호출하지 않고 중앙 백엔드
프록시 계약을 거치는 별도 작업으로 남겨 두었습니다.

기본 테스트는 모델 가중치·원본 CCTV crop·대형 실행 노트북 없이 재현 가능한 배포 계약만
실행합니다. 별도 연구 데이터 번들이 준비된 환경에서는 다음 명령으로 보존된
track-heldout/person-crop 산출물 계약도 검증합니다.

```powershell
uv run --extra realtime pytest -q -m external_research_artifact `
  -o "addopts="
```

실시간 데모의 CLI 경계도 확인합니다.

```powershell
uv run --extra realtime eyesonu-realtime --help
uv run --extra realtime eyesonu-realtime --camera-index 99 --headless --max-frames 1
```

두 번째 명령은 카메라 열기 실패를 한 줄 오류로 반환하는 음수 경로입니다.

## 모델 파일과 데이터 정책

- YOLO 가중치는 `models/` 아래에만 배치하고
  `configs/realtime_model_manifest.json`의 SHA-256과 일치해야 합니다. 미등록 파일,
  URL, 변조된 파일은 실행 전에 거부합니다.
- CLIP ViT-L/14 체크포인트는 Hugging Face 캐시를 사용합니다.
- 모델 가중치, `.env`, 원본 CCTV 영상, 사람 crop, 실시간 캡처 이미지는 Git에 넣지
  않습니다.
- `artifacts/`, 실험 데이터와 체크포인트는 재현 문서만 남기고 파일 자체는 외부
  저장소에서 관리합니다.
- `experiments/results/evidence/zone_region_*_20260802*.gz`는 4구역 합성 proxy 실행의
  selection/sealed 분리와 모델 SHA를 독립 검증하기 위한 압축 증거 사본입니다. 원본
  바이트 SHA와 원격 GPU 경로를 문서에 고정하며, 운영 가중치나 CCTV 데이터로 취급하지
  않습니다.
- `experiments/results/evidence/zone_region_evidence_bundle_20260802.json`은 각 압축 파일의
  저장 SHA와 압축 해제 원본 SHA, 저장소 상대 경로, GPU 원격 경로를 연결합니다.
- 후보점수 임계값은 로컬 데모용입니다. 실제 서비스의 자동 판정 임계값은
  identity/track-heldout 데이터와 독립 검수 결과로 별도 보정해야 합니다.

## 디렉터리

```text
ai-worker/
├─ src/qwen_backend/     FastAPI, 모델 어댑터, 실시간 데모
├─ tests/                계약·점수·런타임 회귀 테스트
├─ scripts/              데이터 준비, 학습, 평가 도구
├─ configs/              모델·실험 설정
├─ deployment/           GPU 서버 실행 구성
└─ docs/                 연동·학습·운영 문서
```
