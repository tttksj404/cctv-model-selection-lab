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

### 녹화 메타데이터 등록 순서

dev Tailscale 구성이 구현된 뒤 Raspberry Pi 5 업로더는 [dev Tailscale 연동 운영](<./Tailscale 연동 운영.md>)에 정의된 tailnet MinIO endpoint를 장치 업로드 전용으로 사용한다. 현재 `dev` 저장소에는 해당 Tailscale·MinIO 노출 구성이 적용되어 있지 않다. 적용 후에도 이 주소는 브라우저에 반환하지 않으며, 녹화 객체 업로드 후 메타데이터 등록은 기존 공용 HTTPS Device API로 수행한다.

1. 미디어 서버가 `recordings/{cameraCode}/.../*.mp4` 키와 소문자 `.mp4` 확장자로 녹화 파일을 MinIO에 업로드한다.
2. 업로드 성공 응답을 받은 뒤 `POST /api/v1/device/cameras/{cameraCode}/recordings`를 `X-Device-Key`와 `Idempotency-Key` 헤더로 호출한다.
3. 촬영 시각은 UTC offset을 포함한 RFC 3339 형식과 최대 6자리 소수 초로 전송한다. local/test의 녹화 객체 제한은 5 GiB이며 prod에서는 `RECORDING_MAX_FILE_SIZE_BYTES`를 반드시 지정한다.
4. 중앙 서버는 같은 버킷의 객체를 HEAD/stat으로 확인하고 실제 파일 크기로 메타데이터를 등록한다.

등록 요청에는 `startTime`, `endTime`, `objectKey`만 포함하며 `fileSize`나 업로드 상태는 보내지 않는다. 객체가 없거나 사용할 수 없으면 녹화 리소스가 생성되지 않으므로 객체 저장소를 정상화한 뒤 같은 멱등 요청으로 재시도한다.
Device 공통 rate limit은 별도 작업에서 확정하며 현재 녹화 등록 계약에는 `429` 응답을 포함하지 않는다.

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
