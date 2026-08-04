# 녹화본 분석 evidence 업로드 계약

AI Worker는 로컬에서 생성한 frame/crop 파일의 바이트만 MinIO/S3에 직접 올린다. 저장소 키와
presigned URL은 중앙 서버가 발급하며, Worker는 임의의 object key나 로컬 경로를 중앙 서버에
보내지 않는다.

## 1. 업로드 URL 요청

```http
POST /api/v1/internal/recording-analysis-jobs/{jobId}/upload-urls
X-Worker-Key: <worker-key>
X-Worker-Claim-Token: <lease-token>
Content-Type: application/json
```

요청마다 최대 100개의 고유한 `trackId`를 보낼 수 있다. 현재 로컬 runtime도 track 단위로 최대
100개를 내보내며, 이후 상한을 늘릴 경우 Worker는 100개 단위로 분할 요청한다.

```json
{
  "candidates": [
    {
      "trackId": "track-17",
      "frameContentType": "image/jpeg",
      "cropContentType": "image/png"
    }
  ]
}
```

응답 예시:

```json
{
  "attempt": 1,
  "candidates": [
    {
      "trackId": "track-17",
      "frame": {
        "objectKey": "analysis/analysis-42/attempt-1/frames/<sha256>.jpg",
        "uploadUrl": "https://minio.example/presigned-put-frame",
        "contentType": "image/jpeg"
      },
      "crop": {
        "objectKey": "analysis/analysis-42/attempt-1/crops/<sha256>.png",
        "uploadUrl": "https://minio.example/presigned-put-crop",
        "contentType": "image/png"
      }
    }
  ],
  "expiresInSeconds": 900
}
```

응답의 `trackId` 집합은 요청 집합과 정확히 같아야 한다. 누락, 중복, 다른 track이 있으면
Worker는 결과를 제출하지 않고 `/fail` 또는 requeue 절차로 처리한다.

## 2. MinIO/S3 직접 PUT

`frame.uploadUrl`과 `crop.uploadUrl`에는 응답의 `contentType`으로 이미지 바이트를 PUT한다.

```http
PUT <presigned-upload-url>
Content-Type: image/jpeg

<image bytes>
```

이 요청에는 `X-Worker-Key`나 `X-Worker-Claim-Token`을 붙이지 않는다. 중앙 서버의 인증 정보는
저장소에 전달하지 않으며, URL에 포함된 서명만 사용한다. Worker는 빈 파일, 설정된 최대 크기 초과,
HTTP 2xx 이외 응답을 실패로 처리한다.

## 3. 분석 결과 제출

frame/crop가 모두 업로드된 뒤에만 결과를 제출한다.

```http
POST /api/v1/internal/recording-analysis-jobs/{jobId}/result
X-Worker-Key: <worker-key>
X-Worker-Claim-Token: <lease-token>
Content-Type: application/json
```

```json
{
  "resultId": "notebook-a:42:1",
  "candidates": [
    {
      "trackId": "track-17",
      "detectedAt": "2026-08-03T09:10:11.123456+09:00",
      "similarity": 0.91,
      "frameObjectKey": "analysis/analysis-42/attempt-1/frames/<sha256>.jpg",
      "cropObjectKey": "analysis/analysis-42/attempt-1/crops/<sha256>.png",
      "boundingBox": { "x": 120, "y": 80, "width": 90, "height": 210 }
    }
  ]
}
```

백엔드는 두 object key가 현재 `jobId`/`attempt` namespace에 속하고, 파일 크기·MIME type·JPEG/PNG
signature가 유효한지 확인한 후 candidate event를 저장한다. 하나라도 검증에 실패하면 결과는
성공 처리되지 않는다.

## 재시도 규칙

- URL 만료나 일시적 저장소 오류: 유효 lease 안에서 `/upload-urls`를 다시 요청한 뒤 재업로드한다.
- `WORKER_LEASE_CONFLICT`: 현재 Worker는 더 이상 소유자가 아니므로 result/fail을 제출하지 않고
  RabbitMQ delivery를 requeue한다.
- terminal callback 응답을 잃은 경우: 동일 `resultId`와 동일 payload로 다시 제출하면 백엔드가
  idempotent하게 `duplicate: true`를 반환한다.
