# Recording analysis image upload contract

The recording AI Worker sends analysis details to the backend API and uploads
the generated frame and crop images directly to MinIO through presigned PUT URLs.
The backend issues those URLs after the Worker claims the analysis job.

## 1. Claim the job

```http
POST /api/v1/internal/recording-analysis-jobs/{jobId}/claim
X-Worker-Key: <worker-key>
```

The response contains the current `attempt`. The Worker must use that attempt
when uploading images and submitting the result.

## 2. Read the analysis target

The Worker reads the recording source and appearance target through the backend
after claiming the job:

```http
GET /api/v1/internal/recording-analysis-jobs/{jobId}/target
X-Worker-Key: <worker-key>
```

The response includes the recording object key, canonical appearance prompts,
search time and area, camera information, and the current attempt. The Worker
must use this response instead of receiving appearance prompts through RabbitMQ.

```json
{
  "jobId": 42,
  "caseId": 7,
  "recordingId": 15,
  "cameraId": 3,
  "cameraCode": "CAM-003",
  "cameraName": "Front",
  "recordingObjectKey": "recordings/CAM-003/2026/08/03/video.mp4",
  "prompt": "a man wearing a black short sleeve top and black pants",
  "exclusionPrompt": null,
  "searchStart": "2026-08-03T00:00:00Z",
  "searchEnd": "2026-08-03T00:30:00Z",
  "searchArea": "front gate",
  "attempt": 1
}
```

## 3. Request image upload URLs

```http
POST /api/v1/internal/recording-analysis-jobs/{jobId}/upload-urls
X-Worker-Key: <worker-key>
Content-Type: application/json
```

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

Only the Worker that currently owns the job lease can request URLs. The
backend derives the attempt from the job and creates the object keys. The
response has one frame URL and one crop URL per track:

```json
{
  "attempt": 1,
  "candidates": [
    {
      "trackId": "track-17",
      "frame": {
        "objectKey": "analysis/analysis-42/attempt-1/frames/<sha256>.jpg",
        "uploadUrl": "https://minio.example/...",
        "contentType": "image/jpeg"
      },
      "crop": {
        "objectKey": "analysis/analysis-42/attempt-1/crops/<sha256>.png",
        "uploadUrl": "https://minio.example/...",
        "contentType": "image/png"
      }
    }
  ],
  "expiresInSeconds": 900
}
```

The Worker uploads only the image bytes to each URL. It must use the returned
`contentType` and retry the URL request if the URL expires.

## 4. Submit the analysis details

After every image upload succeeds, submit the result using the returned object
keys:

```http
POST /api/v1/internal/recording-analysis-jobs/{jobId}/result
X-Worker-Key: <worker-key>
Content-Type: application/json
```

The result request contains `detectedAt`, `similarity`, `boundingBox`,
`frameObjectKey`, and `cropObjectKey`. The backend verifies that both objects
belong to the current job attempt and validates their size, MIME type, and
JPEG/PNG signature before persisting the detailed candidate data.
