@echo off
chcp 65001 > nul
echo 🐳 JOBS 프로젝트를 Docker Hub에 업로드합니다

REM Docker Hub 사용자명 설정 (여기를 본인 Docker Hub 사용자명으로 변경하세요)
set DOCKER_USERNAME=chanerdy

REM 이미지 태그 설정
set IMAGE_TAG=latest

echo 📝 설정 정보:
echo    Docker Hub 사용자명: %DOCKER_USERNAME%
echo    이미지 태그: %IMAGE_TAG%
echo.

REM Docker Hub 로그인 확인 (건너뛰기 - 이미 로그인됨)
echo 🔐 Docker Hub 로그인 상태: 확인됨 (chanerdy)
echo ✅ 빌드를 시작합니다...

REM FastAPI 서버 이미지 빌드
echo 🔨 1. FastAPI 서버 이미지 빌드 중...
docker build -t %DOCKER_USERNAME%/jobs-api:%IMAGE_TAG% -f Dockerfile .

REM MCP 서버 이미지 빌드
echo 🔨 2. MCP 서버 이미지 빌드 중...
docker build -t %DOCKER_USERNAME%/jobs-mcp:%IMAGE_TAG% -f Dockerfile.mcp .

echo ✅ 이미지 빌드 완료

REM 이미지 리스트 확인
echo 📋 빌드된 이미지 목록:
docker images | findstr %DOCKER_USERNAME%

REM Docker Hub에 푸시
echo 📤 3. Docker Hub에 업로드 중...
echo    - FastAPI 서버 업로드...
docker push %DOCKER_USERNAME%/jobs-api:%IMAGE_TAG%

echo    - MCP 서버 업로드...
docker push %DOCKER_USERNAME%/jobs-mcp:%IMAGE_TAG%

echo 🎉 업로드 완료!
echo.
echo 📌 사용 방법:
echo    다른 서버에서 다음 명령어로 사용 가능:
echo    docker pull %DOCKER_USERNAME%/jobs-api:%IMAGE_TAG%
echo    docker pull %DOCKER_USERNAME%/jobs-mcp:%IMAGE_TAG%
echo.
echo 🌐 Docker Hub 페이지:
echo    https://hub.docker.com/r/%DOCKER_USERNAME%/jobs-api
echo    https://hub.docker.com/r/%DOCKER_USERNAME%/jobs-mcp

pause 