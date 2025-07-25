# 🐳 JOBS 프로젝트 Docker 가이드

## 📋 개요

이 가이드는 JOBS 프로젝트를 Docker 컨테이너로 실행하는 방법을 설명합니다.

## 🏗️ 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI 서버   │    │    MCP 서버     │    │  PostgreSQL DB  │
│   (포트 8000)   │◄──►│   (포트 8001)   │◄──►│   (포트 5432)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌─────────────────┐    ┌┴────────────────┐
         │   MongoDB DB    │    │    Redis 캐시    │
         │  (포트 27017)   │    │   (포트 6379)   │
         └─────────────────┘    └─────────────────┘
```

## 🛠️ 필요한 소프트웨어

1. **Docker**: [설치 가이드](https://docs.docker.com/get-docker/)
2. **Docker Compose**: [설치 가이드](https://docs.docker.com/compose/install/)

## ⚡ 빠른 시작

### 1. 환경변수 설정

```bash
# env.example을 복사하여 .env 파일 생성
cp env.example .env

# .env 파일 편집 (필수!)
nano .env
```

**필수 설정 항목:**
```env
OPENROUTER_API_KEY=your_actual_api_key_here
SECRET_KEY=your_very_long_secret_key_here
```

### 2. 실행

#### Linux/Mac:
```bash
chmod +x docker-run.sh
./docker-run.sh
```

#### Windows:
```cmd
docker-run.bat
```

#### 수동 실행:
```bash
# 전체 서비스 시작
docker-compose up --build

# 백그라운드 실행
docker-compose up --build -d

# 애플리케이션만 실행 (관리도구 제외)
docker-compose up --build fastapi mcp-server postgres mongo redis
```

## 🌐 서비스 접속 정보

| 서비스 | URL | 설명 |
|--------|-----|------|
| FastAPI 문서 | http://localhost:8000/docs | API 문서 및 테스트 |
| MCP 서버 | http://localhost:8001 | MCP 도구 서버 |
| pgAdmin | http://localhost:8080 | PostgreSQL 관리 |
| MongoDB Express | http://localhost:8081 | MongoDB 관리 |

## 🔑 기본 계정 정보

| 서비스 | 사용자명 | 비밀번호 |
|--------|----------|----------|
| pgAdmin | admin@example.com | admin |
| MongoDB Express | admin | admin |

## 📁 프로젝트 구조

```
JOBS/
├── Dockerfile              # FastAPI 서버용
├── Dockerfile.mcp          # MCP 서버용
├── docker-compose.yml      # 서비스 오케스트레이션
├── docker-run.sh          # Linux/Mac 실행 스크립트
├── docker-run.bat         # Windows 실행 스크립트
├── env.example            # 환경변수 예시
├── .dockerignore          # Docker 빌드 제외 파일
├── init-scripts/          # PostgreSQL 초기화
│   └── 01-init.sql
├── mongo-init/            # MongoDB 초기화
│   └── 01-init.js
└── backend/               # 애플리케이션 코드
```

## 🛠️ 개발 환경 설정

### 로그 확인
```bash
# 모든 서비스 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f fastapi
docker-compose logs -f mcp-server
```

### 서비스 상태 확인
```bash
docker-compose ps
```

### 컨테이너 접속
```bash
# FastAPI 컨테이너 접속
docker-compose exec fastapi bash

# PostgreSQL 접속
docker-compose exec postgres psql -U myuser -d jobs
```

## 🔧 서비스 관리

### 서비스 중지
```bash
docker-compose down
```

### 서비스 재시작
```bash
docker-compose restart
```

### 특정 서비스만 재빌드
```bash
docker-compose up --build fastapi
```

### 데이터 삭제 (주의!)
```bash
# 컨테이너와 볼륨 모두 삭제
docker-compose down -v

# 이미지도 함께 삭제
docker-compose down -v --rmi all
```

## 📊 데이터베이스 관리

### PostgreSQL
- **접속**: pgAdmin (http://localhost:8080) 또는 직접 연결
- **연결 정보**:
  - Host: localhost (컨테이너 내부에서는 postgres)
  - Port: 5432
  - Database: jobs
  - Username: myuser
  - Password: mypassword

### MongoDB
- **접속**: MongoDB Express (http://localhost:8081) 또는 직접 연결
- **연결 정보**:
  - Host: localhost (컨테이너 내부에서는 mongo)
  - Port: 27017
  - Database: jobs_db
  - Username: admin
  - Password: yourpassword

## 🚨 문제 해결

### 일반적인 문제들

1. **포트 충돌**
   ```bash
   # 포트 사용 확인
   netstat -tulpn | grep :8000
   
   # 다른 포트로 변경
   # docker-compose.yml에서 ports 설정 수정
   ```

2. **환경변수 미설정**
   ```bash
   # .env 파일 확인
   cat .env
   
   # 필수 변수 설정 확인
   ```

3. **데이터베이스 연결 실패**
   ```bash
   # 데이터베이스 컨테이너 상태 확인
   docker-compose ps postgres
   
   # 데이터베이스 로그 확인
   docker-compose logs postgres
   ```

4. **메모리 부족**
   ```bash
   # Docker 메모리 설정 증가 (Docker Desktop)
   # 또는 불필요한 컨테이너 정리
   docker system prune
   ```

### 로그 분석

```bash
# 에러 로그만 필터링
docker-compose logs | grep -i error

# 특정 시간 이후 로그
docker-compose logs --since="2024-01-01T00:00:00"
```

## 🔄 업데이트

```bash
# 최신 코드로 업데이트
git pull

# 컨테이너 재빌드
docker-compose up --build

# 캐시 없이 완전 재빌드
docker-compose build --no-cache
```

## 📈 성능 최적화

1. **리소스 제한 설정**
   ```yaml
   # docker-compose.yml에 추가
   deploy:
     resources:
       limits:
         memory: 512M
       reservations:
         memory: 256M
   ```

2. **헬스체크 간격 조정**
   ```dockerfile
   HEALTHCHECK --interval=60s --timeout=10s
   ```

## 🔒 보안 고려사항

1. **환경변수 보안**
   - `.env` 파일을 절대 Git에 커밋하지 마세요
   - 운영환경에서는 강력한 비밀번호 사용

2. **네트워크 보안**
   - 운영환경에서는 필요한 포트만 노출
   - 방화벽 설정 권장

3. **데이터 백업**
   ```bash
   # PostgreSQL 백업
   docker-compose exec postgres pg_dump -U myuser jobs > backup.sql
   
   # MongoDB 백업
   docker-compose exec mongo mongodump --out /backup
   ```

## 📞 지원

문제가 발생하면 다음을 확인해주세요:

1. Docker 버전: `docker --version`
2. Docker Compose 버전: `docker-compose --version`
3. 시스템 리소스: 메모리, 디스크 공간
4. 포트 충돌: `netstat -tulpn | grep 8000`

## 📝 라이센스

이 프로젝트는 MIT 라이센스를 따릅니다. 