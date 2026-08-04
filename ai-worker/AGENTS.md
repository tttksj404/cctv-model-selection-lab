# AI Worker 실행 지침

이 디렉터리에서 작업하는 모든 에이전트는 아래 임무 순서를 최우선으로 따른다.

## 제품 임무

1. AI Worker는 중앙 서버가 등록한 작업을 받아 마지막 목격 시각부터 현재까지의
   **과거 녹화본**에서 실종자 후보를 찾는다.
2. 후보 결과에는 사건, 카메라, 탐지 시각 또는 `frameOffsetMs`, 사람 crop,
   원본 프레임, 바운딩 박스, 모델·보정기 버전과 점수 종류를 포함한다.
3. 중앙 서버는 반환된 후보로 경로를 만들고 카메라 연결 관계와 이동 가능 시간을
   사용해 다음 녹화본 작업을 계획·등록한다. AI Worker는 이 작업을 받아 지정된
   구간을 분석하고 근거를 반환한다.
4. Jetson Orin Nano는 관할 4개 카메라의 **실시간 탐지**를 담당한다. Jetson 후보는
   중앙 후보 목록에서 `JETSON_REALTIME / URGENT`로 가장 먼저 검토하게 한다.
5. AI Worker는 Jetson을 직접 제어하거나 실시간 탐지를 대신하지 않는다. Jetson이
   후보를 찾지 못해도 AI Worker의 과거 후보와 경로는 수사 보조 자료로 남긴다.

## 금지되는 방향 전환

- 4구역 확률이나 대표 카메라 선택 실험을 제품의 주기능으로 승격하지 않는다.
- 후보 점수만으로 동일인, 현재 위치 또는 다음 이동지를 확정하지 않는다.
- 보정되지 않은 similarity를 확률로 표현하지 않는다.
- AI Worker가 중앙 서버의 lease, idempotency, heartbeat, retry 책임을 가져가지 않는다.

구역 확률 관련 코드와 문서는 비교 연구용으로만 유지한다. 새 기능은
`docs/AI_WORKER_CORE_MISSION.md`의 역할·상태·계약을 먼저 만족해야 한다.

## 변경 검증

- Python 계약 변경: `uv run pytest -q`, `uv run ruff check src tests`,
  `uv run basedpyright`
- 중앙 서버 계약 변경: 해당 Maven 단위 테스트와 컴파일
- 모델 성능 주장은 identity/track-heldout 평가와 독립 검수 결과가 있을 때만 작성
