# 외부 MCP 서버 + FastAPI 서버 연동 가이드

## 개요

이 프로젝트는 **외부 MCP(Model Context Protocol) 서버**와 **FastAPI 서버**를 분리하여 연동하는 구조입니다.

### 아키텍처

```
┌─────────────────┐    HTTP 통신    ┌─────────────────┐
│   FastAPI 서버  │ ◄─────────────► │   MCP 서버      │
│   (포트 8000)   │                 │   (포트 8001)   │
└─────────────────┘                 └─────────────────┘
         │                                   │
         │                                   │
         ▼                                   ▼
┌─────────────────┐                 ┌─────────────────┐
│   PostgreSQL    │                 │   FastAPI 서버  │
│   (주 데이터)    │                 │   (API 호출)    │
└─────────────────┘                 └─────────────────┘
         │
         ▼
┌─────────────────┐
│   MongoDB       │
│   (대화 히스토리) │
└─────────────────┘
```

## 서버 구성

### 1. FastAPI 서버 (포트 8000)
- **역할**: 메인 백엔드 API 서버
- **기능**: 
  - 사용자 인증/인가
  - 데이터베이스 CRUD 작업
  - 기존 API 엔드포인트 제공
  - Swagger 문서화 (`/docs`)
- **데이터베이스**: PostgreSQL (주 데이터), MongoDB (대화 히스토리)

### 2. MCP 서버 (포트 8001)
- **역할**: Model Context Protocol 서버
- **기능**:
  - 도구(Tool) 정의 및 관리
  - FastAPI 서버와의 통신 중계
  - MCP 프로토콜 구현
  - 별도 Swagger 문서화 (`/docs`)

## 설치 및 실행

### 1. 의존성 설치
```bash
cd backend
pip install -r requirements.txt
```

### 2. 서버 실행

#### 방법 1: 자동 실행 스크립트 사용 (권장)
```bash
cd backend
python run_servers.py
```

#### 방법 2: 수동 실행
```bash
# 터미널 1: MCP 서버 실행
cd backend
python -m app.services.mcp_server

# 터미널 2: FastAPI 서버 실행
cd backend
uvicorn app.main:app --reload --port 8000
```

### 3. 서버 접속 확인

#### FastAPI 서버
- **URL**: http://localhost:8000
- **Swagger**: http://localhost:8000/docs
- **기능**: 기존 API 엔드포인트들

#### MCP 서버
- **URL**: http://localhost:8001
- **Swagger**: http://localhost:8001/docs
- **기능**: MCP 도구 및 프로토콜

## API 사용법

### 1. 외부 MCP를 통한 채팅

```bash
curl -X POST "http://localhost:8000/mcp/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 123,
    "message": "채용공고 목록을 보여주세요"
  }'
```

### 2. MCP 도구 목록 조회

```bash
curl -X GET "http://localhost:8000/mcp/tools"
```

### 3. MCP 서버 상태 확인

```bash
curl -X GET "http://localhost:8000/mcp/health"
```

### 4. 특정 도구 직접 호출

```bash
curl -X POST "http://localhost:8000/mcp/tools/job_posts/call" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 5
  }'
```

## Swagger 문서화

### FastAPI 서버 Swagger (http://localhost:8000/docs)
- 기존 API 엔드포인트들
- 사용자 인증/인가
- 데이터베이스 CRUD 작업
- **MCP 연동 API들** (`/mcp/*`)

### MCP 서버 Swagger (http://localhost:8001/docs)
- MCP 도구 정의
- 도구 호출 API
- MCP 프로토콜 엔드포인트

## 주요 차이점

### 기존 구조 vs 외부 MCP 구조

| 구분 | 기존 구조 | 외부 MCP 구조 |
|------|-----------|---------------|
| **MCP 기능** | FastAPI 내부 구현 | 별도 서버로 분리 |
| **Swagger** | 통합 문서 | 분리된 문서 |
| **확장성** | 제한적 | 높음 |
| **유지보수** | 단순 | 모듈화됨 |
| **포트** | 8000만 사용 | 8000 + 8001 |

## 장점

### 1. **모듈화**
- MCP 기능을 독립적인 서버로 분리
- 각 서버의 책임이 명확히 구분됨

### 2. **확장성**
- MCP 서버를 다른 프로젝트에서도 재사용 가능
- 마이크로서비스 아키텍처로 발전 가능

### 3. **독립적인 Swagger**
- FastAPI 서버: 기존 API 문서
- MCP 서버: MCP 도구 및 프로토콜 문서

### 4. **유연한 배포**
- 각 서버를 독립적으로 배포 가능
- 로드 밸런싱 및 스케일링 용이

## 주의사항

### 1. **서버 간 통신**
- FastAPI 서버와 MCP 서버 간 HTTP 통신
- 네트워크 지연 고려 필요

### 2. **에러 처리**
- MCP 서버 다운 시 적절한 에러 처리
- 연결 실패 시 fallback 메커니즘

### 3. **보안**
- 서버 간 통신 시 인증/인가 고려
- CORS 설정 확인

## 트러블슈팅

### 1. MCP 서버 연결 실패
```bash
# MCP 서버 상태 확인
curl http://localhost:8001/health

# 포트 충돌 확인
netstat -an | grep 8001
```

### 2. FastAPI 서버 연결 실패
```bash
# FastAPI 서버 상태 확인
curl http://localhost:8000/

# 포트 충돌 확인
netstat -an | grep 8000
```

### 3. 데이터베이스 연결 문제
```bash
# PostgreSQL 연결 확인
# MongoDB 연결 확인
```

## 향후 개선 계획

1. **서비스 디스커버리**: Consul, Eureka 등 도입
2. **API Gateway**: Kong, Traefik 등 도입
3. **모니터링**: Prometheus, Grafana 등 도입
4. **로깅**: ELK Stack 도입
5. **컨테이너화**: Docker, Kubernetes 도입

## 결론

외부 MCP 서버와 FastAPI 서버를 분리하여 연동하는 구조는 **모듈화, 확장성, 유지보수성**을 크게 향상시킵니다. 각 서버는 독립적인 Swagger 문서를 제공하며, 필요에 따라 독립적으로 배포하고 확장할 수 있습니다. 