# 미디어 서버 Device Key 운영

미디어 서버는 중앙 서버의 다음 경로를 호출할 때 `X-Device-Key` 헤더로 인증한다.

- `/api/v1/device/cameras/**`
- `/api/v1/device/recordings/**`

Device Key 형식은 `msk_<16자리 keyId>.<64자리 secret>`이다. 키 원문은 중앙 DB에 저장하지 않고,
`keyId`와 BCrypt cost 12로 인코딩한 secret만 저장한다.

## 1. 스키마 적용

백엔드를 실행해 Flyway V2 마이그레이션을 먼저 적용한다. V2는 `media_servers` 테이블을 생성하고
`cameras`를 `media_server_id`로 연결한다.

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

## 4. 비활성화와 교체

키를 폐기할 때는 해당 `media_servers.status`를 `DISABLED`로 바꾼다. 비활성 서버의 요청은
`401 INVALID_DEVICE_KEY`로 거부된다.

현재는 미디어 서버당 활성 키 하나만 지원하므로 무중단 키 교체를 지원하지 않는다. 교체 시 새 키와
해시를 준비하고 DB와 라즈베리파이 설정을 계획된 점검 시간에 함께 변경한다.
