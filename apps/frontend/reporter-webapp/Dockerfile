# 1단계: Node.js 환경에서 프론트엔드 프로젝트 빌드 (dist 폴더 생성)
FROM node:18-alpine as build-stage
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# 2단계: 가벼운 Nginx 웹 서버를 통해 빌드된 정적 파일 배포
FROM nginx:stable-alpine as production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]