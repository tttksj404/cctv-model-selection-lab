# 녹화 AI Worker 연동 계약

## 1. 목적과 역할

노트북 AI Worker는 중앙 backend가 등록한 녹화본 분석 작업을 RabbitMQ로 받아 로컬 GPU에서
후보를 탐색하고, evidence frame/crop과 후보 결과를 중앙 서버에 반납한다. RabbitMQ는 작업을
라우팅하는 용도만 가지며 인상착의, 녹화 object key, 카메라 정보, presigned URL, 저장소 자격 증명을
전달하지 않는다.

Backend는 다음을 소유한다.

- 작업·시도(attempt)·lease 상태와 transactional outbox
- Worker Key 인증, claim/target/heartbeat/result/fail API
- MinIO/S3 signed URL 발급과 후보·경로 저장
- RabbitMQ retry/DLQ 토폴로지 선언

Worker는 다음을 소유한다.

- `jobId` claim과 lease heartbeat
- signed URL을 통한 녹화 다운로드와 로컬 AI 추론
- track 단위 evidence frame/crop 업로드
- 멱등 result/fail 반납

## 2. 사전 조건

| 항목 | 요구 사항 |
| --- | --- |
| Backend base URL | 예: `https://api.example.com` |
| Worker Key | 모든 내부 REST 요청의 `X-Worker-Key` |
| RabbitMQ | TLS/AMQPS 또는 VPN/SSH tunnel을 통한 접근 |
| Object storage | Worker는 signed URL만 사용하며 access key/secret은 받지 않음 |
| Worker GPU | 한 프로세스당 `prefetch=1` |

## 3. 작업 흐름

1. 중앙 서버는 녹화 분석 job/outbox를 만들고 routing-only RabbitMQ 이벤트를 발행한다.
2. Worker는 `jobId`로 claim한다.
3. `CLAIMED`일 때만 lease token으로 target을 읽고 녹화본을 분석한다.
4. 긴 다운로드·추론·업로드 중 heartbeat를 보낸다.
5. frame/crop signed PUT URL을 발급받아 object storage에 직접 업로드한다.
6. `/result` 또는 `/fail`이 수락된 뒤에만 delivery를 ACK한다.

## 4. RabbitMQ 계약

| 항목 | 값 |
| --- | --- |
| main exchange | `search.target.exchange` |
| main routing key | `search.target.recording.created` |
| main queue | `search.target.recording.queue` |
| retry exchange | `search.target.recording.retry.exchange` |
| retry queues | `.retry.5s`, `.retry.15s`, `.retry.30s`, `.retry.60s`, `.retry.300s` |
| DLQ | `search.target.recording.dlq` |

```json
{
  "commandId": "01K1...",
  "eventType": "RECORDING_ANALYSIS_JOB_CREATED",
  "jobId": 42,
  "occurredAt": "2026-08-04T00:31:00Z"
}
```

Retry queue마다 `x-message-ttl`을 지정하고 만료 메시지를 main exchange/routing key로
dead-letter한다. Worker는 지연 메시지 publish가 broker confirm된 뒤에만 원 delivery를 ACK한다.
publish confirm 실패 시 원 delivery는 `requeue=true`로 남긴다.

## 5. Claim API와 상태 전이

```http
POST /api/v1/internal/recording-analysis-jobs/{jobId}/claim
X-Worker-Key: <worker-key>
```

```json
{
  "data": {
    "jobId": 42,
    "status": "RUNNING",
    "attempt": 1,
    "disposition": "CLAIMED",
    "startedAt": "2026-08-04T00:31:01Z",
    "claimedBy": "notebook-ai-worker",
    "claimExpiresAt": "2026-08-04T00:36:01Z",
    "leaseToken": "opaque-once-only-token"
  }
}
```

| 응답 | 의미 | Worker 동작 |
| --- | --- | --- |
| `CLAIMED` | 이 Worker가 lease 소유 | 분석 실행 |
| `LEASE_HELD_BY_SELF` | 같은 Worker의 stale delivery가 active lease 소유 | 만료 시점 이후 지연 재발행 |
| `LEASE_HELD_BY_OTHER` | 다른 Worker가 active lease 소유 | 만료 시점 이후 지연 재발행 |
| `RETRY_PENDING` | 경쟁 상태에서 job이 다시 queued | 짧은 지연 재발행 |
| `TERMINAL` | 이미 `SUCCEEDED`/`FAILED`/`CANCELLED` | stale 메시지 ACK |

claim의 이전 `duplicate` 필드는 폐기됐다. Worker는 `LEASE_HELD_BY_SELF`와 `LEASE_HELD_BY_OTHER`를 즉시 ACK하면 안 된다.
그래야 원 Worker 장애 뒤 lease가 만료됐을 때 다른 Worker가 재claim할 수 있다. 두 `LEASE_HELD_*` 상태와
`RETRY_PENDING`은 실패가 아니므로 retry budget을 소비하지 않고 기존 카운터를 보존해 지연 재발행한다.
이전 배포에서 생성된 `claimExpiresAt` 없는 `RUNNING` job은 서버가 `startedAt + worker claim lease`를
응답에 채워 안내하며, `startedAt`까지 비어 있는 깨진 구형 행은 즉시 회수한다. 지연 메시지가
존재하지 않는 상황도 대비해 중앙 서버는 만료 lease를 주기적으로 `QUEUED`로 복구하고 새 outbox를 만든다.

## 6. 오류 및 재처리 규칙

| 상황 | 처리 |
| --- | --- |
| malformed event / jobId 불일치 | `reject(requeue=false)` → DLQ |
| `JOB_NOT_RUNNABLE` stale event | ACK |
| HTTP 4xx | `reject(requeue=false)` → DLQ |
| 네트워크 오류·HTTP 5xx | fixed TTL retry queue에 재발행 |
| `WORKER_LEASE_CONFLICT` | 새 claim을 위해 지연 재시도 |
| retry 횟수 상한 초과 | `reject(requeue=false)` → DLQ |

기본 retry 횟수 상한은 20회다. 4xx를 재큐잉하지 않아 잘못된 Worker Key, 권한, 요청 형식이
큐를 막지 않도록 한다. 상한 초과 delivery가 DLQ로 가도 lease-recovery scheduler가 만료 작업을
다시 outbox화하므로 DB에 `RUNNING` 작업만 영구히 남지 않는다.

## 7. Target, heartbeat, evidence, result

claim 이후 모든 요청에는 `X-Worker-Claim-Token`이 필요하다.

| Method | Path | 용도 |
| --- | --- | --- |
| `GET` | `/{jobId}/target` | prompt, 검색 구간, signed recording GET URL |
| `POST` | `/{jobId}/heartbeat` | active lease 연장 |
| `POST` | `/{jobId}/upload-urls` | 후보 track별 frame/crop signed PUT URL |
| `POST` | `/{jobId}/result` | 후보·evidence 결과 반납 |
| `POST` | `/{jobId}/fail` | 안전한 실패 반납 |

signed recording URL이 만료되어 `401/403`인 경우 Worker는 같은 claimed job의 target을 한 번만
다시 읽어 URL을 갱신한다. 갱신 후에도 실패하면 failure result 또는 오류 분류 규칙을 따른다.

## 8. 배포 순서와 검증

1. 새 retry topology가 없는 동안에는 작업 발행/소비를 잠시 멈춘다.
2. 새 Worker를 먼저 배포한다. 구 이벤트의 확장 필드는 무시할 수 있다.
3. backend를 배포해 routing-only publisher와 fixed TTL retry topology를 선언한 뒤 작업을 재개한다.
4. `recording.analysis.backend-consumer.auto-start=false`를 확인한다.
5. `recording.analysis.lease-recovery.auto-start=true`를 확인한다.
6. 실제 테스트 사건으로 `claim → target → signed GET → inference → signed PUT → result`를 확인한다.
7. 별도로 `LEASE_HELD_BY_SELF`/`LEASE_HELD_BY_OTHER → delay → lease expiry → CLAIMED`, stale terminal ACK, worker 종료 뒤
   lease-recovery outbox 재발행을 확인한다.

세부 schema는 [녹화본 분석 AI Worker 계약](recording-analysis-worker-api.md),
전송 상세는 [RabbitMQ 전송 계약](../ai-worker/docs/RABBITMQ_NOTEBOOK_WORKER_TRANSPORT.md)을 따른다.
