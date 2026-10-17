FROM node:24-bookworm-slim AS ui
WORKDIR /ui
COPY agent-frontend/package.json agent-frontend/package-lock.json ./
RUN npm ci
COPY agent-frontend/ ./
RUN npm run build

FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY agent-backend/pom.xml pom.xml
COPY agent-backend/src src
COPY --from=ui /ui/dist/agent-frontend/browser/ src/main/resources/static/
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/agent-backend-0.1.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
