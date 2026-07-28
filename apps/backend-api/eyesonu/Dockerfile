FROM eclipse-temurin:21-jdk-alpine

WORKDIR /app

RUN addgroup -S app && adduser -S app -G app
COPY --chown=app:app target/*.jar app.jar

USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
