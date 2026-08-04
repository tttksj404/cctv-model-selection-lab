# 미디어 서버 Device Key 운영

미디어 서버는 중앙 서버의 다음 운영 API 경로를 호출할 때 `X-Device-Key` 헤더로 인증한다.

- `/api/v1/device/cameras/**`
- `/api/v1/device/candidate-events`

인증에 성공하면 중앙 서버는 요청을 `ROLE_MEDIA_SERVER` 권한과 해당 미디어 서버의 `mediaServerId`로 처리한다.

Device Key 형식은 `msk_<16자리 소문자 16진수 keyId>.<64자리 소문자 16진수 secret>`이다. 키 원문은 중앙 DB에 저장하지 않고,
`keyId`와 BCrypt cost 12로 인코딩한 secret만 저장한다.

## 1. 스키마 적용

백엔드를 실행해 Flyway V3까지 마이그레이션을 적용한다. V2는 `media_servers` 테이블을 생성하고
`cameras`를 `media_server_id`로 연결한다. V3는 업로드 상태 컬럼을 제거하고 녹화 메타데이터 제약과
성공한 등록 요청의 멱등성 테이블을 추가한다. V3 적용 시 기존 녹화와 이를 참조하는 녹화 분석 작업은 삭제된다.

## 2. Device Key 생성과 등록

백엔드 디렉터리에서 다음 명령을 실행한다.

Linux/macOS:

```bash
./mvnw -q exec:java \
  -Dexec.mainClass=com.ssafy.eyesonu.auth.device.tool.DeviceKeyProvisioningTool \
  -Dexec.args="generate rpi5-media-01 Raspberry Pi 5 Media Server"
```

Windows PowerShell:

```powershell
.\mvnw.cmd -q exec:java `
  '-Dexec.mainClass=com.ssafy.eyesonu.auth.device.tool.DeviceKeyProvisioningTool' `
  '-Dexec.args=generate rpi5-media-01 Raspberry Pi 5 Media Server'
```

도구는 전체 Device Key를 한 번 표시하고, 이어서 중앙 DB에 실행할 `INSERT` 문을 출력한다.

1. 전체 Device Key를 비밀번호 관리자 등 안전한 위치에 저장한다.
2. 출력된 `INSERT` 문을 중앙 DB에서 실행한다. SQL에는 키 원문이나 secret이 포함되지 않는다.
3. 라즈베리파이의 권한이 제한된 설정에 전체 Device Key를 `CENTRAL_API_DEVICE_KEY`로 저장한다.

이미 외부에서 생성한 키를 등록하려면 `generate` 대신 `import`를 사용한다. 키는 명령행 인수가
아니라 터미널의 숨김 입력으로 받는다.

```bash
./mvnw -q exec:java \
  -Dexec.mainClass=com.ssafy.eyesonu.auth.device.tool.DeviceKeyProvisioningTool \
  -Dexec.args="import rpi5-media-01 Raspberry Pi 5 Media Server"
```

## 3. 요청

```http
X-Device-Key: msk_<keyId>.<secret>
```

Device Key는 URL, 요청 본문, 로그에 기록하지 않는다. 실제 배포에서는 HTTPS로만 전송한다.

### Heartbeat 발신 주기

미디어 서버가 카메라 Heartbeat 발신 주기를 소유한다. 기본값은 10초이며, 실제 발신 주기는 미디어 서버의 `CAMERA_HEARTBEAT_INTERVAL` 설정(기본 `10s`)에서 조정한다.
중앙 서버는 Heartbeat를 생성하거나 발신하지 않고, 마지막 Heartbeat 수신 시각을 기준으로 timeout을 판정한다.
중앙 서버의 기본 `OFFLINE` timeout은 30초, 상태 확인 주기는 10초이며 다음 백엔드 환경 변수로 조정한다.

- `CAMERA_HEARTBEAT_OFFLINE_TIMEOUT_MS`
- `CAMERA_HEARTBEAT_STATUS_CHECK_INTERVAL_MS`

### Heartbeat 연동 재현 증거

아래 예시는 실제 Device Key를 노출하지 않는 redacted placeholder 기반 확인 절차다.

정상 Heartbeat 요청은 `204 No Content`를 반환해야 한다.

```bash
curl --fail-with-body --request POST \
  "${CENTRAL_API_BASE_URL}/api/v1/device/cameras/camera-01/heartbeat" \
  --header "X-Device-Key: <REDACTED_DEVICE_KEY>" \
  --header "Content-Type: application/json" \
  --data '{"occurredAt":"2026-07-20T02:00:00Z","status":"ONLINE","detail":null}'
```

정상 응답은 본문 없이 HTTP `204`다. 중앙 서버는 요청의 `occurredAt`을 UTC instant로 저장한다.

```sql
SELECT id, camera_code, status, last_heartbeat, updated_at
FROM cameras
WHERE camera_code = 'camera-01';
```

- Device Key 누락: `401` (`AUTHENTICATION_REQUIRED`)
- Device Key 형식·keyId·secret 오류 또는 비활성화된 키: `401` (`INVALID_DEVICE_KEY`)
- 인증된 미디어 서버에 속하지 않는 카메라: `403` (`ACCESS_DENIED`)
- 존재하지 않는 카메라: `404` (`RESOURCE_NOT_FOUND`)
- Heartbeat 발신을 중단한 뒤 30초 timeout과 다음 상태 확인 주기를 기다리면 `status = 'OFFLINE'`으로 전환된다. `last_heartbeat`는 변경되지 않는다.

### 녹화 업로드와 메타데이터 등록 순서

미디어 서버는 MinIO endpoint·bucket·app access key·app secret key나 Tailscale MinIO 주소를 보관하지 않는다. 배포 환경에서는 공용 HTTPS Device API로 업로드 URL을 발급받고, 응답의 공용 HTTPS `uploadUrl`에만 녹화본을 업로드한다. Tailscale은 dev 실시간 HLS 연결에만 사용한다.

1. 녹화를 마치면 canonical UUID를 `Idempotency-Key`로 생성하고 `POST /api/v1/device/cameras/camera-01/recording-upload-urls`를 호출한다. 요청 본문에는 UTC offset을 포함한 RFC 3339 `startTime`·`endTime`을 최대 6자리 소수 초로 보낸다.
2. 중앙 서버는 `recordings/camera-01/yyyy/MM/dd/yyyyMMddTHHmmssSSSSSSZ_{uuid}.mp4` 형식의 `objectKey`와 15분 동안 유효한 단일 PUT URL을 반환한다. 응답은 캐시하거나 로그에 기록하지 않는다.
3. `uploadUrl`에 원본 MP4 바이트를 `Content-Type: video/mp4`로 PUT한다. 이 요청에는 `X-Device-Key`를 추가하지 않는다. URL 만료 또는 전송 실패 시 최초 요청과 동일한 UUID, `startTime`, `endTime`으로 URL을 다시 발급받아 파일 전체를 재전송한다.
4. PUT 성공 후 `POST /api/v1/device/cameras/camera-01/recordings`에 같은 `Idempotency-Key`, `startTime`, `endTime`, 서버가 발급한 `objectKey`를 보내 완료를 등록한다.
5. 중앙 서버는 예상 object key 일치 여부와 객체의 실제 크기, `video/mp4` Content-Type, ISO BMFF `ftyp` 시그니처를 검증한 뒤 실제 파일 크기로 메타데이터를 등록한다.

녹화본의 최대 크기는 모든 환경에서 `104857600`바이트(100 MiB)다. URL 발급 응답의 `maxFileSizeBytes`도 같은 값을 반환하지만 presigned PUT 자체가 크기를 제한하지는 않으므로 업로더가 PUT 전에 크기를 검사해야 한다. URL 발급 내역은 DB에 저장하지 않으므로 재발급 입력을 임의로 바꾸지 않는다. 이미 같은 UUID로 완료 등록한 녹화에는 새 URL을 발급하지 않으며 `409 RECORDING_ALREADY_REGISTERED`를 반환한다.

완료 등록 성공 후에는 `uploadUrl`을 즉시 폐기하고 같은 object key에 다시 PUT하지 않는다. 완료 전에 발급된 URL은 등록 성공으로 취소되지 않으며 원래 만료 시각까지 유효하다.

완료 요청에는 `startTime`, `endTime`, `objectKey`만 포함하며 `fileSize`나 업로드 상태는 보내지 않는다. 객체가 없거나 사용할 수 없으면 녹화 리소스가 생성되지 않으므로 객체 저장소를 정상화한 뒤 같은 멱등 요청으로 재시도한다. Device 공통 rate limit은 별도 작업에서 확정하며 현재 녹화 URL 발급·등록 계약에는 `429` 응답을 포함하지 않는다.

### 임시 연결 테스트 API

백엔드와 Device Key 연결을 확인하는 동안 다음 임시 API를 사용할 수 있다.

```bash
curl --fail-with-body \
  -H "X-Device-Key: ${CENTRAL_API_DEVICE_KEY}" \
  "${CENTRAL_API_BASE_URL}/api/v1/device/media-server/ping"
```

정상 응답 예시:

```json
{
  "timestamp": "2026-07-27T06:00:00Z",
  "data": {
    "authenticated": true,
    "mediaServerId": 1,
    "serverCode": "rpi5-media-01"
  }
}
```

이 엔드포인트는 연동 확인 후 제거할 임시 API이며 Device Key 원문은 응답하지 않는다.

## 4. 비활성화와 교체

키를 폐기할 때는 해당 `media_servers.status`를 `DISABLED`로 바꾼다. 비활성 서버의 요청은
`401 INVALID_DEVICE_KEY`로 거부된다.

현재는 미디어 서버당 활성 키 하나만 지원하므로 무중단 키 교체를 지원하지 않는다. 교체 시 새 키와
해시를 준비하고 DB와 라즈베리파이 설정을 계획된 점검 시간에 함께 변경한다.
