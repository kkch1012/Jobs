#!/bin/bash

# EC2 Ubuntu 인스턴스용 JOBS 프로젝트 설치 스크립트
echo "🚀 JOBS 프로젝트 EC2 배포 시작"

# 시스템 업데이트
echo "📦 시스템 업데이트 중..."
sudo apt update && sudo apt upgrade -y

# 필수 패키지 설치
echo "🔧 필수 패키지 설치 중..."
sudo apt install -y curl wget git unzip

# Docker 설치
echo "🐳 Docker 설치 중..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Docker Compose 설치
echo "📦 Docker Compose 설치 중..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 프로젝트 디렉토리 생성
echo "📁 프로젝트 디렉토리 생성..."
mkdir -p ~/jobs-project
cd ~/jobs-project

# 배포 파일들 다운로드 (GitHub 등에서)
echo "📥 배포 파일 다운로드..."
# 여기서는 수동으로 업로드하거나 GitHub에서 clone
echo "배포 파일들을 이 디렉토리에 업로드하세요:"
echo "  - ec2-docker-compose.yml"
echo "  - env.production.example"

# 환경변수 파일 생성 안내
echo "🔐 환경변수 설정이 필요합니다:"
echo "  1. cp env.production.example .env"
echo "  2. nano .env (실제 값들로 편집)"

# 방화벽 설정
echo "🔥 방화벽 설정..."
sudo ufw allow 22      # SSH
sudo ufw allow 8000    # FastAPI
sudo ufw allow 8001    # MCP Server
sudo ufw allow 8080    # pgAdmin (선택사항)
sudo ufw allow 8081    # MongoDB Express (선택사항)
sudo ufw --force enable

# Docker 서비스 시작
echo "▶️ Docker 서비스 시작..."
sudo systemctl enable docker
sudo systemctl start docker

echo "✅ 기본 설치 완료!"
echo ""
echo "다음 단계:"
echo "1. 배포 파일들을 ~/jobs-project 디렉토리에 업로드"
echo "2. 환경변수 설정: cp env.production.example .env && nano .env"
echo "3. 서비스 실행: docker-compose -f ec2-docker-compose.yml up -d"
echo "4. 로그 확인: docker-compose -f ec2-docker-compose.yml logs -f"

# 시스템 재부팅 필요 알림
echo "⚠️ Docker 그룹 권한 적용을 위해 다시 로그인하거나 다음 명령어 실행:"
echo "newgrp docker" 