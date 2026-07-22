# EyesOnU

A204 GitLab 프로젝트입니다.

## 환경 프로필

Spring Boot 애플리케이션은 `local`, `test`, `prod` 중 정확히 하나의 프로필로 실행해야 합니다. 프로필을 생략하거나 여러 환경 프로필을 동시에 활성화하면 시작하지 않습니다.

| 프로필 | 용도 | 외부 인프라 |
| --- | --- | --- |
| `local` | IntelliJ 로컬 개발 | Docker Compose의 MySQL·RabbitMQ·MinIO |
| `test` | 컨텍스트·단위 테스트 | 기본적으로 연결하지 않으며 향후 Testcontainers가 설정을 덮어씀 |
| `prod` | 운영 배포 | 환경변수로 전달된 관리형 서비스 |

설정 파일은 `application.yaml`과 프로필별 `application-{profile}.yaml`로 관리합니다. 실제 비밀번호와 액세스 키는 설정 파일에 기록하지 않으며, `test` 프로필에만 외부 서비스에 사용하지 않는 가상 기본값을 둡니다.

## 로컬 개발 환경

Spring Boot는 IntelliJ IDEA에서 Java 21로 실행하고, MySQL·RabbitMQ·MinIO는 Docker Compose로 실행합니다.

### 사전 준비

- Java 21
- IntelliJ IDEA
- Docker Desktop(WSL2 기반 Linux 컨테이너)
- Docker Compose v2

현재 MinIO 커뮤니티 이미지는 아카이브되어 있으므로 Compose에 고정된 이미지는 로컬 개발 용도로만 사용합니다. 운영 환경에서는 AWS S3 등 관리형 객체 저장소를 사용해야 합니다.

### 최초 실행

PowerShell에서 저장소 루트를 기준으로 실행합니다.

```powershell
Copy-Item infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/compose.local.yml up -d --wait
docker compose --env-file infra/.env -f infra/compose.local.yml ps -a
```

`minio-init`은 MinIO가 준비된 뒤 다음 작업을 수행하고 종료 코드 `0`으로 끝납니다.

- `eyesonu-media` 비공개 버킷 생성
- Spring Boot용 S3 사용자 생성 또는 비밀번호 갱신
- 해당 버킷의 객체 조회·업로드·삭제·multipart 작업만 허용

### 서비스 접속 정보

| 서비스 | 주소 | 용도 |
| --- | --- | --- |
| MySQL | `localhost:3307` | 애플리케이션 데이터베이스 |
| RabbitMQ | `localhost:5672` | AMQP 연결 |
| RabbitMQ Management | `http://localhost:15672` | 큐 관리 UI |
| MinIO S3 API | `http://localhost:9000` | S3 호환 API |
| MinIO Console | `http://localhost:9001` | 객체·버킷 관리 UI |

모든 포트는 `127.0.0.1`에만 바인딩되어 로컬 컴퓨터 밖에서는 접근할 수 없습니다.

MinIO Console은 `MINIO_ROOT_USER`와 `MINIO_ROOT_PASSWORD`를 사용합니다. Spring Boot는 관리자 계정 대신 `S3_ACCESS_KEY`와 `S3_SECRET_KEY`를 사용합니다.

### IntelliJ local 실행 설정

`Run > Edit Configurations > Environment variables`에 `infra/.env`의 다음 값을 입력합니다. IntelliJ는 Compose의 `.env` 파일을 Spring Boot 프로세스에 자동으로 전달하지 않습니다.

```text
SPRING_PROFILES_ACTIVE=local
DB_URL
DB_USERNAME
DB_PASSWORD
SPRING_RABBITMQ_HOST
SPRING_RABBITMQ_PORT
SPRING_RABBITMQ_USERNAME
SPRING_RABBITMQ_PASSWORD
SPRING_RABBITMQ_VIRTUAL_HOST
S3_ENDPOINT
S3_REGION
S3_BUCKET
S3_PATH_STYLE_ACCESS
S3_ACCESS_KEY
S3_SECRET_KEY
```

로컬 MinIO는 path-style access를 사용하며 애플리케이션 사용자는 `eyesonu-media` 이외의 버킷에 접근할 수 없습니다.

### 테스트 프로필

테스트는 자동으로 `test` 프로필을 활성화합니다.

```powershell
Set-Location apps/backend-api/eyesonu
.\mvnw.cmd test
```

`application-test.yaml`은 Flyway와 RabbitMQ listener 자동 시작을 비활성화합니다. Testcontainers 도입 시 `TEST_DB_*`, `TEST_RABBITMQ_*`, `TEST_S3_*` 환경변수로 기본값을 덮어씁니다.

### 운영 프로필

운영 환경은 `SPRING_PROFILES_ACTIVE=prod`와 다음 값을 외부 Secret 또는 배포 환경변수로 제공해야 합니다.

- `DB_URL`, `DB_USERNAME`, `DB_PASSWORD`
- `SPRING_RABBITMQ_HOST`, `SPRING_RABBITMQ_PORT`, `SPRING_RABBITMQ_USERNAME`, `SPRING_RABBITMQ_PASSWORD`, `SPRING_RABBITMQ_VIRTUAL_HOST`
- `S3_REGION`, `S3_BUCKET`

AWS IAM Role을 사용하면 `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_ENDPOINT`를 생략합니다. 정적 S3 키를 사용할 때는 access key와 secret key를 반드시 함께 제공합니다. 운영 프로필에서는 Swagger UI가 비활성화됩니다.

### 종료와 초기화

```powershell
# 컨테이너만 종료하고 데이터는 보존
docker compose --env-file infra/.env -f infra/compose.local.yml down

# 로그 확인
docker compose --env-file infra/.env -f infra/compose.local.yml logs -f

# 컨테이너와 로컬 개발 데이터를 모두 삭제
docker compose --env-file infra/.env -f infra/compose.local.yml down -v
```

`down -v`는 MySQL, RabbitMQ, MinIO의 로컬 데이터를 복구할 수 없게 삭제하므로 초기화가 필요한 경우에만 실행합니다.
