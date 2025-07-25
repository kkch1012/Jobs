#!/bin/bash

# Docker 실행 스크립트
echo "🐳 JOBS 프로젝트 Docker 컨테이너 시작"

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo "❌ .env 파일이 없습니다."
    echo "📝 env.example 파일을 복사하여 .env 파일을 생성하고 설정을 입력하세요."
    echo "   cp env.example .env"
    echo "   nano .env  # 또는 다른 에디터로 편집"
    exit 1
fi

# Docker와 Docker Compose 설치 확인
if ! command -v docker &> /dev/null; then
    echo "❌ Docker가 설치되지 않았습니다."
    echo "📥 https://docs.docker.com/get-docker/ 에서 Docker를 설치하세요."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose가 설치되지 않았습니다."
    echo "📥 https://docs.docker.com/compose/install/ 에서 Docker Compose를 설치하세요."
    exit 1
fi

# 실행 모드 선택
echo "실행 모드를 선택하세요:"
echo "1) 전체 서비스 시작 (FastAPI + MCP + DB + Redis + 관리도구)"
echo "2) 애플리케이션만 시작 (FastAPI + MCP + DB + Redis)"
echo "3) 개발 모드 (백그라운드로 실행)"
echo "4) 서비스 중지"
echo "5) 로그 확인"
echo "6) 전체 삭제 (데이터 포함)"

read -p "선택 (1-6): " choice

case $choice in
    1)
        echo "🚀 전체 서비스 시작 중..."
        docker-compose up --build
        ;;
    2)
        echo "🚀 애플리케이션만 시작 중..."
        docker-compose up --build fastapi mcp-server postgres mongo redis
        ;;
    3)
        echo "🚀 개발 모드로 시작 중..."
        docker-compose up --build -d
        echo "✅ 백그라운드에서 실행 중입니다."
        echo "📊 서비스 상태 확인: docker-compose ps"
        echo "📋 로그 확인: docker-compose logs -f"
        ;;
    4)
        echo "🛑 서비스 중지 중..."
        docker-compose down
        echo "✅ 모든 서비스가 중지되었습니다."
        ;;
    5)
        echo "📋 로그 확인 중..."
        docker-compose logs -f
        ;;
    6)
        echo "⚠️  주의: 모든 데이터가 삭제됩니다!"
        read -p "정말 삭제하시겠습니까? (y/N): " confirm
        if [[ $confirm == [yY] ]]; then
            echo "🗑️  전체 삭제 중..."
            docker-compose down -v --rmi all
            docker system prune -f
            echo "✅ 전체 삭제 완료"
        else
            echo "❌ 삭제가 취소되었습니다."
        fi
        ;;
    *)
        echo "❌ 잘못된 선택입니다."
        exit 1
        ;;
esac

# 실행 후 접속 정보 표시
if [[ $choice == 1 || $choice == 2 || $choice == 3 ]]; then
    echo ""
    echo "🌐 서비스 접속 정보:"
    echo "📖 FastAPI 문서: http://localhost:8000/docs"
    echo "🔧 MCP 서버: http://localhost:8001"
    echo "🗄️  pgAdmin: http://localhost:8080"
    echo "📊 MongoDB Express: http://localhost:8081"
    echo ""
    echo "📝 기본 계정 정보:"
    echo "   pgAdmin: admin@example.com / admin"
    echo "   MongoDB Express: admin / admin"
fi 