# 실시간 임베디드 연동 명세

임베디드·Jetson 실시간 처리기가 구현해야 하는 통신 계약만 정리한 문서입니다.
사건 등록, 관제 화면, 녹화영상 분석, 서버 내부 저장 구조는 범위에 포함하지 않습니다.

방향 표기: `서버 → 임베디드`는 서버가 임베디드로 전달하는 데이터이고, `임베디드 → 서버`는 임베디드가 서버로 전달하는 데이터입니다.

## 1. 구현 범위

임베디드 처리기는 다음 세 가지를 수행합니다.

1. RabbitMQ에서 검색 대상 변경 알림을 받습니다.
2. 서버 API에서 최신 검색 대상 목록을 동기화하고 카메라 영상을 분석합니다.
3. 탐지 결과의 이미지 업로드가 끝난 뒤 후보 이벤트를 서버에 등록합니다.

서버 API 호출과 Device Key 보관은 미디어 서버가 담당합니다. Jetson이 별도 프로세스로 동작하는 경우 미디어 서버가 제공하는 인증·업로드 경로를 사용합니다.

## 2. 접속 정보

| 항목 | 값 |
|---|---|
| 검색 대상 API | `GET /api/v1/device/search-targets` |
| 후보 이벤트 API | `POST /api/v1/device/candidate-events` |
| 인증 헤더 | `X-Device-Key: {deviceKey}` |
| 메시지 Exchange | `search.target.exchange` |
| Exchange 타입 | `topic` |
| Routing key | `search.target.updated` |
| 실시간 큐 | `search.target.realtime.queue` |
| 메시지 형식 | JSON, durable queue, persistent message |

## 3. 서버 → 임베디드: RabbitMQ 메시지

### 검색 대상 갱신

`SEARCH_TARGET_UPDATED`는 탐색 시작 또는 조건·카메라 변경을 의미합니다.

전달 방향: `서버 → RabbitMQ → 임베디드`

```json
{
  "commandId": "c2c8d8a0-0e85-4a29-9e34-9bd0f7a5a001",
  "eventType": "SEARCH_TARGET_UPDATED",
  "caseId": 101,
  "updatedAt": "2026-07-31T02:00:00Z",
  "occurredAt": "2026-07-31T02:00:00Z"
}
```

| 필드 | 타입 | 처리 방법 |
|---|---|---|
| `commandId` | string | 중복 처리 방지용 ID |
| `eventType` | string | `SEARCH_TARGET_UPDATED` 또는 `SEARCH_TARGET_DISABLED` |
| `caseId` | number | 동기화할 사건 ID |
| `updatedAt` | string/null | 변경 시각. 직접 판정하지 말고 API 결과를 기준으로 사용 |
| `occurredAt` | string | UTC 발행 시각 |

### 검색 대상 비활성화

`SEARCH_TARGET_DISABLED`를 받으면 해당 `caseId`의 분석을 중지하고 로컬 작업 목록에서 제거합니다.

전달 방향: `서버 → RabbitMQ → 임베디드`

```json
{
  "commandId": "c2c8d8a0-0e85-4a29-9e34-9bd0f7a5a002",
  "eventType": "SEARCH_TARGET_DISABLED",
  "caseId": 101,
  "updatedAt": "2026-07-31T03:10:00Z",
  "occurredAt": "2026-07-31T03:10:00Z"
}
```

### 메시지 처리 규칙

- `commandId`가 이미 처리된 메시지면 작업을 다시 시작하지 않습니다.
- `SEARCH_TARGET_UPDATED` 수신 후 `GET /search-targets`를 호출해 전체 목록을 최신 상태로 교체합니다.
- 동기화와 로컬 작업 반영이 끝난 뒤에만 ACK합니다.
- ACK는 `임베디드 → RabbitMQ` 방향으로 보내며, 서버가 메시지를 정상 처리한 것으로 간주하는 시점입니다.
- 처리 중 장애가 나면 ACK하지 않아 RabbitMQ가 재전달하도록 합니다.
- 프로세스 시작·RabbitMQ 재연결 후에는 메시지를 기다리지 말고 검색 대상 API를 먼저 호출합니다.
- API 호출이 실패해도 기존 작업을 즉시 삭제하지 말고, 다음 재시도까지 기존 설정을 유지합니다.

## 4. 양방향: 검색 대상 동기화 API

### 요청

전달 방향: `임베디드 → 서버`

```http
GET /api/v1/device/search-targets
X-Device-Key: {deviceKey}
Accept: application/json
If-None-Match: "previous-etag"
```

첫 호출에는 `If-None-Match`를 보내지 않습니다. 응답의 `ETag`를 저장했다가 다음 호출에 사용합니다.

### 응답 데이터

전달 방향: `서버 → 임베디드`

```json
{
  "timestamp": "2026-07-31T02:00:00Z",
  "data": [
    {
      "caseId": 101,
      "caseNumber": "EFU-20260730-0001",
      "searchConditions": [
        {
          "conditionId": 10,
          "prompt": "a man wearing a black short sleeve top and black pants",
          "exclusionPrompt": "",
          "searchStart": "2026-07-31T00:00:00Z",
          "searchEnd": "2026-07-31T06:00:00Z",
          "searchArea": "강남역 일대",
          "similarityThreshold": 0.72
        }
      ],
      "cameras": [{ "cameraId": 2, "cameraCode": "CAM-001" }],
      "updatedAt": "2026-07-31T02:00:00Z"
    }
  ]
}
```

| 응답 | 임베디드 처리 |
|---|---|
| `200 OK` | `data` 전체를 최신 스냅샷으로 교체하고 `ETag` 저장 |
| `200 OK`, `data: []` | 모든 사건의 실시간 분석 중지 |
| `304 Not Modified` | 기존 로컬 설정 유지 |
| `401` | 인증 설정 확인 후 재시도. 잘못된 Key를 무한 재시도하지 않음 |
| `403` | 해당 Device Key의 권한·소속 확인 |
| 그 외 `5xx` | 기존 설정 유지, 지수 백오프로 재시도 |

`ETag`도 `서버 → 임베디드`로 전달되며, 임베디드는 다음 요청에 `If-None-Match`로 다시 `임베디드 → 서버` 방향으로 전달합니다.

임베디드가 사용하는 필드는 `caseId`, `conditionId`, `prompt`, `exclusionPrompt`, `similarityThreshold`, `searchStart`, `searchEnd`, `searchArea`, `cameraId`, `cameraCode`입니다. 모든 시간은 UTC `Z` 형식입니다.

실시간 임베디드 응답의 `prompt`와 `exclusionPrompt`는 무료 번역 API를 호출하지 않고 서버의 고정 정규화 규칙으로 처리합니다. 인식하는 색상은 `black`, `blue`, `brown`, `green`, `gray`, `orange`, `pink`, `purple`, `red`, `white`, `yellow`이며, 상의 형태는 `short sleeve` 또는 `long sleeve`만 사용합니다.

임베디드에 전달되는 프롬프트의 정보 순서는 반드시 다음과 같습니다.

`성별 → 상의 색 → 상의 형태 → 하의 색`

상의 형태는 `short sleeve` 또는 `long sleeve` 중 하나만 사용합니다. 예를 들어 `남성, 검은색 반팔 상의와 검은색 청바지`는 `a man wearing a black short sleeve top and black pants`로 전달됩니다. 하의의 옷 종류는 순서 계약에 포함하지 않고 하의 색만 전달합니다.

녹화영상 분석 경로는 실시간 정규화기를 사용하지 않고 기존 번역기(`EmbeddedPromptTranslator`)를 계속 사용합니다.

## 5. 로컬 분석 처리

사건별·카메라별로 독립된 분석 작업을 유지합니다.

```text
검색 대상 스냅샷 반영
 → 카메라 스트림 수신
 → 사람 탐지·trackId 생성
 → prompt/exclusionPrompt 기반 similarity 계산
 → similarityThreshold 이상만 후보로 선별
 → 원본 프레임·crop 업로드 (임베디드 → 저장소/서버)
 → 후보 이벤트 API 등록 (임베디드 → 서버)
 → 성공 응답 수신 (서버 → 임베디드)
 → 로컬 결과 완료 처리
```

- `searchStart`/`searchEnd`가 있으면 해당 UTC 시간 범위 밖에서는 분석하지 않습니다.
- `cameras[].cameraCode`를 후보 이벤트의 `cameraCode`로 그대로 사용합니다.
- 같은 사건·카메라의 이벤트라도 서로 다른 프레임은 서로 다른 `eventId`를 사용합니다.
- 동일 이벤트를 재전송할 때는 최초 요청과 같은 `eventId`와 payload를 사용합니다.
- 후보 이벤트 API 성공 전에는 탐지를 전송 완료로 표시하지 않습니다.

## 6. 임베디드 → 서버: 후보 이벤트 등록 API

### 요청

전달 방향: `임베디드 → 서버`

```http
POST /api/v1/device/candidate-events
X-Device-Key: {deviceKey}
Content-Type: application/json
Accept: application/json
```

```json
{
  "caseId": 101,
  "cameraCode": "CAM-001",
  "eventId": "CAM-001-20260731-000001",
  "detectedAt": "2026-07-31T01:20:10.123Z",
  "frameObjectKey": "realtime/CAM-001/frame-000001.jpg",
  "detections": [
    {
      "trackId": "track-42",
      "similarity": 0.8421,
      "cropObjectKey": "realtime/CAM-001/crop-000001.jpg",
      "boundingBox": { "x": 120, "y": 80, "width": 210, "height": 430 }
    }
  ]
}
```

### 필수 규칙

- `frameObjectKey`와 모든 `cropObjectKey`는 `임베디드 → 저장소/서버` 방향으로 API 호출 전에 업로드가 완료되어야 합니다.
- `eventId`는 이벤트 중복 방지 키입니다. 같은 ID에 다른 payload를 보내면 충돌입니다.
- `detections`는 1개 이상이어야 합니다.
- `similarity`는 `0.0~1.0`입니다.
- bounding box의 `x`, `y`, `width`, `height`는 0 이상입니다.
- `detectedAt`은 RFC 3339 UTC 시각(`Z`)입니다.

### 응답 및 재시도

전달 방향: `서버 → 임베디드`

| HTTP 상태 | 의미 | 처리 |
|---:|---|---|
| `201` | 신규 저장 | 전송 완료 처리 |
| `200` | 동일 `eventId`의 동일 요청 | 중복 성공으로 처리 |
| `400` | payload·시각·좌표·object key 오류 | 수정 후 재전송 |
| `401` | Device Key 누락·오류 | 인증 설정 확인 |
| `403` | 카메라가 Device Key 소속이 아님 | 재시도하지 않음 |
| `404` | 사건 또는 카메라 없음 | 검색 대상 재동기화 |
| `409` | 같은 `eventId`에 다른 내용 | 새 `eventId` 발급 전 원인 확인 |
| `422` | 사건이 탐색 중이 아니거나 카메라 비활성 | 로컬 작업 중지 후 재동기화 |
| `429`, `5xx` | 일시적 서버·속도 제한 | 지수 백오프 후 동일 요청 재시도 |

권장 재시도 간격은 `1초 → 2초 → 4초 → 8초`이며, 최대 간격과 총 재시도 횟수는 장치 운영 설정으로 둡니다. 재시도 중에도 `eventId`는 변경하지 않습니다.

## 7. 임베디드 완료 체크리스트

- [ ] 시작·재연결 시 검색 대상 전체 동기화
- [ ] `ETag` 저장 및 `304` 처리
- [ ] `commandId` 중복 방지 및 ACK 시점 보장
- [ ] `SEARCH_TARGET_DISABLED` 수신 시 사건 작업 중지
- [ ] UTC 시각과 RFC 3339 형식 사용
- [ ] 업로드 완료 후 후보 이벤트 API 호출
- [ ] `eventId` 기반 멱등 재시도
- [ ] `401/403/404/409/422`를 일시 장애와 구분
- [ ] API 실패 시 기존 설정을 보존하고 재동기화
