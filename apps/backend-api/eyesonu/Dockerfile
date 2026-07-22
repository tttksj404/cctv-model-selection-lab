# 1. 자바 21 버전을 기반으로 실행합니다. 
FROM eclipse-temurin:21-jdk-alpine

# 2. 컨테이너 내부의 작업 폴더를 지정합니다.
WORKDIR /app

# 3. 젠킨스가 방금 빌드한 jar 파일을 컨테이너 내부로 복사합니다.
COPY target/*.jar app.jar

# 4. 서버가 시작될 때 실행할 명령어를 지정합니다.
ENTRYPOINT ["java", "-jar", "app.jar"]