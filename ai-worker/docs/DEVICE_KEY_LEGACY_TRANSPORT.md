# Device Key 기반 구형 dev 녹화 분석 전송

이 문서는 중앙 백엔드 코드를 변경하지 않고 노트북의 `ai-worker`만 연결할 때의 계약이다.

## 적용되는 흐름

구형 dev 이벤트가 녹화 분석 대상 정보를 함께 담아 RabbitMQ로 발행하면 워커는 다음 순서로 동작한다.

1. RabbitMQ 메시지를 `prefetch=1`로 수신한다.
2. `CENTRAL_API_WORKER_KEY`가 `msk_<16자리 hex>.<64자리 hex>` 형식이면 내부 Worker API를 호출하지 않는다.
3. 같은 원문 키를 `X-Device-Key`로 사용해 `/api/v1/device/recording-analysis-jobs/{jobId}/result`에 결과를 제출한다.
4. 메시지의 `recordingObjectKey`를 private MinIO/S3에서 직접 내려받는다.
5. 로컬 SOLIDER+CLIP 런타임을 실행한다.
6. 선택된 frame/crop을 `analysis/analysis-{jobId}/attempt-{attempt}/...`에 업로드한 뒤 후보 이벤트를 제출하고 Rabbit delivery를 ACK한다.

기존 내부 Worker API(`X-Worker-Key`, claim/target/heartbeat/upload-urls/result/fail)는 비-Device 키를 사용하는 배포와의 호환성을 위해 그대로 유지한다. Device Key 이벤트에서는 claim, lease token, 내부 Worker API 호출을 시도하지 않는다.

## 이벤트 계약

Device Key 경로는 다음 구형 enriched 필드를 요구한다.

- `jobId`, `caseId`, `recordingId`, `cameraId`
- `cameraCode`, `cameraName`, `recordingObjectKey`, `prompt`
- 선택: `exclusionPrompt`, `similarityThreshold`, `searchStart`, `searchEnd`, `searchArea`, `searchFromMs`, `searchToMs`, `attempt`

현재 메시지가 `jobId`만 담은 routing-only 이벤트라면 이 경로로는 녹화 대상과 인상착의를 복원할 수 없다. 워커는 이를 내부 Worker API로 몰래 전환하지 않고 DLQ로 보낸다. 그 경우 중앙 발행자가 enriched 이벤트를 발행하거나, 별도 Device 조회 계약을 중앙에서 제공해야 한다.

## 환경 변수

```dotenv
CENTRAL_API_BASE_URL=https://central.example
CENTRAL_API_WORKER_KEY=<raw-device-key>
RABBITMQ_URL=amqps://<user>:<password>@<host>/<vhost>
RABBITMQ_QUEUE=search.target.recording.queue

EYESONU_AI_WORKER_STORAGE_ENDPOINT=https://storage-dev.example
EYESONU_AI_WORKER_STORAGE_BUCKET=eyesonu-media
EYESONU_AI_WORKER_STORAGE_REGION=ap-northeast-2
EYESONU_AI_WORKER_STORAGE_ACCESS_KEY=<minio-app-access-key>
EYESONU_AI_WORKER_STORAGE_SECRET_KEY=<minio-app-secret-key>
EYESONU_AI_WORKER_STORAGE_PATH_STYLE=true
```

MinIO가 private이면 app access key/secret key가 필요하다. 이 자격증명은 중앙 API 요청 헤더에 넣지 않고 S3 SigV4 object 요청에만 사용한다. 키 원문과 secret은 로그·커밋·Rabbit payload에 넣지 않는다.

## 제한 사항

구형 Device 결과 DTO는 `detections`가 비어 있으면 성공 처리할 수 없다. 따라서 영상에서 후보가 0명인 작업을 성공/실패로 종결하는 별도 Device API가 중앙에 없으면 워커는 임의의 빈 성공을 만들지 않고 DLQ로 보낸다. 이 상태를 운영에서 종결하려면 중앙의 기존 계약을 변경하지 않는 범위 밖에서 empty-result/fail 계약을 추가해야 한다.
