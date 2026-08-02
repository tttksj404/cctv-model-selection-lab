# EyesOnU

A204 팀의 EyesOnU 프로젝트입니다. 현재 로컬 개발 환경은 Spring Boot 백엔드와 Docker Compose로 실행하는 MySQL, RabbitMQ, MinIO로 구성됩니다.

> Camera와 Jetson 모듈의 실행 환경은 준비 중이며, 설정이 확정되면 각 모듈의 README에 추가합니다.

## 1. 필수 프로그램

| 프로그램 | 용도 |
| --- | --- |
| Git | 저장소 관리 |
| Java 21 JDK | Spring Boot 빌드 및 실행 |
| Docker Desktop | 로컬 MySQL, RabbitMQ, MinIO 실행 |
| Docker Compose v2 | 로컬 컨테이너 구성 실행 |

- Windows에서는 Docker Desktop의 WSL2 기반 Linux 컨테이너를 사용합니다.
- Maven은 프로젝트에 포함된 Maven Wrapper를 사용하므로 별도로 설치하지 않아도 됩니다.
- IntelliJ IDEA와 VS Code 중 원하는 IDE를 선택해서 사용할 수 있습니다.

설치 확인:

```powershell
git --version
java -version
docker --version
docker compose version
```

`java -version`에는 21 버전이 표시되어야 합니다.

## 2. 최초 실행

저장소를 받은 뒤 PowerShell에서 저장소 루트로 이동해 실행합니다.

### 환경변수 파일 생성

```powershell
Copy-Item infra/.env.example infra/.env
```

`infra/.env`는 로컬 개발용 설정이며 Git에 커밋하지 않습니다. 공유가 필요한 기본값은 `infra/.env.example`만 수정합니다.
`.idea`, `.vscode` 같은 개인 IDE 설정도 커밋하지 않습니다.

### 로컬 인프라 실행

Docker Desktop을 실행한 뒤 다음 명령을 입력합니다.

```powershell
docker compose --env-file infra/.env -f infra/compose.local.yml up -d --wait
docker compose --env-file infra/.env -f infra/compose.local.yml ps -a
```

`mysql`, `rabbitmq`, `minio`가 정상 상태이고 `minio-init`이 종료 코드 `0`으로 끝나면 준비가 완료된 것입니다.

| 서비스 | 주소 | 용도 |
| --- | --- | --- |
| MySQL 8.0.46 | `localhost:3307` | 애플리케이션 데이터베이스 |
| RabbitMQ | `localhost:5672` | AMQP 연결 |
| RabbitMQ Management | `http://localhost:15672` | 큐 관리 UI |
| MinIO S3 API | `http://localhost:9000` | S3 호환 API |
| MinIO Console | `http://localhost:9001` | 버킷 및 객체 관리 UI |

관리 화면의 계정 정보는 `infra/.env`에서 확인합니다. 모든 서비스 포트는 로컬 컴퓨터에서만 접근할 수 있도록 바인딩되어 있습니다.

## 3. IntelliJ IDEA 설정

IntelliJ IDEA는 선택 사항입니다.

1. `File > Open`에서 `apps/backend-api/eyesonu/pom.xml`을 선택하고 Maven 프로젝트로 엽니다.
2. `File > Project Structure > Project`에서 Project SDK를 Java 21로 설정합니다.
3. `Settings > Build, Execution, Deployment > Build Tools > Maven`에서 Maven Wrapper를 사용하도록 설정합니다.
4. 같은 메뉴의 `Maven > Runner`에서 JRE를 Java 21로 설정합니다.
5. `Settings > Plugins`에서 Lombok 플러그인을 설치합니다.
6. `Settings > Build, Execution, Deployment > Compiler > Annotation Processors`에서 `Enable annotation processing`이 활성화되어 있는지 확인합니다.

### 실행 구성

`Run > Edit Configurations`에서 Spring Boot 또는 Application 실행 구성을 만들고 다음 값을 입력합니다.

| 항목 | 값 |
| --- | --- |
| Main class | `com.ssafy.eyesonu.EyesonuApplication` |
| Active profiles | `local` |
| Working directory | 저장소의 `apps/backend-api/eyesonu` 절대 경로 |
| Environment file | 저장소의 `infra/.env` 절대 경로 |

IntelliJ 버전에 따라 Environment file 항목이 없다면 Environment variables 편집 화면에서 `infra/.env`의 다음 항목을 직접 등록합니다.

```text
SPRING_PROFILES_ACTIVE=local
DB_URL
DB_USERNAME
DB_PASSWORD
AUTH_RATE_LIMIT_KEY_SECRET
ADMIN_BOOTSTRAP_LOGIN_ID
ADMIN_BOOTSTRAP_PASSWORD
ADMIN_BOOTSTRAP_NAME
SPRING_RABBITMQ_HOST
SPRING_RABBITMQ_PORT
SPRING_RABBITMQ_USERNAME
SPRING_RABBITMQ_PASSWORD
SPRING_RABBITMQ_VIRTUAL_HOST
S3_ENDPOINT
S3_PUBLIC_ENDPOINT
S3_REGION
S3_BUCKET
S3_PATH_STYLE_ACCESS
S3_ACCESS_KEY
S3_SECRET_KEY
RECORDING_MAX_FILE_SIZE_BYTES
S3_CONNECT_TIMEOUT
S3_READ_TIMEOUT
S3_CALL_TIMEOUT
S3_PRESIGNED_URL_EXPIRY
```

Docker 인프라가 실행 중인지 확인한 후 `EyesonuApplication`을 실행합니다.

## 4. VS Code 설정

VS Code도 선택 사항입니다.

1. VS Code에서 `apps/backend-api/eyesonu` 폴더를 엽니다.
2. 다음 확장을 설치합니다.
   - [Extension Pack for Java](https://marketplace.visualstudio.com/items?itemName=vscjava.vscode-java-pack)
   - [Spring Boot Extension Pack](https://marketplace.visualstudio.com/items?itemName=vmware.vscode-boot-dev-pack)
3. 명령 팔레트(`Ctrl+Shift+P`)에서 `Java: Configure Java Runtime`을 실행하고 프로젝트 JDK가 Java 21인지 확인합니다.
4. Java 프로젝트 가져오기와 Maven 의존성 로딩이 끝날 때까지 기다립니다.

Extension Pack for Java에 Lombok 지원이 포함되어 있으므로 별도의 Lombok 확장은 필요하지 않습니다.

### 실행 구성

열어 둔 `apps/backend-api/eyesonu` 폴더 아래에 `.vscode/launch.json`을 만들고 다음 내용을 입력합니다. `.vscode`는 개인 IDE 설정이므로 Git에 커밋되지 않습니다.

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "java",
      "name": "EyesOnU (local)",
      "request": "launch",
      "mainClass": "com.ssafy.eyesonu.EyesonuApplication",
      "projectName": "eyesonu",
      "cwd": "${workspaceFolder}",
      "envFile": "${workspaceFolder}/../../../infra/.env"
    }
  ]
}
```

Docker 인프라가 실행 중인지 확인한 후 `F5`를 누르거나 Spring Boot Dashboard에서 애플리케이션을 실행합니다.

### 관리자 세션 인증

- 최초 실행 시 `infra/.env`의 `ADMIN_BOOTSTRAP_*` 값으로 `SUPER_ADMIN` 계정 하나를 생성합니다. 이미 관리자가 있으면 이 값으로 계정을 덮어쓰지 않습니다.
- `SUPER_ADMIN`은 관리자 계정 목록 조회, 일반 `ADMIN` 계정 생성 및 활성화·비활성화를 수행할 수 있습니다. 새 계정은 항상 `ADMIN` 권한으로 생성됩니다.
- 브라우저 클라이언트는 로그인 전에 `GET /api/v1/auth/csrf`를 호출하고 `XSRF-TOKEN` 쿠키 값을 `X-XSRF-TOKEN` 헤더로 보냅니다.
- 로그인 후 JWT를 저장하지 않습니다. `EYESONU_SESSION`은 `HttpOnly` 쿠키이며 브라우저가 자동으로 전송합니다.
- 로그인 성공과 로그아웃 후에는 CSRF 발급 API를 다시 호출합니다.
- 운영에서는 관리자 웹과 `/api`를 동일 Origin으로 프록시하고 백엔드 8080 포트를 외부에 직접 공개하지 않습니다.

## 5. 테스트

PowerShell에서 다음 명령을 실행합니다. 테스트는 자동으로 `test` 프로필을 사용합니다.

```powershell
Set-Location apps/backend-api/eyesonu
.\mvnw.cmd test
```

IDE에서도 `src/test` 아래의 테스트 클래스 또는 메서드를 직접 실행할 수 있습니다.

## 6. GitLab CI와 Jenkins CD 경계

GitLab CI는 Merge Request의 빌드와 테스트만 담당합니다. Jenkins는 `dev` 또는 `master`에 반영된 커밋을 감지하고 해당 커밋을 직접 checkout하여 Docker 이미지를 빌드하고 서버에 배포합니다.

### 파이프라인 실행 정책

- Merge Request에서 백엔드가 변경되면 Maven 빌드와 일반 테스트를 실행합니다.
- Merge Request에서 관리자 대시보드가 변경되면 `npm ci`와 Vite 빌드를 실행합니다.
- `.gitlab-ci.yml`이 변경되면 백엔드와 관리자 대시보드를 모두 검증합니다.
- 문서나 인프라 파일만 변경되면 경량 파이프라인 정보 작업만 실행합니다.
- 소스와 패키지 매니페스트가 아직 없는 `apps/frontend/reporter-webapp`은 CI 대상에서 제외합니다.
- `dev`와 `master` push에서는 GitLab CI 파이프라인을 생성하지 않습니다.

### Jenkins 연동 규칙

GitLab CI는 Jenkins를 호출하거나 JAR, `dist/`, Docker 이미지를 전달하지 않습니다. Jenkins는 `dev` 또는 `master`에 병합된 커밋 SHA를 checkout한 뒤 그 소스로 Docker 이미지를 빌드하고 배포합니다. `infra/Jenkinsfile` 수정과 실제 배포 구성은 Jenkins 담당자의 작업 범위입니다.

### GitLab Runner 요구 사항

- 태그 없는 일반 Linux Docker executor를 사용하고 `Run untagged jobs`를 활성화합니다.
- Docker-in-Docker와 privileged 모드는 필요하지 않습니다. Docker를 사용할 수 없는 Runner에서는 현재 설정에 따라 MySQL Testcontainers 통합 테스트가 생략될 수 있습니다.
- 프로젝트의 Merge checks에서 `Pipelines must succeed`를 활성화해야 실패하거나 실행 중인 파이프라인의 Merge Request를 병합할 수 없습니다.
- Container Registry와 Registry 인증 변수는 GitLab CI에서 사용하지 않습니다.

## 7. 종료와 초기화

저장소 루트에서 실행합니다.

```powershell
# 컨테이너 종료, 데이터 보존
docker compose --env-file infra/.env -f infra/compose.local.yml down

# 로그 확인
docker compose --env-file infra/.env -f infra/compose.local.yml logs -f

# 컨테이너와 로컬 데이터 전체 삭제
docker compose --env-file infra/.env -f infra/compose.local.yml down -v
```

> `down -v`는 MySQL, RabbitMQ, MinIO의 로컬 데이터를 복구할 수 없게 삭제합니다. 초기화가 필요한 경우에만 사용하세요.

### MySQL 8.4 데이터가 남아 있는 경우

로컬 Compose는 MySQL 8.0.46을 사용합니다. MySQL 8.4에서 생성한 `mysql_data` 볼륨을 MySQL 8.0.46 컨테이너에 직접 연결하지 마세요. MySQL은 데이터 디렉터리를 이전 버전에서 직접 여는 다운그레이드를 지원하지 않습니다.

- 기존 데이터가 필요하면 MySQL 8.4에서 논리 백업한 뒤 새 MySQL 8.0.46 볼륨으로 복원합니다.
- 기존 데이터가 불필요하고 RabbitMQ와 MinIO 데이터도 함께 삭제해도 되는 경우에만 위의 `down -v` 명령으로 로컬 인프라를 초기화합니다.

## 8. 문제 해결

- `docker` 명령을 찾지 못하면 Docker Desktop이 설치 및 실행 중인지 확인한 뒤 PowerShell을 다시 엽니다.
- `3307`, `5672`, `15672`, `9000`, `9001` 포트를 이미 사용 중이면 해당 프로그램을 종료하거나 `infra/.env`의 로컬 포트를 변경합니다.
- 애플리케이션이 프로필 또는 환경변수 오류로 종료되면 `local` 프로필과 `infra/.env` 적용 여부를 확인합니다.
- IntelliJ에서 Lombok 코드가 오류로 표시되면 Lombok 플러그인, Annotation Processing, Maven 새로고침을 확인합니다.
- VS Code가 Maven 프로젝트를 인식하지 못하면 명령 팔레트에서 `Java: Import Java Projects in Workspace`를 실행합니다.

## 환경 프로필

| 프로필 | 용도 | 외부 인프라 |
| --- | --- | --- |
| `local` | 로컬 개발 | Docker Compose의 MySQL, RabbitMQ, MinIO |
| `test` | 자동화 테스트 | 기본적으로 외부 서비스에 연결하지 않음 |
| `prod` | 운영 배포 | 배포 환경변수로 전달된 관리형 서비스 |

Spring Boot 애플리케이션은 세 프로필 중 정확히 하나로 실행해야 합니다. 실제 비밀번호와 액세스 키는 설정 파일이나 IDE 설정 파일에 기록해 커밋하지 않습니다.
