# EyesOnU REST API 명세서

## 1. 문서 개요

이 문서는 실종 신고, 사건별 CCTV 탐색, AI 후보 검토 및 운영 이력 관리를 위한 REST API를 정의한다.

- API 버전: `v1`
- Base URL: `/api/v1`
- 데이터 형식: JSON (`application/json`)
- 파일 업로드: `multipart/form-data`
- JSON 필드명: `camelCase`
- 일시 형식: 요청은 UTC offset이 포함된 RFC 3339, 저장·응답은 UTC `Z` (`2026-07-20T01:30:00Z`)
- 위치 좌표: WGS84(SRID 4326), 위도 `latitude`, 경도 `longitude`
- 실시간 WebSocket/STOMP 메시지 명세는 이 문서의 범위에서 제외한다.

### 1.1 API 사용자

| 구분 | 인증 방식 | 주요 권한 |
| --- | --- | --- |
| 신고자 | 인증 없음 | 관리자가 전달한 사건조회번호와 신고 전화번호를 이용한 진행 상황 조회 |
| 관리자 | `EYESONU_SESSION` 세션 쿠키 (`ADMIN`) | 사건, 탐색 조건, 미디어 서버, 카메라, 후보, 작업 및 감사 로그 관리 |
| 미디어 서버 | `X-Device-Key: {deviceKey}` (`ROLE_MEDIA_SERVER`) | Heartbeat, 녹화 메타데이터와 Jetson 후보 이벤트 전송 |

> v1 사건 등록은 ADMIN 세션을 가진 관리자만 수행한다. 신고자 진행 상황 조회에는 별도 로그인이나 전화번호 인증을 요구하지 않는다.
> 신고자 정보는 회원 계정이 아니라 신고 당시 입력값을 보존하는 사건별 스냅샷으로 취급한다.

---

## 2. 전체 API 목록

세부 요청·응답 예시와 업무 규칙은 뒤쪽의 상세 명세에서 확인한다. 아래 경로는 모두 Base URL `/api/v1`을 기준으로 한다.

### 2.1 인증·진행 조회

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `GET` | `/auth/csrf` | CSRF 토큰 발급 | 없음 | `204` |
| `POST` | `/auth/admin/login` | 관리자 로그인 | `loginId`, `password`, CSRF | `200`, `400`, `401`, `403`, `429`, `503` |
| `POST` | `/auth/admin/logout` | 관리자 로그아웃 | CSRF | `204`, `403` |
| `GET` | `/admins/me` | 로그인 관리자 정보 조회 | 세션 | `200`, `401` |
| `PATCH` | `/admins/me` | 관리자 정보 수정 | 세션, CSRF, `name`, 비밀번호 변경 정보 | `200`, `400`, `401`, `403`, `503` |
| `POST` | `/cases/status-inquiries` | 신고자 사건 진행 상황 조회 | `caseNumber`, `phone` | `200`, `400`, `404`, `429`, `503` |

### 2.2 관리자 사건·탐색·후보

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `POST` | `/admin/cases` | 관리자 사건 등록 | 신고자·실종자·구조화 인상착의·마지막 목격 정보 | `201`, `400`, `401`, `403`, `503` |
| `GET` | `/admin/cases` | 사건 목록 | `status`, `caseNumber`, `missingName`, 신고 기간, 페이지 조건 | `200`, `400` |
| `GET` | `/admin/cases/{caseId}` | 사건 상세 | `caseId` | `200`, `404` |
| `PATCH` | `/admin/cases/{caseId}` | 사건 정보 수정 | 신고자, 실종자·구조화 인상착의·마지막 목격 정보 | `200`, `400`, `404`, `422` |
| `PUT` | `/admin/cases/{caseId}/photo` | 실종자 사진 등록·교체 | multipart `photo` | `200`, `400`, `404`, `413`, `415`, `422`, `503` |
| `DELETE` | `/admin/cases/{caseId}/photo` | 실종자 사진 제거 | `caseId` | `204`, `404`, `503` |
| `PATCH` | `/admin/cases/{caseId}/status` | 종료 외 사건 상태 변경 | `status`, `reason` | `200`, `400`, `404`, `422` |
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

### 2.3 미디어 서버·카메라·녹화·장치

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/media-servers` | 미디어 서버 목록 | `status`, `search`, 페이지 조건 | `200`, `400` |
| `POST` | `/admin/media-servers` | 미디어 서버 등록·Device Key 최초 발급 | `serverCode`, `name` | `201`, `400`, `409` |
| `GET` | `/admin/media-servers/{mediaServerId}` | 미디어 서버 상세 | `mediaServerId` | `200`, `404` |
| `PATCH` | `/admin/media-servers/{mediaServerId}` | 미디어 서버 정보·상태 수정 | `name`, `status` | `200`, `400`, `404`, `409` |
| `POST` | `/admin/media-servers/{mediaServerId}/device-key/rotate` | Device Key 즉시 교체 | `mediaServerId` | `200`, `404`, `409` |
| `GET` | `/admin/cameras` | 카메라 목록 | `status`, `search`, 페이지 조건 | `200`, `400` |
| `POST` | `/admin/cameras` | 카메라 등록 | 미디어 서버, 이름, 카메라 코드, 좌표, 주소, RTSP URL | `201`, `400`, `404`, `409` |
| `GET` | `/admin/cameras/{cameraId}` | 카메라 상세 | `cameraId` | `200`, `404` |
| `PATCH` | `/admin/cameras/{cameraId}` | 카메라 정보·소속 수정 | 미디어 서버, 이름, 좌표, 주소, RTSP URL | `200`, `400`, `404`, `409` |
| `POST` | `/device/cameras/{cameraCode}/heartbeat` | 카메라 Heartbeat·상태 갱신 | `X-Device-Key`, `occurredAt`, `status`, `detail` | `204`, `400`, `401`, `403`, `404`, `429` |
| `POST` | `/device/cameras/{cameraCode}/recordings` | 업로드 완료 녹화 메타데이터 등록 | `X-Device-Key`, `Idempotency-Key`, 촬영 시간, Object Key | `201`, `200`, `400`, `401`, `403`, `404`, `409`, `413`, `415`, `422`, `503` |
| `GET` | `/device/search-targets` | 임베디드·실시간 처리기용 활성 검색 대상 조회 | `X-Device-Key`, `If-None-Match` | `200`, `304`, `401`, `403` |
| `GET` | `/admin/recordings` | 녹화 목록 | `cameraId`, 촬영 구간, 페이지·정렬 조건 | `200`, `400` |
| `GET` | `/admin/recordings/{recordingId}` | 녹화 상세와 재생 URL | `recordingId` | `200`, `404`, `503` |
| `POST` | `/device/candidate-events` | 미디어 서버 후보 이벤트 등록 | `X-Device-Key`, `Idempotency-Key`, 사건, 카메라, 탐지 시각, 유사도, 이미지 | `201`, `200`, `400`, `401`, `403`, `404`, `409`, `413`, `415`, `422`, `429` |

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
| `Cookie: EYESONU_SESSION={sessionId}` | 조건부 | 관리자 API 호출 시 필수. 브라우저가 자동으로 전송하는 `HttpOnly` 세션 쿠키 |
| `X-XSRF-TOKEN: {csrfToken}` | 조건부 | 로그인과 관리자 상태 변경 API 호출 시 `XSRF-TOKEN` 쿠키와 같은 값을 전송 |
| `X-Device-Key: msk_{deviceKeyId}.{randomSecret}` | 조건부 | 모든 `/device/**` API 호출 시 필수. `deviceKeyId`는 16자리, `randomSecret`은 64자리 소문자 16진수 |
| `Content-Type` | 필수 | `application/json` 또는 `multipart/form-data` |
| `Idempotency-Key` | 조건부 | 녹화 메타데이터와 후보 이벤트 등록 시 필수인 UUID. 각 등록 API에서 인증된 미디어 서버 단위로 해석 |
| `X-Request-Id` | 선택 | 호출 추적용 ID. 없으면 서버에서 생성 |

관리자 세션·CSRF 규칙:

- 세션 쿠키 이름은 `EYESONU_SESSION`이며 `HttpOnly`, `SameSite=Lax`, `Path=/` 속성을 사용한다. 운영 프로필에서는 `Secure` 속성도 사용한다.
- 세션 유효 시간은 마지막 요청부터 30분이며, 관리자 한 명당 세션 하나만 유지한다. 새 로그인은 기존 세션을 만료시킨다.
- 브라우저는 로그인 전에 `GET /api/v1/auth/csrf`를 호출하고, 응답 쿠키 `XSRF-TOKEN`의 값을 로그인 요청의 `X-XSRF-TOKEN` 헤더에 담는다.
- 로그인 성공 또는 로그아웃 후에는 `GET /api/v1/auth/csrf`를 다시 호출해 새로운 CSRF 토큰을 사용한다.
- `GET` 관리자 API는 세션만 필요하고, `POST`·`PATCH`·`DELETE` 관리자 API는 세션과 CSRF 토큰이 모두 필요하다.
- 인증 API, `/admins/me`, 사건 진행 조회 API의 성공·오류 응답에는 `Cache-Control: no-store`를 적용한다.
- Device Key 원문을 반환하는 미디어 서버 등록·키 교체 응답에도 `Cache-Control: no-store`를 적용한다.

### 3.2 미디어 서버 Device Key 인증

- `/api/v1/device/**`는 관리자 세션과 분리된 Stateless API다. 세션을 생성하지 않고 CSRF 검사에서 제외하며 `ROLE_MEDIA_SERVER` 권한이 필요하다.
- Device Key는 중앙 서버가 `msk_<deviceKeyId>.<randomSecret>` 형식으로 생성한다. `deviceKeyId`는 16자리 소문자 16진수이며, `randomSecret`은 암호학적으로 안전한 32바이트 난수를 64자리 소문자 16진수로 표현한다.
- `deviceKeyId`는 미디어 서버를 조회하기 위한 공개 식별자이며, `randomSecret`만 bcrypt 또는 Argon2 계열의 적응형 단방향 해시로 저장한다.
- Device Key 원문은 최초 발급과 키 교체 응답에서 각각 한 번만 반환하며 중앙 서버의 DB와 로그에 저장하지 않는다.
- 인증 필터는 `X-Device-Key` 헤더와 형식을 확인하고, `deviceKeyId`로 미디어 서버를 조회한 뒤 상태와 secret 해시를 검증한다.
- 인증에 성공하면 `mediaServerId`, `serverCode`, `ROLE_MEDIA_SERVER`를 가진 `MediaServerPrincipal`을 SecurityContext에 저장하고 `lastAuthenticatedAt`을 갱신한다.
- 서비스 계층은 요청의 `cameraCode`가 인증된 `mediaServerId` 소속인지 검사한다. 다른 미디어 서버 소속이면 `403 ACCESS_DENIED`를 반환한다.
- 헤더 누락은 `401 AUTHENTICATION_REQUIRED`, 형식 오류·미등록 ID·secret 불일치·`INACTIVE`·`REVOKED` 상태는 원인을 구분하지 않고 `401 INVALID_DEVICE_KEY`를 반환한다.
- Device API는 HTTPS로만 제공한다. Device Key를 URL·Query Parameter·요청 로그·오류 로그에 포함하지 않으며 IP 제한은 보조 통제로만 사용한다.
- 미디어 서버마다 서로 다른 Device Key를 사용하며 카메라, Jetson 또는 다른 미디어 서버와 공유하지 않는다. Jetson의 후보 탐지 결과는 해당 카메라를 관리하는 미디어 서버가 중앙 서버로 전달한다.

### 3.3 성공 응답

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

### 3.4 오류 응답

오류 응답:

```json
{
  "timestamp": "2026-07-20T01:30:00Z",
  "status": 400,
  "code": "VALIDATION_ERROR",
  "message": "요청 값이 올바르지 않습니다."
}
```

| 필드 | 필수 여부 | 설명 |
| --- | --- | --- |
| `timestamp` | 필수 | 오류 발생 시각 |
| `status` | 필수 | HTTP 상태 코드 |
| `code` | 필수 | 클라이언트가 분기 처리할 오류 코드 |
| `message` | 필수 | 사용자에게 표시 가능한 오류 메시지 |
| `fieldErrors` | 선택 | 필드별 검증 실패 정보 |
| `traceId` | 선택 | 서버 로그 추적 ID |

| HTTP 상태 | 공통 오류 코드 | 사용 조건 |
| --- | --- | --- |
| `400 Bad Request` | `INVALID_REQUEST`, `VALIDATION_ERROR`, `CURRENT_PASSWORD_MISMATCH`, `INVALID_STATE_TRANSITION` | 형식 오류, 필드 검증 실패, 현재 비밀번호 불일치, 허용되지 않은 상태 전이 |
| `401 Unauthorized` | `AUTHENTICATION_REQUIRED`, `SESSION_EXPIRED`, `INVALID_CREDENTIALS`, `INVALID_DEVICE_KEY` | 관리자 세션 누락·만료, 로그인 정보 불일치 또는 장치 인증 실패 |
| `403 Forbidden` | `ACCESS_DENIED` | 역할 또는 장치 권한 부족 |
| `404 Not Found` | `RESOURCE_NOT_FOUND`, `INQUIRY_NOT_FOUND` | 리소스 없음 또는 사건조회번호·전화번호 불일치 |
| `409 Conflict` | `DUPLICATE_RESOURCE`, `IDEMPOTENCY_KEY_CONFLICT`, `RESOURCE_STATE_CONFLICT`, `OPTIMISTIC_LOCK_CONFLICT`, `CASE_CLOSE_CONFLICT` | 중복 생성, 멱등 키 충돌, 리소스 상태 충돌, 버전 충돌, 종료 조건 불충족 |
| `413 Payload Too Large` | `FILE_TOO_LARGE` | 허용 용량을 초과한 파일 |
| `415 Unsupported Media Type` | `UNSUPPORTED_MEDIA_TYPE` | 지원하지 않는 요청 Content-Type 또는 이미지·영상 형식 |
| `422 Unprocessable Entity` | `BUSINESS_RULE_VIOLATION`, `STORAGE_OBJECT_NOT_FOUND`, `STORAGE_OBJECT_INVALID` | 업무 규칙 위반, 녹화 객체 미존재 또는 사용할 수 없는 저장소 객체 |
| `429 Too Many Requests` | `RATE_LIMIT_EXCEEDED` | 로그인·사건 진행 조회·Device 인증 또는 요청 허용 횟수 초과 |
| `500 Internal Server Error` | `INTERNAL_SERVER_ERROR` | 처리되지 않은 서버 오류 |
| `503 Service Unavailable` | `DATABASE_UNAVAILABLE`, `AUTHENTICATION_UNAVAILABLE`, `ADMIN_UPDATE_FAILED`, `STORAGE_UNAVAILABLE`, `ANALYSIS_SERVICE_UNAVAILABLE` | 데이터베이스, 인증, 저장소 또는 분석 시스템 일시 장애 |

### 3.5 페이지네이션과 정렬

| 파라미터 | 기본값 | 제한 | 설명 |
| --- | --- | --- | --- |
| `page` | `0` | `0` 이상 | 0부터 시작하는 페이지 번호 |
| `size` | `20` | `1`~`100` | 페이지 크기 |
| `sort` | 리소스별 기본값 | 허용 필드만 사용 | `{field},{asc\|desc}` 형식. 여러 번 전달 가능 |

잘못된 정렬 필드는 `400 VALIDATION_ERROR`로 처리한다.

### 3.6 파일과 민감 정보

- `password`, `photoS3Key`, `imageS3Key`, `clipS3Key`, `objectKey`, `s3Key`, `rtspUrl`, `deviceKeyHash`는 외부 응답에 노출하지 않는다.
- Device Key 원문은 미디어 서버 등록·키 교체 응답에서만 한 번 반환하며 이후 다시 조회할 수 없다.
- 사진·후보 이미지·클립은 만료 시간이 있는 `photoUrl`, `imageUrl`, `clipUrl`로 반환한다. 녹화 `videoUrl`은 관리자 상세 응답에만 포함한다.
- URL 만료 시 리소스를 다시 조회해 새로운 URL을 발급받는다.
- 지원 이미지 형식은 JPEG·PNG·WebP, 녹화 생성 주체가 업로드하는 영상 형식은 MP4(H.264)를 기본으로 한다. 녹화 등록 API는 `.mp4` 객체 키와 저장소 메타데이터만 검증하며 파일 본문을 내려받거나 H.264 코덱을 검사하지 않는다.
- 사건 사진은 최대 10 MiB이며 선언된 Content-Type과 실제 JPEG·PNG·WebP 파일 시그니처가 일치해야 한다.
- 파일 크기 제한은 배포 환경 설정값을 따른다. 녹화는 local/test에서 5 GiB를 사용하고 prod에서는 `RECORDING_MAX_FILE_SIZE_BYTES`를 필수로 지정하며, HEAD/stat에서 확인한 실제 크기가 제한을 초과하면 `413 FILE_TOO_LARGE`를 반환한다.

### 3.7 주요 검증 규칙

- `caseNumber`는 앞뒤 공백을 제거하고 대문자로 변환한 뒤 검증한다. 형식은 `EFU-`와 Crockford Base32 26자로 구성된 총 30자 문자열이다.
- `phone`은 ASCII 숫자(`0`~`9`), ASCII 하이픈(`-`), ASCII 공백(`U+0020`)만 허용한다. 하이픈과 공백을 제거한 정규화 결과가 숫자 10~11자리여야 하며, 그 밖의 문자·공백 문자는 제거하지 않고 검증 오류로 거부한다.
- `cameraCode`는 앞뒤 공백을 제거한 후 검증한다. `loginId`는 앞뒤 공백을 제거하고 소문자로 변환한다.
- 위도는 `-90`~`90`, 경도는 `-180`~`180` 범위여야 한다.
- `lastSeenLat`와 `lastSeenLng`는 함께 제공하거나 모두 생략한다.
- `similarity`, `similarityThreshold`는 `0.0000`~`1.0000` 범위여야 한다.
- 탐색 종료 시각은 탐색 시작 시각보다 빠를 수 없다.
- 관리자·브라우저 클라이언트는 내부 S3 Key, 생성·수정 시각, 검토 관리자 ID를 직접 지정할 수 없다. 예외적으로 인증된 미디어 서버는 녹화 등록 시 정해진 규칙의 `objectKey`를 제공한다.

로그인과 사건 진행 조회의 현행 Rate Limit은 실패 기준 10분 동안 동일 IP·식별자 조합 5회, 동일 IP 전체 30회다. 성공하면 해당 IP·식별자 조합의 실패 횟수는 초기화된다.

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
| `MediaServerStatus` | `ACTIVE`, `INACTIVE`, `REVOKED` |
| `CameraStatus` | `ONLINE`, `OFFLINE`, `ERROR` |
| `ReviewStatus` | `PENDING`, `KEPT`, `CONFIRMED`, `REJECTED` |
| `ClipStatus` | `PENDING`, `PROCESSING`, `READY`, `FAILED` |
| `AnalysisJobType` | `RECORDING_ANALYSIS`, `CLIP_GENERATION` |
| `AnalysisJobStatus` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` |

### 4.3 기타 상태 전이

| 구분 | 전이 규칙 |
| --- | --- |
| 미디어 서버 | 최초 `ACTIVE`; `ACTIVE ↔ INACTIVE`, `ACTIVE → REVOKED`, `INACTIVE → REVOKED`를 허용한다. `REVOKED`는 종단 상태이며 재활성화하거나 Device Key를 교체할 수 없다. |
| 카메라 | 정상 Heartbeat 수신 시 `ONLINE`, 기준 시간 동안 미수신 시 `OFFLINE`, 장치 오류 보고 시 `ERROR` |
| 후보 판정 | 최초 `PENDING`; 관리자는 `KEPT`, `CONFIRMED`, `REJECTED` 사이에서 재판정할 수 있으며 모든 변경을 감사 로그에 남김 |
| 클립 | `PENDING → PROCESSING → READY` 또는 `FAILED`, 재시도 시 `FAILED → PROCESSING` |
| 분석 작업 | `QUEUED → RUNNING → SUCCEEDED` 또는 `FAILED`; 재시도 시 `FAILED → QUEUED`이며 `retryCount` 증가 |

---

## 5. 인증·신고·진행 조회 API

### 5.1 CSRF 토큰 발급

`GET /api/v1/auth/csrf`

- 인증: 없음
- 요청 본문: 없음
- 응답: `204 No Content`
- 응답 헤더: `Set-Cookie: XSRF-TOKEN={token}; Path=/; SameSite=Lax`

응답 본문은 없다. 브라우저는 `XSRF-TOKEN` 쿠키 값을 읽어 로그인과 관리자 상태 변경 요청의 `X-XSRF-TOKEN` 헤더로 전송한다.

### 5.2 관리자 로그인

`POST /api/v1/auth/admin/login`

- 인증: 없음
- CSRF: 필수
- Content-Type: `application/json`

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
    "id": 1,
    "loginId": "control01",
    "name": "관제 관리자"
  }
}
```

로그인 성공 시 `EYESONU_SESSION` 쿠키를 발급한다. 응답 본문에 토큰을 반환하지 않으며 이후 관리자 API는 브라우저가 전송하는 세션 쿠키로 인증한다.

주요 오류:

| 조건 | 응답 |
| --- | --- |
| 요청 값 검증 실패 | `400 VALIDATION_ERROR` |
| 로그인 정보 불일치 | `401 INVALID_CREDENTIALS` |
| CSRF 토큰 누락 또는 불일치 | `403 ACCESS_DENIED` |
| 로그인 시도 횟수 초과 | `429 RATE_LIMIT_EXCEEDED` |
| 인증·데이터베이스 또는 필수 감사 로그 장애 | `503` |

### 5.3 관리자 로그아웃

`POST /api/v1/auth/admin/logout`

- CSRF: 필수
- 요청 본문: 없음
- 응답: `204 No Content`

인증된 세션이 있으면 해당 세션을 무효화하고 `EYESONU_SESSION`, `XSRF-TOKEN` 쿠키를 만료시킨다. 세션 유무와 관계없이 올바른 CSRF 토큰이 필요하며, 누락하거나 일치하지 않으면 `403 ACCESS_DENIED`를 반환한다.

### 5.4 로그인 관리자 정보

#### 5.4.1 내 정보 조회

`GET /api/v1/admins/me`

- 인증: 관리자 세션
- 주요 응답: `200`, `401`

응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T01:35:00Z",
  "data": {
    "id": 1,
    "loginId": "control01",
    "name": "관제 관리자"
  }
}
```

#### 5.4.2 내 정보 수정

`PATCH /api/v1/admins/me`

- 인증: 관리자 세션
- CSRF: 필수
- 주요 응답: `200`, `400`, `401`, `403`, `503`

요청:

```json
{
  "name": "통합 관제 관리자",
  "currentPassword": "current-password",
  "newPassword": "new-password-1234"
}
```

응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T01:40:00Z",
  "data": {
    "admin": {
      "id": 1,
      "loginId": "control01",
      "name": "통합 관제 관리자"
    },
    "reauthenticationRequired": true
  }
}
```

- `name` 또는 비밀번호 변경 정보 중 하나 이상을 제공해야 한다.
- `name`은 앞뒤 공백을 제거한 1~50자 문자열이다.
- 비밀번호 변경 시 `currentPassword`와 `newPassword`를 함께 제공해야 한다.
- 새 비밀번호는 12~64자이며 UTF-8 기준 72바이트 이하여야 한다.
- 현재 비밀번호가 일치하지 않으면 `400 CURRENT_PASSWORD_MISMATCH`를 반환한다.
- 이름만 변경하면 `reauthenticationRequired=false`이며 현재 세션을 유지한다.
- 비밀번호를 변경하면 `reauthenticationRequired=true`를 반환한 뒤 해당 관리자의 모든 세션을 종료한다.

### 5.5 사건 등록 주체

공개 사건 등록 API는 제공하지 않는다. 사건 등록은 6.1의 `POST /api/v1/admin/cases`를 사용하며 ADMIN 세션과 CSRF 토큰이 필요하다. reporter-webapp은 진행 조회만 제공하고 사건 등록 화면 제거는 별도 프런트 작업으로 관리한다.

### 5.6 신고자 사건 진행 조회

`POST /api/v1/cases/status-inquiries`

- 인증: 없음
- Content-Type: `application/json`
- 동일 IP 또는 전화번호의 반복 조회는 Rate Limit을 적용한다.
- `phone`은 3.7의 공통 규칙으로 검증·정규화한 뒤 사건에 저장된 전화번호와 비교한다.

요청:

```json
{
  "caseNumber": "EFU-0123456789ABCDEFGHJKMNPQRS",
  "phone": "01012345678"
}
```

응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T02:20:00Z",
  "data": {
    "caseNumber": "EFU-0123456789ABCDEFGHJKMNPQRS",
    "status": "SEARCHING",
    "reportedAt": "2026-07-20T01:30:00Z",
    "updatedAt": "2026-07-20T02:20:00Z",
    "closedAt": null
  }
}
```

공개 필드:

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `caseNumber` | string | 사건 조회번호 |
| `status` | CaseStatus | 현재 진행 상태 |
| `reportedAt` | datetime | 신고 접수 시각 |
| `updatedAt` | datetime | 사건 정보가 마지막으로 변경된 시각 |
| `closedAt` | datetime, nullable | 사건 종료 시각 |

- 사건조회번호와 전화번호가 모두 동일한 사건에 연결될 때만 정보를 반환한다.
- 둘 중 하나라도 일치하지 않으면 어떤 값이 틀렸는지 구분하지 않고 `404 INQUIRY_NOT_FOUND`를 반환한다.

실종자 이름·사진·마지막 목격 정보, 후보와 확정 목격 정보, 유사도, 원본 CCTV 영상, `cameraId`, 내부 관리자 정보와 감사 로그는 노출하지 않는다.

---

## 6. 관리자 사건 API

이 절의 모든 엔드포인트는 별도 표기가 없으면 ADMIN 세션이 필요하며, 상태 변경 요청에는 CSRF 토큰도 필요하다.

### 6.1 사건 관리

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `POST` | `/admin/cases` | 사건 등록 | 신고자, 실종자, 구조화 인상착의, 마지막 목격 정보 | `201`, `400`, `401`, `403`, `503` |
| `GET` | `/admin/cases` | 사건 목록 | `status`, `caseNumber`, `missingName`, `reportedFrom`, `reportedTo`, 페이지 조건 | `200`, `400` |
| `GET` | `/admin/cases/{caseId}` | 사건 상세 | Path: `caseId` | `200`, `404` |
| `PATCH` | `/admin/cases/{caseId}` | 사건 정보 수정 | 신고자, 실종자, 인상착의, 마지막 목격 정보 | `200`, `400`, `404`, `422` |
| `PUT` | `/admin/cases/{caseId}/photo` | 선택 사진 등록·교체 | multipart `photo` | `200`, `400`, `404`, `413`, `415`, `422`, `503` |
| `DELETE` | `/admin/cases/{caseId}/photo` | 사진 제거 | Path: `caseId` | `204`, `404` |
| `PATCH` | `/admin/cases/{caseId}/status` | 종료를 제외한 상태 변경 | `status`, `reason` | `200`, `400`, `404`, `422` |
| `POST` | `/admin/cases/{caseId}/close` | 사건 종료 | `reason`, `force` | `200`, `404`, `409` |

등록 요청 예시:

```json
{
  "reporter": {
    "name": "홍길동",
    "phone": "010-1234-5678",
    "email": "reporter@example.com",
    "relation": "보호자"
  },
  "reportContent": "마지막 연락 이후 귀가하지 않았습니다.",
  "missingName": "김민수",
  "gender": "MALE",
  "birthYear": 2001,
  "appearance": {
    "hair": "짧은 검은 머리",
    "face": null,
    "upperClothing": "검은색 셔츠",
    "lowerClothing": "청바지",
    "shoes": "흰색 운동화",
    "belongings": "검은색 백팩",
    "bodyType": null,
    "distinctiveFeatures": null
  },
  "lastSeenTime": "2026-07-20T00:10:00+09:00",
  "lastSeenLat": 37.5012345,
  "lastSeenLng": 127.0398765,
  "lastSeenAddress": "서울특별시 강남구"
}
```

- `reporter.name`, `reporter.phone`, `reportContent`, `missingName`, `gender`, `appearance`, `lastSeenTime`, `lastSeenAddress`는 필수다.
- 인상착의 8개 항목 중 하나 이상은 공백이 아닌 값이어야 한다.
- `birthYear`는 생략할 수 있으며 제공 시 1900년부터 현재 연도까지 허용한다.
- 사건 생성은 JSON으로 수행하고 사진과 초기 탐색 조건·카메라는 생성된 `caseId`로 별도 호출한다.
- 성공 시 `Location: /api/v1/admin/cases/{caseId}`와 사건 ID·사건번호·`RECEIVED` 상태·접수 시각을 반환한다.

목록 기본 정렬은 `reportedAt,desc`이며 `reportedAt`, `updatedAt`, `missingName`만 정렬할 수 있다. 수정은 last-write-wins 방식이며 요청에 없는 필드는 유지하고 nullable 필드의 명시적 `null`은 삭제한다. 인상착의 부분 수정은 등록과 동일하게 `appearance` 객체 안에 변경할 항목만 담는다.

사건 상세 응답 예시:

```json
{
  "timestamp": "2026-07-20T01:40:00Z",
  "data": {
    "id": 101,
    "caseNumber": "EFU-0123456789ABCDEFGHJKMNPQRS",
    "status": "SEARCHING",
    "reporter": {
      "id": 20,
      "name": "홍길동",
      "phone": "01012345678",
      "email": "reporter@example.com",
      "relation": "보호자"
    },
    "reportContent": "마지막 연락 이후 귀가하지 않았습니다.",
    "missingName": "김민수",
    "gender": "MALE",
    "birthYear": 2001,
    "appearance": {
      "hair": "짧은 검은 머리",
      "face": null,
      "upperClothing": "검은색 셔츠",
      "lowerClothing": "청바지",
      "shoes": "흰색 운동화",
      "belongings": "검은색 백팩",
      "bodyType": null,
      "distinctiveFeatures": null
    },
    "photoUrl": "https://media.example.com/signed/...",
    "lastSeenTime": "2026-07-20T00:10:00Z",
    "lastSeenLat": 37.5012345,
    "lastSeenLng": 127.0398765,
    "lastSeenAddress": "서울특별시 강남구",
    "reportedAt": "2026-07-20T01:30:00Z",
    "closedAt": null,
    "updatedAt": "2026-07-20T01:35:00Z"
  }
}
```

사건 종료:

- `force` 기본값은 `false`이다.
- 미처리 후보 또는 실행 중인 작업이 있으면 `force=false` 요청은 `409 CASE_CLOSE_CONFLICT`를 반환한다.
- `force=true`는 관리자 확인 후 미완료 작업을 취소하고 종료하며, 사유와 강제 종료 여부를 감사 로그에 남긴다.
- `RECEIVED`에서 `SEARCHING`으로 전환하려면 탐색 조건과 활성 사건 카메라가 각각 하나 이상 필요하다.
- 사건 자체의 `DELETE` API는 제공하지 않는다. 종료 후 보관기한 자동 파기는 후속 구현 범위다.
- 종료 사건은 정보 수정과 사진 등록·교체를 거부하지만 개인정보 제거를 위해 사진 삭제는 허용한다.
- 사진은 JPEG·PNG·WebP 한 장, 최대 10 MiB이며 Content-Type과 파일 시그니처가 일치해야 한다.

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

인증: ADMIN 세션

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

## 7. 미디어 서버·카메라 및 녹화 API

관리자 조회 API는 ADMIN 세션이 필요하며 등록·수정·키 교체 API는 CSRF 토큰도 필요하다.

### 7.1 관리자 미디어 서버 API

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/media-servers` | 미디어 서버 목록 | `status`, `search`, 페이지 조건 | `200`, `400` |
| `POST` | `/admin/media-servers` | 미디어 서버 등록·Device Key 최초 발급 | `serverCode`, `name` | `201`, `400`, `409` |
| `GET` | `/admin/media-servers/{mediaServerId}` | 미디어 서버 상세 | Path: `mediaServerId` | `200`, `404` |
| `PATCH` | `/admin/media-servers/{mediaServerId}` | 이름·상태 수정 | `name`, `status` | `200`, `400`, `404`, `409` |
| `POST` | `/admin/media-servers/{mediaServerId}/device-key/rotate` | Device Key 즉시 교체 | Path: `mediaServerId` | `200`, `404`, `409` |

목록 필터의 `search`는 `serverCode`와 `name`을 대상으로 하며 기본 정렬은 `createdAt,desc`이다.

등록 요청:

```json
{
  "serverCode": "rpi5-media-01",
  "name": "1층 미디어 서버"
}
```

등록 응답 `201 Created`:

```json
{
  "timestamp": "2026-07-20T01:30:00Z",
  "data": {
    "mediaServer": {
      "id": 11,
      "serverCode": "rpi5-media-01",
      "name": "1층 미디어 서버",
      "deviceKeyId": "0123456789abcdef",
      "status": "ACTIVE",
      "lastAuthenticatedAt": null,
      "createdAt": "2026-07-20T01:30:00Z",
      "updatedAt": "2026-07-20T01:30:00Z"
    },
    "deviceKey": "msk_0123456789abcdef.0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }
}
```

수정 요청:

```json
{
  "name": "1층 통합 미디어 서버",
  "status": "INACTIVE"
}
```

Device Key 교체 응답은 등록 응답과 같은 구조로 현재 미디어 서버 정보와 새 `deviceKey`를 반환한다.

- `serverCode`와 `deviceKeyId`는 전체 미디어 서버에서 각각 고유하다.
- 등록 시 상태는 `ACTIVE`이며 서버가 Device Key를 생성한다. 클라이언트는 `deviceKeyId`, `randomSecret`, 해시를 지정할 수 없다.
- 등록·키 교체 응답 외의 목록·상세·수정 응답은 `deviceKey`와 `deviceKeyHash`를 포함하지 않는다.
- Device Key 원문은 감사 로그의 변경 전후 값이나 상세 설명에도 기록하지 않는다.
- 키 교체가 성공하는 즉시 이전 키는 사용할 수 없다. 활성 키를 하나만 보관하므로 무중단 키 교체와 키 이력은 지원하지 않는다.
- `INACTIVE` 서버는 다시 `ACTIVE`로 전환할 수 있지만 `REVOKED`는 재활성화하거나 키를 교체할 수 없다.
- `REVOKED` 서버의 상태 변경 또는 키 교체 요청은 `409 RESOURCE_STATE_CONFLICT`를 반환한다.
- 미디어 서버는 물리 삭제하지 않으며 운영 중지 또는 폐기는 상태 변경으로 처리한다.

### 7.2 관리자 카메라 API

| 메서드 | 경로 | 설명 | 주요 요청·필터 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/cameras` | 카메라 목록 | `status`, `search`, 페이지 조건 | `200`, `400` |
| `POST` | `/admin/cameras` | 카메라 등록 | 미디어 서버·카메라 식별 정보 | `201`, `400`, `404`, `409` |
| `GET` | `/admin/cameras/{cameraId}` | 카메라 상세 | Path: `cameraId` | `200`, `404` |
| `PATCH` | `/admin/cameras/{cameraId}/name` | 카메라 이름 수정 | `cameraName` | `200`, `400`, `404` |
| `PUT` | `/admin/cameras/{cameraId}` | 카메라 정보·소속 전체 수정 | 미디어 서버, 이름, 좌표, 주소, RTSP URL | `200`, `400`, `404` |

카메라 등록 요청:

```json
{
  "mediaServerId": 11,
  "cameraName": "Zone A 복도",
  "cameraCode": "camera-01",
  "latitude": 37.5015000,
  "longitude": 127.0402000,
  "address": "서울특별시 강남구",
  "rtspUrl": "rtsp://camera.internal/live"
}
```

- `mediaServerId`는 카메라의 Heartbeat, 녹화와 후보 이벤트 전송을 담당하는 미디어 서버 ID이며 필수다.
- 카메라 응답에는 소속 미디어 서버의 `id`, `serverCode`, `name`을 포함한다.
- `cameraCode`는 외부 식별자이며 전체 카메라에서 고유하다. Device API는 `cameraCode`를, 관리자 API와 DB 관계는 숫자 `cameraId`를 사용한다.
- 수정 API에서 `mediaServerId`를 변경하면 기존 서버의 접근 권한은 즉시 사라지고 새 서버에 권한이 부여된다. 소속 변경은 감사 로그에 기록한다.
- `rtspUrl`은 생성·수정 요청에서만 받고 조회 응답에는 포함하지 않는다.
- 최초 카메라 상태는 `OFFLINE`이다.

### 7.3 미디어 서버 Heartbeat

`POST /api/v1/device/cameras/{cameraCode}/heartbeat`

- 인증: `X-Device-Key: {deviceKey}`
- 주요 응답: `204`, `400`, `401`, `403`, `404`, `429`

```http
POST /api/v1/device/cameras/camera-01/heartbeat
X-Device-Key: msk_0123456789abcdef.0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
Content-Type: application/json
```

```json
{
  "occurredAt": "2026-07-20T02:00:00Z",
  "status": "ONLINE",
  "detail": null
}
```

- `cameraCode`가 인증된 미디어 서버 소속이 아니면 `403 ACCESS_DENIED`를 반환한다.
- 정상 처리 시 카메라의 `lastHeartbeat`, `status`, `updatedAt`을 갱신하고 `204 No Content`를 반환한다.

### 7.4 녹화 메타데이터 API

미디어 서버는 녹화 파일을 객체 저장소에 성공적으로 업로드한 뒤 메타데이터 등록 API를 호출한다. 이 API는 파일을 업로드하거나 업로드 진행 상태를 관리하지 않는다.

| 메서드 | 경로 | 인증 | 설명 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `POST` | `/device/cameras/{cameraCode}/recordings` | `X-Device-Key` | 업로드 완료 녹화 메타데이터 등록 | `201`, `200`, `400`, `401`, `403`, `404`, `409`, `413`, `415`, `422`, `503` |
| `GET` | `/admin/recordings` | ADMIN 세션 | 녹화 목록 조회 | `200`, `400` |
| `GET` | `/admin/recordings/{recordingId}` | ADMIN 세션 | 녹화 상세와 재생 URL 조회 | `200`, `404`, `503` |

#### 7.4.1 녹화 등록

등록 요청:

```http
POST /api/v1/device/cameras/camera-01/recordings
X-Device-Key: msk_0123456789abcdef.0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json
```

```json
{
  "startTime": "2026-07-20T01:50:00Z",
  "endTime": "2026-07-20T02:00:00Z",
  "objectKey": "recordings/camera-01/2026/07/20/015000.mp4"
}
```

| 필드 | 타입 | 필수 | 검증 규칙 |
| --- | --- | --- | --- |
| `startTime` | RFC 3339 datetime | 예 | UTC offset 필수, 소수점 최대 6자리. 서버는 같은 instant의 UTC `Z`로 정규화 |
| `endTime` | RFC 3339 datetime | 예 | UTC offset 필수, 소수점 최대 6자리이며 `startTime`보다 커야 함 |
| `objectKey` | string | 예 | 대소문자를 구분하는 최대 500자 키. 선행 `/` 없이 `recordings/{cameraCode}/`로 시작하고 소문자 `.mp4`로 끝나야 함 |

- `objectKey`의 `{cameraCode}`는 Path Variable과 정확히 일치해야 한다. 빈 경로 구간, `.`·`..` 경로 구간, 역슬래시, 제어 문자, 파일명이 없는 `.mp4`는 허용하지 않는다.
- 요청의 `fileSize`와 업로드 상태 필드는 받지 않는다. 서버가 저장소에서 확인한 실제 크기를 사용하며 등록된 녹화는 곧 사용 가능한 완료본이다.
- `Idempotency-Key`는 UUID 형식이며 이 API 안에서 인증된 `mediaServerId` 단위로 해석한다.
- 멱등 비교 대상은 소유권 확인이 끝난 `cameraCode`, UTC instant로 정규화한 `startTime`·`endTime`, 대소문자를 보존한 `objectKey`다. JSON 공백과 필드 순서는 비교 결과에 영향을 주지 않는다.

처리 순서:

1. `X-Device-Key`를 인증하고 `MediaServerPrincipal`을 생성한다.
2. 촬영 구간, `objectKey`, `Idempotency-Key` 형식을 검증하고 촬영 시각을 UTC instant로 정규화한다.
3. `cameraCode`의 존재 여부와 인증된 미디어 서버 소속 여부를 검증한다.
4. 동일 멱등 요청이 이미 성공했다면 저장소를 다시 조회하지 않고 기존 결과를 `200 OK`로 반환한다.
5. 최초 요청이면 설정된 버킷과 `objectKey`로 HEAD/stat을 실행한다.
6. 객체가 존재하고 실제 크기가 0보다 크며 환경별 제한 이하인지 확인한다.
7. 별도 DB 트랜잭션에서 카메라 소유권을 잠금 재확인하고 녹화와 성공 멱등 요청을 원자적으로 생성한 뒤, 생성 행을 재조회한다.

- 성공한 S3 PUT 이후 HEAD는 강한 일관성을 가지므로 객체 미발견을 전파 지연으로 처리하지 않는다. 자세한 내용은 [Amazon S3 데이터 일관성 모델](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html)을 따른다.
- [S3 HeadObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html) 또는 [MinIO statObject](https://docs.min.io/aistor/developers/sdk/java/api/)로 메타데이터만 조회하며 파일 본문을 다운로드하거나 H.264 코덱을 검사하지 않는다.
- 전송 무결성이 필요하면 업로드 과정에서 객체 저장소의 체크섬 기능을 사용한다. multipart ETag를 전체 파일 MD5로 간주하지 않는다. 자세한 내용은 [Amazon S3 객체 무결성 검사](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html)를 따른다.

신규 등록 응답 `201 Created`:

```json
{
  "timestamp": "2026-07-20T02:00:01Z",
  "data": {
    "id": 501,
    "cameraId": 1,
    "startTime": "2026-07-20T01:50:00Z",
    "endTime": "2026-07-20T02:00:00Z",
    "fileSize": 104857600,
    "duplicate": false,
    "createdAt": "2026-07-20T02:00:01Z"
  }
}
```

동일 요청 재전송 응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T02:00:03Z",
  "data": {
    "id": 501,
    "cameraId": 1,
    "startTime": "2026-07-20T01:50:00Z",
    "endTime": "2026-07-20T02:00:00Z",
    "fileSize": 104857600,
    "duplicate": true,
    "createdAt": "2026-07-20T02:00:01Z"
  }
}
```

- 같은 `Idempotency-Key`와 같은 요청은 최초 생성된 `id`, `fileSize`, `createdAt`을 유지한다.
- 같은 키에 다른 요청 내용을 사용하면 `409 IDEMPOTENCY_KEY_CONFLICT`를 반환한다.
- `objectKey`는 버킷 전체에서 대소문자를 구분해 고유하다. 다른 Idempotency-Key로 같은 객체를 등록하면 `409 DUPLICATE_RESOURCE`를 반환한다.
- 저장소 검증에 실패하면 녹화 리소스를 생성하지 않는다. 객체 또는 저장소를 정상화한 뒤 같은 키와 같은 요청으로 재시도할 수 있다.

오류:

| 조건 | 응답 |
| --- | --- |
| `X-Device-Key` 누락 | `401 AUTHENTICATION_REQUIRED` |
| Device Key 형식 오류·미등록 ID·secret 불일치·비활성 또는 폐기 서버 | `401 INVALID_DEVICE_KEY` |
| 존재하지 않는 `cameraCode` | `404 RESOURCE_NOT_FOUND` |
| 다른 미디어 서버 소속 `cameraCode` | `403 ACCESS_DENIED` |
| 필수 필드·RFC 3339 offset·시간 범위·객체 키·UUID 형식 오류 | `400 VALIDATION_ERROR` |
| `application/json`이 아닌 요청 | `415 UNSUPPORTED_MEDIA_TYPE` |
| 같은 Idempotency-Key에 다른 요청 내용 사용 | `409 IDEMPOTENCY_KEY_CONFLICT` |
| 다른 Idempotency-Key로 같은 `objectKey` 등록 | `409 DUPLICATE_RESOURCE` |
| 저장소에 객체가 없음 | `422 STORAGE_OBJECT_NOT_FOUND` |
| 객체 크기가 0 | `422 STORAGE_OBJECT_INVALID` |
| 객체가 환경별 용량 제한을 초과함 | `413 FILE_TOO_LARGE` |
| 저장소 권한·타임아웃·연결 또는 서비스 장애 | `503 STORAGE_UNAVAILABLE` |

Device 공통 rate limit은 허용량 정책이 확정된 뒤 별도 작업으로 정의하며, 이 녹화 등록 API와 OpenAPI에는 아직 `429`를 명세하지 않는다.

#### 7.4.2 관리자 녹화 조회

목록 요청:

```http
GET /api/v1/admin/recordings?cameraId=1&startFrom=2026-07-20T01:00:00Z&startTo=2026-07-20T03:00:00Z&page=0&size=20&sort=startTime,desc
```

| 쿼리 파라미터 | 필수 | 설명 |
| --- | --- | --- |
| `cameraId` | 아니요 | 특정 카메라 ID |
| `startFrom` | 아니요 | 조회 구간 시작. RFC 3339 offset 필수, 소수점 최대 6자리 |
| `startTo` | 아니요 | 조회 구간 끝. RFC 3339 offset 필수, 소수점 최대 6자리 |
| `page` | 아니요 | 기본값 `0`, 0 이상 |
| `size` | 아니요 | 기본값 `20`, `1`~`100` |
| `sort` | 아니요 | `startTime` 또는 `createdAt`과 `asc`·`desc` 조합 |

- 기간 필터는 반개방 조회 구간 `[startFrom, startTo)`과 녹화 구간이 겹치는 녹화본을 반환한다.
- 양쪽 경계를 지정하면 `recording.startTime < startTo AND recording.endTime > startFrom`을 적용한다.
- `startFrom`만 지정하면 `recording.endTime > startFrom`, `startTo`만 지정하면 `recording.startTime < startTo`를 적용한다.
- `startFrom >= startTo`이면 `400 VALIDATION_ERROR`를 반환한다.
- 기본 정렬은 `startTime,desc`이며 같은 `startTime`에서는 `id,desc`를 적용한다. 사용자 지정 정렬에서도 같은 값은 `id,desc`로 고정한다.

목록 응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T03:00:00Z",
  "data": [
    {
      "id": 501,
      "camera": {
        "id": 1,
        "cameraCode": "camera-01",
        "cameraName": "Zone A 복도"
      },
      "startTime": "2026-07-20T01:50:00Z",
      "endTime": "2026-07-20T02:00:00Z",
      "fileSize": 104857600,
      "createdAt": "2026-07-20T02:00:01Z"
    }
  ],
  "meta": {
    "page": 0,
    "size": 20,
    "totalElements": 1,
    "totalPages": 1,
    "sort": "startTime,desc"
  }
}
```

상세 응답 `200 OK`:

```json
{
  "timestamp": "2026-07-20T03:00:05Z",
  "data": {
    "id": 501,
    "camera": {
      "id": 1,
      "cameraCode": "camera-01",
      "cameraName": "Zone A 복도"
    },
    "startTime": "2026-07-20T01:50:00Z",
    "endTime": "2026-07-20T02:00:00Z",
    "fileSize": 104857600,
    "videoUrl": "https://media.example.com/signed/recording-501",
    "createdAt": "2026-07-20T02:00:01Z"
  }
}
```

- 목록과 상세는 `id`, 카메라의 `id`·`cameraCode`·`cameraName`, 촬영 구간, 실제 파일 크기, 생성 시각을 반환한다.
- 목록에는 `videoUrl`을 포함하지 않는다. 상세의 `videoUrl`은 만료되는 서명 URL이며 만료 후 상세 API를 다시 호출한다.
- `objectKey`와 내부 `s3Key`는 목록과 상세 어느 응답에도 노출하지 않는다.
- 상세 조회 중 서명 URL을 발급할 수 없으면 `503 STORAGE_UNAVAILABLE`을 반환한다.

---

## 8. AI 후보 이벤트 API

### 8.1 임베디드 검색 대상 조회

`GET /api/v1/device/search-targets`

- 인증: `X-Device-Key: {deviceKey}`
- 요청 본문과 쿼리 파라미터는 없다.
- 응답은 인증된 미디어 서버가 소유한 카메라가 등록된 `SEARCHING` 사건 중 활성 검색 조건이 하나 이상 있는 사건만 반환한다.
- 비활성화·삭제된 검색 조건과 카메라는 반환하지 않는다.
- 응답은 `Cache-Control: private, no-cache, must-revalidate`를 적용한다. 임베디드는 이 API 응답을 최신 기준 데이터로 사용한다.

```http
GET /api/v1/device/search-targets
X-Device-Key: msk_0123456789abcdef.0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

정상 응답 `200 OK`:

```json
{
  "timestamp": "2026-07-30T04:00:00Z",
  "data": [
    {
      "caseId": 101,
      "caseNumber": "EFU-20260730-0001",
      "searchConditions": [
        {
          "conditionId": 10,
          "prompt": "검은색 상의와 청바지를 입은 사람",
          "exclusionPrompt": "모자를 쓴 사람",
          "searchStart": "2026-07-30T03:00:00Z",
          "searchEnd": "2026-07-30T12:00:00Z",
          "searchArea": "강남역 일대",
          "similarityThreshold": 0.72
        }
      ],
      "cameras": [
        {
          "cameraId": 2,
          "cameraCode": "CAM-001"
        }
      ],
      "updatedAt": "2026-07-30T04:00:00Z"
    }
  ]
}
```

변경 없음 응답 `304 Not Modified`:

```http
HTTP/1.1 304 Not Modified
ETag: "media-server-7-search-targets-2026-07-30T04:00:00Z"
Cache-Control: private, no-cache, must-revalidate
```

- 디바이스는 직전 응답의 `ETag`를 `If-None-Match` 헤더로 전송한다.
- ETag는 미디어 서버별 검색 대상 변경 버전을 나타낸다.
- 변경이 없으면 서버는 전체 검색 대상 데이터를 다시 조회·직렬화하지 않고 `304`를 반환한다.

- `updatedAt`은 해당 사건의 검색 조건·검색 카메라 변경 여부를 확인하기 위한 최신 수정 시각이다. 활성 데이터뿐 아니라 비활성화·삭제된 검색 대상의 마지막 수정 시각도 반영될 수 있다.
- 모든 시간 필드는 JSON에서 UTC `Z`로 반환한다.
- `caseId`, `caseNumber`, 검색 조건과 카메라 외 신고자 개인정보·관리자 메모·Device Key·내부 저장소 정보는 반환하지 않는다.
- 사건에 활성 검색 조건이 없으면 해당 사건은 응답에서 제외한다.
- 인증된 미디어 서버가 소유하지 않은 카메라는 응답에 포함하지 않는다.
- 데이터가 없으면 `200 OK`와 빈 배열을 반환한다.

### 8.2 후보 이벤트 등록

`POST /api/v1/device/candidate-events`

- 인증: `X-Device-Key: {deviceKey}`
- 주요 응답: `201`, `200`(동일 요청 재전송), `400`, `401`, `403`, `404`, `409`, `413`, `415`, `422`, `429`
- Content-Type: `multipart/form-data`
- 헤더 `Idempotency-Key`: 미디어 서버가 이벤트별로 생성한 필수 UUID. 이 API 안에서 인증된 `mediaServerId` 단위로 해석
- `metadata`: 아래 JSON 구조
- `image`: 필수 후보 크롭 이미지

```http
POST /api/v1/device/candidate-events
X-Device-Key: msk_0123456789abcdef.0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
Idempotency-Key: 27bc8f50-5cf1-46b1-96c8-73e06f8f84ab
Content-Type: multipart/form-data
```

`metadata` 파트:

```json
{
  "caseId": 101,
  "cameraCode": "camera-02",
  "detectedTime": "2026-07-20T02:00:12Z",
  "similarity": 0.8421
}
```

필수 필드: `caseId`, `cameraCode`, `detectedTime`, `similarity`, `image`

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

1. `X-Device-Key`를 인증하고 `MediaServerPrincipal`을 생성한다.
2. `cameraCode`의 카메라가 인증된 미디어 서버 소속인지 확인한다.
3. 사건과 카메라가 존재하고 사건이 종료되지 않았는지 검증한다.
4. 카메라가 해당 사건의 활성 탐색 대상으로 지정됐는지 확인한다.
5. `Idempotency-Key`와 요청 내용의 중복 여부를 확인한다.
6. 이미지와 유사도 범위를 검증하고 이미지를 저장한다.
7. `CANDIDATES`를 생성하고 필요한 클립 생성 작업을 `ANALYSIS_JOBS`에 등록한다.

오류:

| 조건 | 응답 |
| --- | --- |
| `X-Device-Key` 누락 | `401 AUTHENTICATION_REQUIRED` |
| `X-Device-Key` 오류 또는 비활성·폐기 미디어 서버 | `401 INVALID_DEVICE_KEY` |
| 다른 미디어 서버 소속 `cameraCode` 사용 | `403 ACCESS_DENIED` |
| 존재하지 않는 사건·카메라 | `404 RESOURCE_NOT_FOUND` |
| 같은 Idempotency-Key에 다른 요청 내용 사용 | `409 IDEMPOTENCY_KEY_CONFLICT` |
| 종료된 사건 또는 비활성 탐색 카메라 | `422 BUSINESS_RULE_VIOLATION` |
| UUID·유사도 범위 오류 또는 필수 필드 누락 | `400 VALIDATION_ERROR` |
| 요청 속도 제한 초과 | `429 RATE_LIMIT_EXCEEDED` |

같은 `Idempotency-Key`와 같은 요청을 재전송하면 최초 생성 결과를 `200 OK`, `duplicate=true`로 반환한다. `Idempotency-Key`는 중복 요청 제어용 서버 관리 데이터이며 `CANDIDATES`의 비즈니스 필드에는 포함하지 않는다.

Jetson은 후보 탐지를 수행하고 해당 카메라를 관리하는 미디어 서버에 결과를 전달한다. 중앙 서버 Device API 호출과 Device Key 보관은 미디어 서버가 담당한다.

---

## 9. 분석 작업 API

| 메서드 | 경로 | 인증 | 설명 | 주요 응답 |
| --- | --- | --- | --- | --- |
| `POST` | `/admin/cases/{caseId}/analysis-jobs` | ADMIN 세션 | 녹화 영상 분석 작업 생성 | `202`, `400`, `404`, `409` |
| `GET` | `/admin/cases/{caseId}/analysis-jobs` | ADMIN 세션 | 사건별 분석 작업 목록 | `200`, `404` |
| `GET` | `/admin/analysis-jobs/{jobId}` | ADMIN 세션 | 작업 상세 조회 | `200`, `404` |
| `POST` | `/admin/analysis-jobs/{jobId}/retry` | ADMIN 세션 | 실패 작업 재시도 | `202`, `404`, `409` |

작업 생성 요청:

```json
{
  "jobType": "RECORDING_ANALYSIS",
  "searchConditionId": 301,
  "recordingIds": [501, 502]
}
```

- `recordingIds`를 생략하면 사건의 활성 카메라와 탐색 시간 범위에 포함되며 등록 및 저장소 검증이 끝난 녹화본을 서버가 선정한다.
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

인증: ADMIN 세션
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
| `REPORTERS` | 관리자가 입력한 사건별 연락처 스냅샷, 사건조회번호·전화번호 기반 진행 조회 | v1에서는 사건마다 새로 생성하며 각 `REPORTERS`는 해당 `CASES` 한 건에만 사용 |
| `CASES` | 관리자 사건 등록·관리, 신고자 진행 조회 | 탐색 조건·후보·작업·로그의 기준 사건 |
| `SEARCH_CONDITIONS` | `/admin/cases/{caseId}/search-conditions` | `CASES 1:N SEARCH_CONDITIONS` |
| `MEDIA_SERVERS` | 관리자 미디어 서버 관리, Device Key 인증·교체 | `MEDIA_SERVERS 1:N CAMERAS` |
| `CAMERAS` | 관리자 카메라 관리, Heartbeat, 후보 이벤트 | 미디어 서버 소속이며 녹화·후보의 촬영 카메라 |
| `CASE_CAMERAS` | 사건별 카메라 지정·제외 | `CASES N:M CAMERAS` 연결 및 활성 여부 |
| `RECORDINGS` | 업로드 완료 객체의 HEAD/stat 검증 후 메타데이터 등록, 관리자 녹화 조회 | `CAMERAS 1:N RECORDINGS` |
| `CANDIDATES` | 후보 이벤트 등록, 관리자 후보 조회·판정, 동선 | 사건·카메라·검토 관리자 참조 |
| `ANALYSIS_JOBS` | 분석 작업 생성·조회·재시도, 클립 생성 내부 처리 | 사건 및 녹화본 또는 후보 참조 |
| `AUDIT_LOGS` | 감사 로그 조회, 모든 주요 변경의 내부 기록 | 관리자·사건과 선택적 연결 |

`MEDIA_SERVERS` 주요 컬럼:

| 컬럼 | 제약·설명 |
| --- | --- |
| `id` | 내부 숫자 ID, PK |
| `server_code` | 외부 식별자, UNIQUE |
| `name` | 관리자 표시 이름 |
| `device_key_id` | Device Key의 공개 조회 식별자, UNIQUE |
| `device_key_hash` | `randomSecret`의 bcrypt 또는 Argon2 계열 해시 |
| `status` | `ACTIVE`, `INACTIVE`, `REVOKED` |
| `last_authenticated_at` | 최근 Device Key 인증 성공 시각, nullable |
| `created_at`, `updated_at` | 생성·수정 시각 |

`CAMERAS.media_server_id`는 `MEDIA_SERVERS.id`를 참조하는 필수 FK다. Device Key는 카메라가 아닌 미디어 서버에만 저장하며 관계는 `MEDIA_SERVERS 1:N CAMERAS 1:N RECORDINGS`다.

---

## 12. 대표 오류 시나리오

| 시나리오 | 처리 |
| --- | --- |
| 탐색 종료가 시작보다 빠름 | `400 VALIDATION_ERROR` |
| 탐색 카메라 없이 분석 작업 요청 | `422 BUSINESS_RULE_VIOLATION` |
| `X-Device-Key` 헤더 누락 | `401 AUTHENTICATION_REQUIRED` |
| Device Key 형식 오류·미등록 ID·secret 불일치·비활성 또는 폐기 서버 | 상세 원인을 숨기고 `401 INVALID_DEVICE_KEY` 반환 |
| 다른 미디어 서버 소속 `cameraCode` 사용 | `403 ACCESS_DENIED` |
| 동일 녹화·후보 요청 재전송 | 최초 생성 결과를 `200`과 `duplicate=true`로 반환 |
| 같은 Idempotency-Key에 다른 요청 내용 사용 | `409 IDEMPOTENCY_KEY_CONFLICT` |
| 다른 Idempotency-Key로 같은 `objectKey` 등록 | `409 DUPLICATE_RESOURCE` |
| 녹화 객체가 저장소에 없음 | `422 STORAGE_OBJECT_NOT_FOUND`, 녹화 리소스 미생성 |
| 녹화 객체 크기가 0 | `422 STORAGE_OBJECT_INVALID`, 녹화 리소스 미생성 |
| 녹화 객체가 환경별 제한을 초과함 | `413 FILE_TOO_LARGE`, 녹화 리소스 미생성 |
| 녹화 객체 HEAD/stat 중 저장소 일시 장애 | `503 STORAGE_UNAVAILABLE`, 같은 멱등 요청으로 재시도 가능 |
| Device 요청 허용 횟수 초과 | `429 RATE_LIMIT_EXCEEDED` |
| 후보 판정 `version` 불일치 | `409 OPTIMISTIC_LOCK_CONFLICT`와 최신 후보 정보 반환 |
| 존재하지 않는 사건·카메라·후보 요청 | `404 RESOURCE_NOT_FOUND` |
| 실행 중인 작업 또는 미처리 후보가 있는 사건 종료 | `409 CASE_CLOSE_CONFLICT` |
| 종료 사건에 후보·탐색 작업 추가 | `422 BUSINESS_RULE_VIOLATION` |
| 전화번호에 ASCII 숫자·하이픈·공백 외 문자가 포함되거나 정규화 결과가 10~11자리가 아님 | `400 VALIDATION_ERROR` |
| 사건조회번호와 전화번호 조합 불일치 | 상세 불일치 원인을 숨기고 `404 INQUIRY_NOT_FOUND` 반환 |
| 동일 전화번호 또는 IP의 과도한 진행 조회 | `429 RATE_LIMIT_EXCEEDED` |

---

## 13. 구현 참고사항

- 서버 저장 일시는 모두 UTC를 사용하고 화면에서 KST 등 사용자 시간대로 변환한다.
- 관리자 비밀번호 검증은 단방향 해시를 사용하며 평문 비밀번호를 저장하거나 로그에 남기지 않는다.
- 관리자 API는 Stateful 세션 인증을, Device API는 Stateless Device Key 인증을 사용한다. Device API는 세션을 생성하지 않으며 CSRF 검사에서 제외한다.
- Device Key 인증 필터 또는 AuthenticationProvider는 헤더 파싱, 미디어 서버 조회, 상태·secret 검증과 `MediaServerPrincipal` 생성을 담당한다.
- 서비스 계층은 카메라 소유권, 녹화 `objectKey` 접두사와 업무 규칙을 검증한다. 인증 로직과 리소스 소유권 검사를 한 계층에 혼합하지 않는다.
- Device API는 HTTPS로만 제공하며 Device Key 원문은 최초 발급·교체 시 한 번만 전달하고 DB·소스 코드·Git·요청 및 오류 로그에 저장하지 않는다.
- 미디어 서버에서는 Device Key를 환경 변수, 실행 계정만 읽을 수 있는 설정 파일 또는 systemd credential로 관리한다.
- 미디어 서버당 활성 Device Key 하나만 지원하며 키 교체 즉시 이전 키를 무효화한다. 무중단 교체나 키 이력이 필요하면 별도 credentials 테이블을 도입한다.
- 후보 판정은 `CANDIDATES.version`을 이용한 낙관적 락으로 동시 수정을 방지한다.
- 후보 이미지·클립처럼 중앙 서버가 저장을 제어하는 파일은 실패 시 DB와 객체 저장소 사이의 보상 처리를 수행한다. 녹화는 미디어 서버가 먼저 업로드하며 중앙 서버의 HEAD/stat 검증에 실패하면 객체를 변경하거나 DB 행을 생성하지 않는다.
- 관리자 세션 만료 시간은 현재 30분이며 애플리케이션 설정으로 관리한다.
- 로그인·사건 진행 조회 Rate Limit은 현재 애플리케이션 상수로 적용한다. 장치 Heartbeat의 `OFFLINE` 판정 시간, 임시 미디어 URL 만료 시간과 파일 용량은 환경 설정으로 관리한다.
- REST 조회 API는 WebSocket 연결이 끊긴 동안 발생한 후보와 상태 변경을 복구 조회하는 기준 데이터로 사용한다.
