# MinIO 운영 및 자격증명 교체

이 문서는 백엔드와 미디어 서버가 사용하는 MinIO 운영값을 변경하거나 장애를 복구할 때 따른다. MinIO는 S3 API를 제공하지만 이 프로젝트의 운영 대상은 MinIO 하나로 고정한다.

## 1. 엔드포인트와 환경변수

| 용도 | 환경변수 | 사용 주체 | 규칙 |
| --- | --- | --- | --- |
| 내부 API | `MINIO_INTERNAL_ENDPOINT` | 백엔드 | EC2 내부 네트워크 주소를 사용한다. |
| 공개 URL | `MINIO_PUBLIC_ENDPOINT` | 브라우저용 presigned URL | 외부 클라이언트가 접근할 수 있는 HTTPS 주소를 사용한다. 비워 두지 않는다. |
| API 포트 | `MINIO_API_PORT` | Compose | MinIO API 포트와 보안 그룹 설정을 일치시킨다. |
| 버킷 | `MINIO_BUCKET` | 백엔드·미디어 서버 | 환경별 버킷을 분리하고 버킷명을 배포 로그에 출력하지 않는다. |
| 리전 | `MINIO_REGION_NAME` | 백엔드·MinIO | 애플리케이션과 버킷 정책의 값이 일치해야 한다. |
| 애플리케이션 키 | `MINIO_APP_ACCESS_KEY`, `MINIO_APP_SECRET_KEY` | 백엔드·미디어 서버 | root 계정 대신 최소 권한 애플리케이션 계정을 사용한다. |

운영 배포에서는 `infra/compose.deploy.yml`이 호스트 환경변수를 컨테이너 환경변수로 전달한다. 전환 기간에만 기존 `S3_*` 값의 fallback이 허용되며, 신규 배포 대상은 `MINIO_*` 값을 직접 설정한다.

## 2. 자격증명 교체

서비스 중단을 피하려면 새 키를 먼저 배포하고 기존 키를 나중에 폐기한다.

1. MinIO에서 기존 권한과 동일한 최소 권한의 새 애플리케이션 키를 발급한다.
2. GitLab CI/CD 변수와 EC2 secret store에 새 `MINIO_APP_ACCESS_KEY`·`MINIO_APP_SECRET_KEY`를 등록한다. 값 자체는 저장소와 배포 로그에 남기지 않는다.
3. `MINIO_INTERNAL_ENDPOINT`, `MINIO_PUBLIC_ENDPOINT`, 버킷과 리전이 기존 값과 일치하는지 확인한다.
4. 새 설정으로 배포하고 MinIO health, 기존 객체 `statObject`, presigned URL 다운로드, 미디어 서버 업로드를 순서대로 확인한다.
5. 구버전 컨테이너와 진행 중인 업로드가 사라진 뒤 MinIO에서 기존 키를 폐기한다.
6. 교체 결과와 검증 시각만 운영 기록에 남긴다. 인증 URL, secret, 전체 환경 파일은 기록하지 않는다.

검증이 실패하면 기존 키를 폐기하지 말고 배포를 중단한다. 기존 키가 이미 폐기된 경우에는 새 키를 다시 발급한 뒤 같은 검증 절차를 수행한다.

## 3. 버킷·객체 복구

버킷을 삭제하거나 Compose volume을 제거하기 전에 백업과 복구 가능 여부를 확인한다. `docker compose down -v`는 객체를 지울 수 있으므로 운영 복구 명령으로 사용하지 않는다.

1. 백엔드의 `MINIO_INTERNAL_ENDPOINT`, `MINIO_BUCKET`, 리전, 애플리케이션 키를 확인한다.
2. MinIO health endpoint와 버킷 존재 여부를 확인한다.
3. 버킷이 없으면 운영 승인 후 동일한 이름으로 생성하고 private 정책을 적용한다.
4. 백업에서 객체를 복구한 뒤 대표적인 사건 사진, 녹화 파일, 후보 crop 객체를 `statObject`로 확인한다.
5. 백엔드에서 사진·녹화·후보 조회를 수행하고 presigned URL이 `MINIO_PUBLIC_ENDPOINT`로 발급되는지 확인한다.
6. 미디어 서버에서 테스트 객체를 업로드하고 녹화 메타데이터 등록 API가 실제 크기를 읽는지 확인한 뒤 테스트 객체를 삭제한다.

MinIO 정책 문서의 `s3:GetObject`, `s3:PutObject` 같은 action 이름과 `arn:aws:s3:::...` 형식의 ARN은 S3 API 호환 정책 문법이므로 MinIO에서도 그대로 유지한다. 저장소를 MinIO 전용으로 운영한다는 이유로 정책 문법을 임의로 바꾸지 않는다.

## 4. 환경변수 전환 완료 후 정리

모든 배포 대상이 `MINIO_*` 계열로 전환되고 구버전 컨테이너가 종료된 것을 확인한 다음 `infra/compose.deploy.yml`의 `S3_*` fallback을 별도 변경으로 제거한다. 제거 후에는 새 환경변수만으로 `docker compose config`와 실제 배포 검증을 다시 수행한다.
