#!/bin/bash

# Docker Hub 업로드 스크립트
echo "🐳 JOBS 프로젝트를 Docker Hub에 업로드합니다"

# Docker Hub 사용자명 설정 (여기를 본인 Docker Hub 사용자명으로 변경하세요)
DOCKER_USERNAME="your-docker-username"

# 이미지 태그 설정
IMAGE_TAG="latest"

echo "📝 설정 정보:"
echo "   Docker Hub 사용자명: $DOCKER_USERNAME"
echo "   이미지 태그: $IMAGE_TAG"
echo ""

# Docker Hub 로그인 확인
echo "🔐 Docker Hub 로그인 확인..."
if ! docker info | grep -q "Username"; then
    echo "❌ Docker Hub에 로그인하지 않았습니다."
    echo "다음 명령어로 로그인하세요: docker login"
    exit 1
fi

echo "✅ Docker Hub 로그인 확인 완료"

# FastAPI 서버 이미지 빌드
echo "🔨 1. FastAPI 서버 이미지 빌드 중..."
docker build -t $DOCKER_USERNAME/jobs-api:$IMAGE_TAG -f Dockerfile .

# MCP 서버 이미지 빌드
echo "🔨 2. MCP 서버 이미지 빌드 중..."
docker build -t $DOCKER_USERNAME/jobs-mcp:$IMAGE_TAG -f Dockerfile.mcp .

echo "✅ 이미지 빌드 완료"

# 이미지 리스트 확인
echo "📋 빌드된 이미지 목록:"
docker images | grep $DOCKER_USERNAME

# Docker Hub에 푸시
echo "📤 3. Docker Hub에 업로드 중..."
echo "   - FastAPI 서버 업로드..."
docker push $DOCKER_USERNAME/jobs-api:$IMAGE_TAG

echo "   - MCP 서버 업로드..."
docker push $DOCKER_USERNAME/jobs-mcp:$IMAGE_TAG

echo "🎉 업로드 완료!"
echo ""
echo "📌 사용 방법:"
echo "   다른 서버에서 다음 명령어로 사용 가능:"
echo "   docker pull $DOCKER_USERNAME/jobs-api:$IMAGE_TAG"
echo "   docker pull $DOCKER_USERNAME/jobs-mcp:$IMAGE_TAG"
echo ""
echo "🌐 Docker Hub 페이지:"
echo "   https://hub.docker.com/r/$DOCKER_USERNAME/jobs-api"
echo "   https://hub.docker.com/r/$DOCKER_USERNAME/jobs-mcp" 