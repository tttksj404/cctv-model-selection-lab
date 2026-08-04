FROM maven:3.9.11-eclipse-temurin-21-alpine AS build

WORKDIR /workspace

COPY pom.xml ./
RUN mvn -B -DskipTests dependency:go-offline

COPY src ./src
RUN mvn -B -DskipTests package \
    && app_jar="$(find target -maxdepth 1 -type f -name '*.jar' ! -name '*.jar.original' -print -quit)" \
    && test -n "$app_jar" \
    && cp "$app_jar" /tmp/app.jar

FROM eclipse-temurin:21-jdk-alpine

WORKDIR /app

RUN addgroup -S app && adduser -S app -G app
RUN apk add --no-cache wget
COPY --from=build --chown=app:app /tmp/app.jar app.jar

USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
