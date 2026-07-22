# EyesOnU REST API 명세서

## 1. 문서 개요

이 문서는 실종 신고, 사건별 CCTV 탐색, AI 후보 검토 및 운영 이력 관리를 위한 REST API를 정의한다.

- API 버전: `v1`
- Base URL: `/api/v1`
- 데이터 형식: JSON (`application/json`)
- 파일 업로드: `multipart/form-data`
- JSON 필드명: `camelCase`
- 일시 형식: UTC 기준 RFC 3339 (`2026-07-20T01:30:00Z`)
- 위치 좌표: WGS84(SRID 4326), 위도 `latitude`, 경도 `longitude`
- 실시간 WebSocket/STOMP 메시지 명세는 이 문서의 범위에서 제외한다.

### 1.1 API 사용자

| 구분 | 인증 방식 | 주요 권한 |
| --- | --- | --- |
| 신고자·경찰서 접수자 | 인증 없음 | 실종 신고 접수, 사건조회번호와 전화번호를 이용한 진행 상황 조회 |
| 관리자 | Bearer JWT (`ADMIN`) | 사건, 탐색 조건, 카메라, 후보, 작업 및 감사 로그 관리 |
| 카메라·Jetson | `X-Device-Key` | Heartbeat, 녹화 메타데이터, AI 후보 이벤트 전송 |

> v1에서는 실종 신고와 신고자 진행 상황 조회에 별도 로그인이나 전화번호 인증을 요구하지 않는다.

---

## 2. 전체 API 목록

세부 요청·응답 예시와 업무 규칙은 뒤쪽의 상세 명세에서 확인한다. 아래 경로는 모두 Base URL `/api/v1`을 기준으로 한다.

### 2.1 인증·신고·진행 조회

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `POST` | `/auth/admin/login` | 관리자 로그인 | `loginId`, `password` | `200`, `401` |
| `GET` | `/admins/me` | 로그인 관리자 정보 조회 | 없음 | `200`, `401` |
| `PATCH` | `/admins/me` | 관리자 정보 수정 | `name`, 비밀번호 변경 정보 | `200`, `400`, `401` |
| `POST` | `/cases` | 인증 없는 실종 신고 접수 | 신고자·실종자·마지막 목격 정보, `photo` | `201`, `400`, `409`, `413`, `415` |
| `POST` | `/cases/status-inquiries` | 신고자 사건 진행 상황 조회 | `caseNumber`, `phone` | `200`, `400`, `404`, `429` |

### 2.2 관리자 사건·탐색·후보

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/cases` | 사건 목록 | `status`, `caseNumber`, `missingName`, 신고 기간, 페이지 조건 | `200`, `400` |
| `GET` | `/admin/cases/{caseId}` | 사건 상세 | `caseId` | `200`, `404` |
| `PATCH` | `/admin/cases/{caseId}` | 사건 정보 수정 | 신고 내용, 실종자·마지막 목격 정보 | `200`, `400`, `404`, `409` |
| `PATCH` | `/admin/cases/{caseId}/status` | 종료 외 사건 상태 변경 | `status`, `reason` | `200`, `400`, `404` |
| `POST` | `/admin/cases/{caseId}/close` | 사건 종료 | `reason`, `force` | `200`, `404`, `409` |
| `GET` | `/admin/cases/{caseId}/search-conditions` | 탐색 조건 목록 | `caseId` | `200`, `404` |
| `POST` | `/admin/cases/{caseId}/search-conditions` | 탐색 조건 생성 | 프롬프트, 시간, 구역, 임계값 | `201`, `400`, `404` |
| `GET` | `/admin/cases/{caseId}/search-conditions/{conditionId}` | 탐색 조건 상세 | `caseId`, `conditionId` | `200`, `404` |
| `PATCH` | `/admin/cases/{caseId}/search-conditions/{conditionId}` | 탐색 조건 수정 | 변경할 탐색 조건 | `200`, `400`, `404` |
| `DELETE` | `/admin/cases/{caseId}/search-conditions/{conditionId}` | 미사용 탐색 조건 삭제 | `caseId`, `conditionId` | `204`, `404`, `409` |
| `GET` | `/admin/cases/{caseId}/cameras` | 사건의 탐색 카메라 목록 | `caseId` | `200`, `404` |
| `POST` | `/admin/cases/{caseId}/cameras` | 탐색 카메라 추가·재활성화 | `cameraIds` | `200`, `400`, `404` |
| `DELETE` | `/admin/cases/{caseId}/cameras/{cameraId}` | 탐색 카메라 제외 | `caseId`, `cameraId` | `204`, `404` |
| `GET` | `/admin/cases/{caseId}/candidates` | 사건 후보 목록 | 판정 상태, 카메라, 탐지 기간, 최소 유사도, 페이지 조건 | `200`, `400`, `404` |
| `GET` | `/admin/candidates/{candidateId}` | 후보 상세 | `candidateId` | `200`, `404` |
| `PATCH` | `/admin/candidates/{candidateId}/review` | 후보 판정 | `reviewStatus`, `reviewComment`, `version` | `200`, `400`, `404`, `409` |
| `GET` | `/admin/cases/{caseId}/route` | 확정 후보 기반 동선 조회 | `from`, `to` | `200`, `400`, `404` |

### 2.3 카메라·녹화·장치

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/cameras` | 카메라 목록 | `status`, `search`, 페이지 조건 | `200`, `400` |
| `POST` | `/admin/cameras` | 카메라 등록 | 이름, Raspberry Pi ID, 좌표, 주소, RTSP URL | `201`, `400`, `409` |
| `GET` | `/admin/cameras/{cameraId}` | 카메라 상세 | `cameraId` | `200`, `404` |
| `PATCH` | `/admin/cameras/{cameraId}` | 카메라 정보 수정 | 이름, 좌표, 주소, RTSP URL | `200`, `400`, `404`, `409` |
| `POST` | `/device/cameras/{raspberryId}/heartbeat` | 카메라 Heartbeat·상태 갱신 | `occurredAt`, `status`, `detail` | `204`, `400`, `401`, `403`, `404` |
| `POST` | `/device/cameras/{raspberryId}/recordings` | 녹화 메타데이터 등록 | 촬영 시간, Object Key, 파일 크기, 업로드 상태 | `201`, `400`, `403`, `409` |
| `PATCH` | `/device/recordings/{recordingId}/upload-status` | 녹화 업로드 상태 갱신 | `uploadStatus`, `fileSize` | `200`, `400`, `403`, `404` |
| `GET` | `/admin/recordings` | 녹화 목록 | 카메라, 업로드 상태, 촬영 기간, 페이지 조건 | `200`, `400` |
| `GET` | `/admin/recordings/{recordingId}` | 녹화 상세 | `recordingId` | `200`, `404` |
| `POST` | `/device/candidate-events` | Jetson 후보 이벤트 등록 | 사건, 장치, 탐지 시각, 유사도, 이미지 | `201`, `200`, `400`, `401`, `403`, `404`, `422` |

### 2.4 분석 작업·감사 로그

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `POST` | `/admin/cases/{caseId}/analysis-jobs` | 녹화 영상 분석 작업 생성 | 작업 유형, 탐색 조건, 녹화 ID 목록 | `202`, `400`, `404`, `409` |
| `GET` | `/admin/cases/{caseId}/analysis-jobs` | 사건별 분석 작업 목록 | 상태, 작업 유형, 페이지 조건 | `200`, `404` |
| `GET` | `/admin/analysis-jobs/{jobId}` | 분석 작업 상세 | `jobId` | `200`, `404` |
| `POST` | `/admin/analysis-jobs/{jobId}/retry` | 실패 작업 재시도 | `jobId` | `202`, `404`, `409` |
| `GET` | `/admin/audit-logs` | 감사 로그 조회 | 사건, 관리자, 행위, 대상, 기간, 페이지 조건 | `200`, `400`, `401`, `403` |

---

## 3. 공통 규칙

### 3.1 요청 헤더

| 헤더 | 필수 여부 | 설명 |
| --- | --- | --- |
| `Authorization: Bearer {token}` | 조건부 | 관리자 API 호출 시 필수 |
| `X-Device-Key: {deviceKey}` | 조건부 | 카메라·Jetson API 호출 시 필수 |
| `Content-Type` | 필수 | `application/json` 또는 `multipart/form-data` |
| `Idempotency-Key` | 조건부 | 후보 이벤트 전송 시 필수인 클라이언트 생성 고유 키 |
| `X-Request-Id` | 선택 | 호출 추적용 ID. 없으면 서버에서 생성 |

### 3.2 성공 응답

단건 응답:

```json
{
  "timestamp": "2026-07-20T01:30:00Z",
  "data": {
    "id": 1
  }
}
```

목록 응답:

```json
{
  "timestamp": "2026-07-20T01:30:00Z",
  "data": [
    {
      "id": 1
    }
  ],
  "meta": {
    "page": 0,
    "size": 20,
    "totalElements": 42,
    "totalPages": 3,
    "sort": "createdAt,desc"
  }
}
```

생성 API는 `201 Created`와 생성된 리소스를 반환한다. 응답 본문이 필요 없는 삭제 API는 `204 No Content`를 반환한다.

### 3.3 오류 응답

```json
{
  "timestamp": "2026-07-20T01:30:00Z",
  "status": 400,
  "code": "VALIDATION_ERROR",
  "message": "요청 값이 올바르지 않습니다.",
  "fieldErrors": [
    {
      "field": "searchEnd",
      "reason": "searchStart보다 빠를 수 없습니다."
    }
  ],
  "traceId": "42a90b7d6bbf4f38"
}
```

| HTTP 상태 | 공통 오류 코드 | 사용 조건 |
| --- | --- | --- |
| `400 Bad Request` | `INVALID_REQUEST`, `VALIDATION_ERROR`, `INVALID_STATE_TRANSITION` | 형식 오류, 필드 검증 실패, 허용되지 않은 상태 전이 |
| `401 Unauthorized` | `AUTHENTICATION_REQUIRED`, `INVALID_TOKEN`, `INVALID_DEVICE_KEY` | 인증 정보 누락·만료·위조 |
| `403 Forbidden` | `ACCESS_DENIED` | 역할 또는 장치 권한 부족 |
| `404 Not Found` | `RESOURCE_NOT_FOUND`, `INQUIRY_NOT_FOUND` | 리소스 없음 또는 사건조회번호·전화번호 불일치 |
| `409 Conflict` | `DUPLICATE_RESOURCE`, `OPTIMISTIC_LOCK_CONFLICT`, `CASE_CLOSE_CONFLICT` | 중복 생성, 버전 충돌, 종료 조건 불충족 |
| `413 Payload Too Large` | `FILE_TOO_LARGE` | 허용 용량을 초과한 파일 |
| `415 Unsupported Media Type` | `UNSUPPORTED_MEDIA_TYPE` | 지원하지 않는 이미지·영상 형식 |
| `422 Unprocessable Entity` | `BUSINESS_RULE_VIOLATION` | 문법상 유효하지만 업무 규칙을 위반한 요청 |
| `429 Too Many Requests` | `RATE_LIMIT_EXCEEDED` | 로그인·사건 진행 조회 등 요청 허용 횟수 초과 |
| `500 Internal Server Error` | `INTERNAL_SERVER_ERROR` | 처리되지 않은 서버 오류 |
| `503 Service Unavailable` | `STORAGE_UNAVAILABLE`, `ANALYSIS_SERVICE_UNAVAILABLE` | 저장소 또는 분석 시스템 일시 장애 |

### 3.4 페이지네이션과 정렬

| 파라미터 | 기본값 | 제한 | 설명 |
| --- | --- | --- | --- |
| `page` | `0` | `0` 이상 | 0부터 시작하는 페이지 번호 |
| `size` | `20` | `1`~`100` | 페이지 크기 |
| `sort` | 리소스별 기본값 | 허용 필드만 사용 | `{field},{asc\|desc}` 형식. 여러 번 전달 가능 |

잘못된 정렬 필드는 `400 VALIDATION_ERROR`로 처리한다.

### 3.5 파일과 민감 정보

- `password`, `photoS3Key`, `imageS3Key`, `clipS3Key`, `s3Key`, `rtspUrl`, Device Key는 외부 응답에 노출하지 않는다.
- 사진·후보 이미지·클립은 만료 시간이 있는 `photoUrl`, `imageUrl`, `clipUrl`로 반환한다.
- URL 만료 시 리소스를 다시 조회해 새로운 URL을 발급받는다.
- 지원 이미지 형식은 JPEG·PNG·WebP, 지원 영상 형식은 MP4(H.264)를 기본으로 한다.
- 파일 크기 제한은 배포 환경 설정값을 따르며, 초과 시 `413 FILE_TOO_LARGE`를 반환한다.

### 3.6 주요 검증 규칙

- `phone`, `caseNumber`, `raspberryId`, `loginId`는 앞뒤 공백을 제거한 후 검증한다.
- 위도는 `-90`~`90`, 경도는 `-180`~`180` 범위여야 한다.
- `lastSeenLat`와 `lastSeenLng`는 함께 제공하거나 모두 생략한다.
- `similarity`, `similarityThreshold`는 `0.0000`~`1.0000` 범위여야 한다.
- 탐색 종료 시각은 탐색 시작 시각보다 빠를 수 없다.
- 클라이언트는 S3 Key, 생성·수정 시각, 검토 관리자 ID를 직접 지정할 수 없다.

---

## 4. 상태값과 전이 규칙

### 4.1 사건 상태 `CaseStatus`

| 상태 | 설명 | 허용되는 다음 상태 |
| --- | --- | --- |
| `RECEIVED` | 신고 접수 | `SEARCHING`, `CLOSED` |
| `SEARCHING` | 녹화·실시간 영상 탐색 중 | `CANDIDATE_FOUND`, `CLOSED` |
| `CANDIDATE_FOUND` | 검토할 후보 존재 | `SEARCHING`, `FIELD_SEARCH`, `CLOSED` |
| `FIELD_SEARCH` | 확인 후보를 기반으로 현장 수색 중 | `SEARCHING`, `CLOSED` |
| `CLOSED` | 사건 종료 | 없음 |

- `CLOSED` 전이는 사건 종료 API를 통해서만 수행한다.
- 사건 종료 시 미처리 후보 또는 실행 중인 분석 작업이 있으면 `409 CASE_CLOSE_CONFLICT`를 반환한다.
- 종료된 사건은 수정·탐색·후보 등록이 불가능하며 다시 열기 API는 v1에서 제공하지 않는다.

### 4.2 기타 상태값

| 구분 | 값 |
| --- | --- |
| `CameraStatus` | `ONLINE`, `OFFLINE`, `ERROR` |
| `UploadStatus` | `PENDING`, `UPLOADING`, `COMPLETED`, `FAILED` |
| `ReviewStatus` | `PENDING`, `KEPT`, `CONFIRMED`, `REJECTED` |
| `ClipStatus` | `PENDING`, `PROCESSING`, `READY`, `FAILED` |
| `AnalysisJobType` | `RECORDING_ANALYSIS`, `CLIP_GENERATION` |
| `AnalysisJobStatus` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` |

### 4.3 기타 상태 전이

| 구분 | 전이 규칙 |
| --- | --- |
| 카메라 | 정상 Heartbeat 수신 시 `ONLINE`, 기준 시간 동안 미수신 시 `OFFLINE`, 장치 오류 보고 시 `ERROR` |
| 녹화 업로드 | `PENDING → UPLOADING → COMPLETED` 또는 `FAILED`, 재업로드 시 `FAILED → UPLOADING` |
| 후보 판정 | 최초 `PENDING`; 관리자는 `KEPT`, `CONFIRMED`, `REJECTED` 사이에서 재판정할 수 있으며 모든 변경을 감사 로그에 남김 |
| 클립 | `PENDING → PROCESSING → READY` 또는 `FAILED`, 재시도 시 `FAILED → PROCESSING` |
| 분석 작업 | `QUEUED → RUNNING → SUCCEEDED` 또는 `FAILED`; 재시도 시 `FAILED → QUEUED`이며 `retryCount` 증가 |

---

## 5. 인증·신고·진행 조회 API

### 5.1 관리자 로그인

`POST /api/v1/auth/admin/login`

요청:

```json
{
  "loginId": "control01",
  "password": "********"
}
```

응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T01:30:00Z",
  "data": {
    "accessToken": "eyJhbGciOi...",
    "tokenType": "Bearer",
    "expiresAt": "2026-07-20T03:30:00Z",
    "admin": {
      "id": 1,
      "loginId": "control01",
      "name": "관제 관리자"
    }
  }
}
```

### 5.2 실종 신고 접수

`POST /api/v1/cases`

- 신고 접수는 경찰서에서 진행하는 것으로 가정한다.
- 인증: 없음
- Content-Type: `multipart/form-data`
- `request`: 아래 JSON 구조
- `photo`: 선택 이미지 파일

`request` 파트:

```json
{
  "reporter": {
    "name": "홍길동",
    "phone": "01012345678",
    "email": "reporter@example.com"
  },
  "reportContent": "마지막 연락 이후 귀가하지 않았습니다.",
  "missingName": "김민수",
  "gender": "MALE",
  "ageGroup": "TWENTIES",
  "appearance": "검은색 셔츠와 청바지, 흰색 운동화",
  "belongings": "검은색 백팩",
  "lastSeenTime": "2026-07-20T00:10:00Z",
  "lastSeenLat": 37.5012345,
  "lastSeenLng": 127.0398765,
  "lastSeenAddress": "서울특별시 강남구"
}
```

필수 필드: `reporter.name`, `reporter.phone`, `reportContent`, `missingName`, `appearance`, `lastSeenTime`

응답 `201 Created`:

```json
{
  "timestamp": "2026-07-20T01:30:00Z",
  "data": {
    "id": 101,
    "caseNumber": "EFU-20260720-000101",
    "status": "RECEIVED",
    "reportedAt": "2026-07-20T01:30:00Z"
  }
}
```

서버 처리:

1. `REPORTERS`를 신고 접수 정보로 생성하고 `phoneVerified=false`, `verifiedAt=null`로 저장한다.
2. 사진을 저장한 후 내부 S3 Key를 포함하여 `CASES`를 생성한다.
3. 사건번호를 중복되지 않게 발급하고 생성 이력을 `AUDIT_LOGS`에 기록한다.

> `REPORTERS.phoneVerified`와 `verifiedAt`은 향후 인증 기능 확장을 위해 유지하며 v1 신고 흐름에서는 사용하지 않는다.

### 5.3 신고자 사건 진행 조회

`POST /api/v1/cases/status-inquiries`

- 인증: 없음
- Content-Type: `application/json`
- 동일 IP 또는 전화번호의 반복 조회는 Rate Limit을 적용한다.

요청:

```json
{
  "caseNumber": "EFU-20260720-000101",
  "phone": "01012345678"
}
```

응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T02:20:00Z",
  "data": {
    "caseNumber": "EFU-20260720-000101",
    "status": "SEARCHING",
    "missingName": "김민수",
    "photoUrl": "https://media.example.com/signed/...",
    "lastSeenTime": "2026-07-20T00:10:00Z",
    "lastSeenAddress": "서울특별시 강남구",
    "reportedAt": "2026-07-20T01:30:00Z",
    "closedAt": null,
    "confirmedSightings": []
  }
}
```

공개 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `caseNumber` | string | 사건 조회번호 |
| `status` | CaseStatus | 현재 진행 상태 |
| `missingName` | string | 실종자 이름 |
| `photoUrl` | string, nullable | 실종자 사진 임시 URL |
| `lastSeenTime` | datetime | 마지막 목격 시각 |
| `lastSeenAddress` | string, nullable | 마지막 목격 주소 |
| `reportedAt` | datetime | 신고 접수 시각 |
| `closedAt` | datetime, nullable | 사건 종료 시각 |
| `confirmedSightings` | array | 관리자가 `CONFIRMED`로 판정한 공개 가능 목격 정보 |

- 사건조회번호와 전화번호가 모두 동일한 사건에 연결될 때만 정보를 반환한다.
- 둘 중 하나라도 일치하지 않으면 어떤 값이 틀렸는지 구분하지 않고 `404 INQUIRY_NOT_FOUND`를 반환한다.

미확정 후보, 유사도, 원본 CCTV 영상, `cameraId`, 내부 관리자 정보와 감사 로그는 노출하지 않는다.

---

## 6. 관리자 사건 API

이 절의 모든 엔드포인트는 별도 표기가 없으면 ADMIN Bearer JWT가 필요하다.

### 6.1 사건 관리

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/cases` | 사건 목록 | `status`, `caseNumber`, `missingName`, `reportedFrom`, `reportedTo`, 페이지 조건 | `200`, `400` |
| `GET` | `/admin/cases/{caseId}` | 사건 상세 | Path: `caseId` | `200`, `404` |
| `PATCH` | `/admin/cases/{caseId}` | 사건 정보 수정 | 신고 내용, 실종자 정보, 마지막 목격 정보 | `200`, `400`, `404`, `409` |
| `PATCH` | `/admin/cases/{caseId}/status` | 종료를 제외한 상태 변경 | `status`, `reason` | `200`, `400`, `404` |
| `POST` | `/admin/cases/{caseId}/close` | 사건 종료 | `reason`, `force` | `200`, `404`, `409` |

목록 기본 정렬은 `reportedAt,desc`이다.

사건 상세 응답 예시:

```json
{
  "timestamp": "2026-07-20T01:40:00Z",
  "data": {
    "id": 101,
    "caseNumber": "EFU-20260720-000101",
    "status": "SEARCHING",
    "reporter": {
      "id": 20,
      "name": "홍길동",
      "phone": "01012345678",
      "email": "reporter@example.com",
      "phoneVerified": false,
      "verifiedAt": null
    },
    "reportContent": "마지막 연락 이후 귀가하지 않았습니다.",
    "missingName": "김민수",
    "gender": "MALE",
    "ageGroup": "TWENTIES",
    "appearance": "검은색 셔츠와 청바지, 흰색 운동화",
    "belongings": "검은색 백팩",
    "photoUrl": "https://media.example.com/signed/...",
    "lastSeenTime": "2026-07-20T00:10:00Z",
    "lastSeenLat": 37.5012345,
    "lastSeenLng": 127.0398765,
    "lastSeenAddress": "서울특별시 강남구",
    "reportedAt": "2026-07-20T01:30:00Z",
    "closedAt": null,
    "createdAt": "2026-07-20T01:30:00Z",
    "updatedAt": "2026-07-20T01:35:00Z"
  }
}
```

사건 종료:

- `force` 기본값은 `false`이다.
- 미처리 후보 또는 실행 중인 작업이 있으면 `force=false` 요청은 `409 CASE_CLOSE_CONFLICT`를 반환한다.
- `force=true`는 관리자 확인 후 미완료 작업을 취소하고 종료하며, 사유와 강제 종료 여부를 감사 로그에 남긴다.

### 6.2 탐색 조건

| 메서드 | 경로 | 설명 | 주요 응답 |
| --- | --- | --- | --- |
| `GET` | `/admin/cases/{caseId}/search-conditions` | 사건의 탐색 조건 목록 | `200`, `404` |
| `POST` | `/admin/cases/{caseId}/search-conditions` | 탐색 조건 생성 | `201`, `400`, `404` |
| `GET` | `/admin/cases/{caseId}/search-conditions/{conditionId}` | 탐색 조건 상세 | `200`, `404` |
| `PATCH` | `/admin/cases/{caseId}/search-conditions/{conditionId}` | 탐색 조건 수정 | `200`, `400`, `404` |
| `DELETE` | `/admin/cases/{caseId}/search-conditions/{conditionId}` | 미사용 탐색 조건 삭제 | `204`, `404`, `409` |

생성 요청:

```json
{
  "prompt": "검은색 셔츠와 청바지를 입고 흰색 운동화를 신은 20대 남성",
  "exclusionPrompt": "모자 또는 붉은색 상의",
  "searchStart": "2026-07-20T00:00:00Z",
  "searchEnd": "2026-07-20T01:30:00Z",
  "searchArea": "Zone A, Zone B",
  "similarityThreshold": 0.7200
}
```

필수 필드: `prompt`, `similarityThreshold`

추가 규칙:

- `searchStart`와 `searchEnd`는 함께 지정하는 것을 기본으로 하며, 한쪽만 제공하면 `400 VALIDATION_ERROR`이다.
- 실행 중인 분석 작업이 참조하는 조건은 삭제할 수 없으며 `409`를 반환한다.
- 생성·수정 시 변경 전후 값을 `AUDIT_LOGS`에 기록한다.

### 6.3 사건별 탐색 카메라

| 메서드 | 경로 | 설명 | 주요 응답 |
| --- | --- | --- | --- |
| `GET` | `/admin/cases/{caseId}/cameras` | 사건에 지정된 카메라 목록 | `200`, `404` |
| `POST` | `/admin/cases/{caseId}/cameras` | 탐색 카메라 추가 또는 재활성화 | `200`, `400`, `404` |
| `DELETE` | `/admin/cases/{caseId}/cameras/{cameraId}` | 탐색 카메라 제외 | `204`, `404` |

카메라 추가 요청:

```json
{
  "cameraIds": [1, 2]
}
```

- 추가 시 `searchEnabled=true`, `selectedAt=현재 시각`, `removedAt=null`로 처리한다.
- 제외 시 연결 데이터를 물리 삭제하지 않고 `searchEnabled=false`, `removedAt=현재 시각`으로 변경한다.
- 동일 사건·카메라 조합은 하나만 유지한다.

### 6.4 후보 조회 및 판정

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/cases/{caseId}/candidates` | 사건 후보 목록 | `reviewStatus`, `cameraId`, `detectedFrom`, `detectedTo`, `minSimilarity`, 페이지 조건 | `200`, `400`, `404` |
| `GET` | `/admin/candidates/{candidateId}` | 후보 상세 | Path: `candidateId` | `200`, `404` |
| `PATCH` | `/admin/candidates/{candidateId}/review` | 후보 판정 | `reviewStatus`, `reviewComment`, `version` | `200`, `400`, `404`, `409` |

목록 기본 정렬은 `detectedTime,desc`이다.

후보 판정 요청:

```json
{
  "reviewStatus": "CONFIRMED",
  "reviewComment": "신고 사진의 의상과 소지품이 일치함",
  "version": 3
}
```

응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T02:10:00Z",
  "data": {
    "id": 9001,
    "caseId": 101,
    "camera": {
      "id": 2,
      "cameraName": "Zone B 출입구",
      "latitude": 37.5020000,
      "longitude": 127.0410000,
      "address": "서울특별시 강남구"
    },
    "detectedTime": "2026-07-20T02:00:12Z",
    "similarity": 0.8421,
    "imageUrl": "https://media.example.com/signed/...",
    "clipUrl": "https://media.example.com/signed/...",
    "clipStatus": "READY",
    "reviewStatus": "CONFIRMED",
    "reviewComment": "신고 사진의 의상과 소지품이 일치함",
    "reviewedBy": {
      "id": 1,
      "name": "관제 관리자"
    },
    "reviewedAt": "2026-07-20T02:10:00Z",
    "version": 4
  }
}
```

- 요청 `version`이 DB의 현재 버전과 다르면 `409 OPTIMISTIC_LOCK_CONFLICT`와 최신 후보 정보를 반환한다.
- `CONFIRMED` 판정은 사건 상태를 자동 종료하지 않는다.
- 판정 및 재판정은 관리자, 판정 시각, 의견과 변경 전후 상태를 감사 로그에 남긴다.

### 6.5 확정 동선 조회

`GET /api/v1/admin/cases/{caseId}/route`

인증: ADMIN

주요 응답: `200`, `400`, `404`

| 쿼리 파라미터 | 필수 | 설명 |
| --- | --- | --- |
| `from` | 아니요 | 조회 시작 시각 |
| `to` | 아니요 | 조회 종료 시각 |

응답은 `reviewStatus=CONFIRMED`인 후보만 `detectedTime,asc` 순서로 반환한다.

```json
{
  "timestamp": "2026-07-20T02:20:00Z",
  "data": {
    "caseId": 101,
    "latestSighting": {
      "candidateId": 9001,
      "detectedTime": "2026-07-20T02:00:12Z",
      "latitude": 37.5020000,
      "longitude": 127.0410000
    },
    "sightings": [
      {
        "candidateId": 8990,
        "detectedTime": "2026-07-20T01:45:10Z",
        "cameraName": "Zone A 복도",
        "latitude": 37.5015000,
        "longitude": 127.0402000,
        "imageUrl": "https://media.example.com/signed/..."
      },
      {
        "candidateId": 9001,
        "detectedTime": "2026-07-20T02:00:12Z",
        "cameraName": "Zone B 출입구",
        "latitude": 37.5020000,
        "longitude": 127.0410000,
        "imageUrl": "https://media.example.com/signed/..."
      }
    ]
  }
}
```

---

## 7. 카메라 및 녹화 API

### 7.1 관리자 카메라 API

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/cameras` | 카메라 목록 | `status`, `search`, 페이지 조건 | `200`, `400` |
| `POST` | `/admin/cameras` | 카메라 등록 | 카메라·라즈베리파이 정보 | `201`, `400`, `409` |
| `GET` | `/admin/cameras/{cameraId}` | 카메라 상세 | Path: `cameraId` | `200`, `404` |
| `PATCH` | `/admin/cameras/{cameraId}` | 카메라 정보 수정 | 이름, 좌표, 주소, RTSP URL | `200`, `400`, `404`, `409` |

카메라 등록 요청:

```json
{
  "cameraName": "Zone A 복도",
  "raspberryId": "RPI-ZONE-A-01",
  "latitude": 37.5015000,
  "longitude": 127.0402000,
  "address": "서울특별시 강남구",
  "rtspUrl": "rtsp://camera.internal/live"
}
```

- `raspberryId`는 중복될 수 없다.
- `rtspUrl`은 생성·수정 요청에서만 받고 조회 응답에는 포함하지 않는다.
- 최초 상태는 `OFFLINE`이다.

### 7.2 장치 Heartbeat

`POST /api/v1/device/cameras/{raspberryId}/heartbeat`

인증: `X-Device-Key`
주요 응답: `204`, `400`, `401`, `403`, `404`

```json
{
  "occurredAt": "2026-07-20T02:00:00Z",
  "status": "ONLINE",
  "detail": null
}
```

- Device Key에 연결된 장치와 `raspberryId`가 다르면 `403 ACCESS_DENIED`이다.
- 정상 처리 시 카메라의 `lastHeartbeat`, `status`, `updatedAt`을 갱신한다.
- `204 No Content`를 반환한다.

### 7.3 녹화 메타데이터 등록

| 메서드 | 경로 | 인증 | 설명 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `POST` | `/device/cameras/{raspberryId}/recordings` | Device Key | 녹화 파일 메타데이터 등록 | `201`, `400`, `403`, `409` |
| `PATCH` | `/device/recordings/{recordingId}/upload-status` | Device Key | 업로드 상태·파일 정보 갱신 | `200`, `400`, `403`, `404` |
| `GET` | `/admin/recordings` | ADMIN | 녹화 목록 조회 | `200`, `400` |
| `GET` | `/admin/recordings/{recordingId}` | ADMIN | 녹화 상세 조회 | `200`, `404` |

등록 요청:

```json
{
  "startTime": "2026-07-20T01:50:00Z",
  "endTime": "2026-07-20T02:00:00Z",
  "objectKey": "recordings/RPI-ZONE-A-01/2026/07/20/015000.mp4",
  "fileSize": 104857600,
  "uploadStatus": "PENDING"
}
```

> `objectKey`는 장치 요청 필드이며 서버가 검증 후 내부 `s3Key`로 저장한다. 관리자 응답에는 `objectKey` 또는 `s3Key` 대신 필요 시 `videoUrl`을 반환한다.

업로드 상태 변경:

```json
{
  "uploadStatus": "COMPLETED",
  "fileSize": 104857600
}
```

관리자 목록 필터: `cameraId`, `uploadStatus`, `startFrom`, `startTo`, 페이지 조건. 기본 정렬은 `startTime,desc`이다.

---

## 8. AI 후보 이벤트 API

### 8.1 후보 이벤트 등록

`POST /api/v1/device/candidate-events`

- 인증: `X-Device-Key`
- 주요 응답: `201`, `200`(중복 재전송), `400`, `401`, `403`, `404`, `413`, `415`, `422`
- Content-Type: `multipart/form-data`
- 헤더 `Idempotency-Key`: 장치가 이벤트별로 생성한 고유 문자열
- `metadata`: 아래 JSON 구조
- `image`: 필수 후보 크롭 이미지

`metadata` 파트:

```json
{
  "caseId": 101,
  "raspberryId": "RPI-ZONE-B-01",
  "detectedTime": "2026-07-20T02:00:12Z",
  "similarity": 0.8421
}
```

필수 필드: `caseId`, `raspberryId`, `detectedTime`, `similarity`, `image`

신규 등록 응답 `201 Created`:

```json
{
  "timestamp": "2026-07-20T02:00:13Z",
  "data": {
    "candidateId": 9001,
    "caseId": 101,
    "cameraId": 2,
    "clipStatus": "PENDING",
    "reviewStatus": "PENDING",
    "duplicate": false,
    "createdAt": "2026-07-20T02:00:13Z"
  }
}
```

동일 `Idempotency-Key` 재전송 응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T02:00:14Z",
  "data": {
    "candidateId": 9001,
    "caseId": 101,
    "cameraId": 2,
    "clipStatus": "PENDING",
    "reviewStatus": "PENDING",
    "duplicate": true,
    "createdAt": "2026-07-20T02:00:13Z"
  }
}
```

검증 순서:

1. Device Key와 `raspberryId`의 연결 관계를 검증한다.
2. 사건과 카메라가 존재하고 사건이 종료되지 않았는지 검증한다.
3. 카메라가 해당 사건의 활성 탐색 대상으로 지정됐는지 확인한다.
4. `Idempotency-Key` 중복 여부를 확인한다.
5. 이미지와 유사도 범위를 검증하고 이미지를 저장한다.
6. `CANDIDATES`를 생성하고 필요한 클립 생성 작업을 `ANALYSIS_JOBS`에 등록한다.

오류:

| 조건 | 응답 |
| --- | --- |
| 미등록 Device Key | `401 INVALID_DEVICE_KEY` |
| 다른 장치의 `raspberryId` 사용 | `403 ACCESS_DENIED` |
| 존재하지 않는 사건·카메라 | `404 RESOURCE_NOT_FOUND` |
| 종료된 사건 또는 비활성 탐색 카메라 | `422 BUSINESS_RULE_VIOLATION` |
| 유사도 범위 오류·필수 필드 누락 | `400 VALIDATION_ERROR` |

> `Idempotency-Key`는 중복 요청 제어용 일시 데이터이며 ERD 엔터티의 영속 필드에는 포함하지 않는다.

---

## 9. 분석 작업 API

| 메서드 | 경로 | 인증 | 설명 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `POST` | `/admin/cases/{caseId}/analysis-jobs` | ADMIN | 녹화 영상 분석 작업 생성 | `202`, `400`, `404`, `409` |
| `GET` | `/admin/cases/{caseId}/analysis-jobs` | ADMIN | 사건별 분석 작업 목록 | `200`, `404` |
| `GET` | `/admin/analysis-jobs/{jobId}` | ADMIN | 작업 상세 조회 | `200`, `404` |
| `POST` | `/admin/analysis-jobs/{jobId}/retry` | ADMIN | 실패 작업 재시도 | `202`, `404`, `409` |

작업 생성 요청:

```json
{
  "jobType": "RECORDING_ANALYSIS",
  "searchConditionId": 301,
  "recordingIds": [501, 502]
}
```

- `recordingIds`를 생략하면 사건의 활성 카메라와 탐색 시간 범위에 포함되며 업로드가 완료된 녹화본을 서버가 선정한다.
- 선택된 각 녹화본마다 `ANALYSIS_JOBS`를 생성하며, 응답에는 생성된 작업 ID 배열을 반환한다.
- 사건이 `CLOSED`이면 작업을 생성할 수 없다.
- `retry`는 `FAILED` 상태에서만 허용하며, `retryCount`를 증가시키고 오류 메시지를 유지한 채 `QUEUED`로 전환한다.

작업 응답 주요 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | long | 작업 ID |
| `caseId` | long | 사건 ID |
| `recordingId` | long, nullable | 녹화본 분석 시 대상 ID |
| `candidateId` | long, nullable | 클립 생성 시 후보 ID |
| `jobType` | AnalysisJobType | 작업 종류 |
| `status` | AnalysisJobStatus | 작업 상태 |
| `retryCount` | integer | 재시도 횟수 |
| `errorMessage` | string, nullable | 최근 실패 원인 |
| `requestedAt` | datetime | 요청 시각 |
| `startedAt` | datetime, nullable | 시작 시각 |
| `completedAt` | datetime, nullable | 완료 시각 |

---

## 10. 감사 로그 API

`GET /api/v1/admin/audit-logs`

인증: ADMIN
주요 응답: `200`, `400`, `401`, `403`

| 쿼리 파라미터 | 필수 | 설명 |
| --- | --- | --- |
| `caseId` | 아니요 | 사건 ID |
| `adminId` | 아니요 | 수행 관리자 ID |
| `actionType` | 아니요 | 작업 유형 |
| `targetType` | 아니요 | 대상 엔터티 유형 |
| `targetId` | 아니요 | 대상 ID |
| `createdFrom` | 아니요 | 조회 시작 시각 |
| `createdTo` | 아니요 | 조회 종료 시각 |
| `page`, `size`, `sort` | 아니요 | 페이지·정렬 조건 |

기본 정렬은 `createdAt,desc`이다.

응답 주요 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | long | 감사 로그 ID |
| `admin` | object, nullable | 수행 관리자의 ID와 이름 |
| `caseId` | long, nullable | 관련 사건 ID |
| `actionType` | string | 작업 유형 |
| `targetType` | string, nullable | 작업 대상 유형 |
| `targetId` | long, nullable | 작업 대상 ID |
| `beforeValue` | object/string, nullable | 변경 전 값 |
| `afterValue` | object/string, nullable | 변경 후 값 |
| `detail` | string, nullable | 상세 설명 |
| `createdAt` | datetime | 수행 시각 |

- 비밀번호, 토큰, Device Key, 전체 RTSP URL 등 비밀정보는 변경 전후 값에 기록하지 않는다.
- 개인정보 조회 이력도 남기되 응답 권한과 보존 정책은 별도 운영 정책을 따른다.
- 감사 로그는 이 API로 수정·삭제할 수 없다.

---

## 11. 엔터티와 API 매핑

| ERD 엔터티 | 관련 API·처리 | 주요 관계 |
| --- | --- | --- |
| `ADMINS` | 관리자 로그인, `/admins/me`, 후보 판정, 감사 로그 | `CANDIDATES.reviewed_by`, `AUDIT_LOGS.admin_id` |
| `REPORTERS` | 신고 접수, 사건조회번호·전화번호 기반 진행 조회 | `REPORTERS 1:N CASES` |
| `CASES` | 신고 접수, 관리자 사건 관리, 신고자 진행 조회 | 탐색 조건·후보·작업·로그의 기준 사건 |
| `SEARCH_CONDITIONS` | `/admin/cases/{caseId}/search-conditions` | `CASES 1:N SEARCH_CONDITIONS` |
| `CAMERAS` | 관리자 카메라 관리, Heartbeat, 후보 이벤트 | 녹화·후보의 촬영 카메라 |
| `CASE_CAMERAS` | 사건별 카메라 지정·제외 | `CASES N:M CAMERAS` 연결 및 활성 여부 |
| `RECORDINGS` | 장치 녹화 메타데이터 등록, 관리자 녹화 조회 | `CAMERAS 1:N RECORDINGS` |
| `CANDIDATES` | 후보 이벤트 등록, 관리자 후보 조회·판정, 동선 | 사건·카메라·검토 관리자 참조 |
| `ANALYSIS_JOBS` | 분석 작업 생성·조회·재시도, 클립 생성 내부 처리 | 사건 및 녹화본 또는 후보 참조 |
| `AUDIT_LOGS` | 감사 로그 조회, 모든 주요 변경의 내부 기록 | 관리자·사건과 선택적 연결 |

---

## 12. 대표 오류 시나리오

| 시나리오 | 처리 |
| --- | --- |
| 탐색 종료가 시작보다 빠름 | `400 VALIDATION_ERROR` |
| 탐색 카메라 없이 분석 작업 요청 | `422 BUSINESS_RULE_VIOLATION` |
| 미등록 Device Key로 Heartbeat 또는 후보 전송 | `401 INVALID_DEVICE_KEY` |
| Device Key와 다른 `raspberryId` 사용 | `403 ACCESS_DENIED` |
| 동일 후보 이벤트 재전송 | 최초 생성 결과를 `200`과 `duplicate=true`로 반환 |
| 후보 판정 `version` 불일치 | `409 OPTIMISTIC_LOCK_CONFLICT`와 최신 후보 정보 반환 |
| 존재하지 않는 사건·카메라·후보 요청 | `404 RESOURCE_NOT_FOUND` |
| 실행 중인 작업 또는 미처리 후보가 있는 사건 종료 | `409 CASE_CLOSE_CONFLICT` |
| 종료 사건에 후보·탐색 작업 추가 | `422 BUSINESS_RULE_VIOLATION` |
| 사건조회번호와 전화번호 조합 불일치 | 상세 불일치 원인을 숨기고 `404 INQUIRY_NOT_FOUND` 반환 |
| 동일 전화번호 또는 IP의 과도한 진행 조회 | `429 RATE_LIMIT_EXCEEDED` |

---

## 13. 구현 참고사항

- 서버 저장 일시는 모두 UTC를 사용하고 화면에서 KST 등 사용자 시간대로 변환한다.
- 관리자 JWT의 비밀번호 검증은 단방향 해시를 사용하며 평문 비밀번호를 저장하거나 로그에 남기지 않는다.
- 후보 판정은 `CANDIDATES.version`을 이용한 낙관적 락으로 동시 수정을 방지한다.
- 후보 이미지·클립·녹화본 저장 실패 시 DB와 객체 저장소 사이의 보상 처리를 수행한다.
- 장치 Heartbeat의 `OFFLINE` 판정 시간, 관리자 JWT 만료 시간, 임시 미디어 URL 만료 시간, 조회 Rate Limit과 파일 용량은 환경 설정으로 관리한다.
- REST 조회 API는 WebSocket 연결이 끊긴 동안 발생한 후보와 상태 변경을 복구 조회하는 기준 데이터로 사용한다.
