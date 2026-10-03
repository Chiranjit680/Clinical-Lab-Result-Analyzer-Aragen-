# patientService — Spring Boot 4 on Java 21.
#
# Build context is this directory (patientService/patientService):
#   docker build -t patient-service patientService/patientService

# ---------- build ----------
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build

# Resolve dependencies in their own layer so source edits do not re-download
# the world on every build.
COPY pom.xml .
RUN mvn -B -q dependency:go-offline

COPY src ./src
RUN mvn -B -q clean package -DskipTests

# ---------- runtime ----------
# JRE only: the compiler and Maven are build-time concerns and would roughly
# double the shipped image.
FROM eclipse-temurin:21-jre
WORKDIR /app

COPY --from=build /build/target/identity-service-*.jar app.jar

# Uploaded reports land here.
#
# IMPORTANT: this directory is part of the container filesystem, which is
# ephemeral on most platforms. Every restart or redeploy loses the files while
# the lab_report rows survive in Postgres and keep pointing at them. Mount a
# volume or a persistent disk at this path, or move storage to an object store.
ENV APP_UPLOAD_DIR=/app/uploads

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD bash -c "exec 3<>/dev/tcp/127.0.0.1/${PORT:-8082}" || exit 1

# MaxRAMPercentage so the JVM sizes its heap from the container limit instead
# of the host's memory, which is what makes containers get OOM-killed.
# --server.port picks up the platform's injected PORT, falling back to the
# 8082 that application.yml uses locally.
CMD ["sh", "-c", "exec java -XX:MaxRAMPercentage=75.0 -jar app.jar --server.port=${PORT:-8082}"]
