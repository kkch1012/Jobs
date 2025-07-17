# Jobs - Recruitment Platform Backend

채용 플랫폼 백엔드 API 서버입니다. 사용자와 채용공고 간의 유사도 분석, 추천 시스템, 스케줄링 기능을 제공합니다.

## 🚀 주요 기능

### 사용자 관리
- 사용자 등록/로그인/프로필 관리
- 스킬, 경험, 자격증 관리
- 사용자 선호도 설정

### 채용공고 관리
- 채용공고 CRUD
- 스킬 요구사항 관리
- MongoDB 연동

### 유사도 분석 시스템
- 사용자-채용공고 유사도 계산
- 자동 유사도 재계산 (사용자 업데이트, 채용공고 생성 시)
- 매일 아침8시 배치 작업으로 전체 유사도 재계산

### 추천 시스템
- 개인화된 채용공고 추천
- 스킬 기반 추천

### 스케줄링 시스템
- APScheduler 기반 자동 배치 작업
- 수동 배치 작업 실행
- 스케줄러 상태 모니터링

## 🛠 기술 스택

- **Framework**: FastAPI
- **Database**: PostgreSQL + MongoDB
- **ORM**: SQLAlchemy + Beanie
- **Scheduler**: APScheduler
- **ML**: scikit-learn, sentence-transformers
- **Authentication**: JWT

## 📁 프로젝트 구조

```
backend/
├── app/
│   ├── routers/          # API 라우터
│   ├── services/         # 비즈니스 로직
│   ├── models/           # 데이터 모델
│   ├── schemas/          # Pydantic 스키마
│   ├── database/         # 데이터베이스 설정
│   └── utils/            # 유틸리티
├── run_similarity_batch.py  # 독립 배치 스크립트
├── requirements.txt      # 의존성
└── .env.example         # 환경 변수 예시
```

## 🚀 설치 및 실행

### 1 의존성 설치
```bash
cd backend
pip install -r requirements.txt
```

### 2. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일을 편집하여 실제 값으로 설정
```

### 3. 데이터베이스 설정
- PostgreSQL 서버 실행
- MongoDB 서버 실행
- 환경 변수에서 연결 정보 설정

### 4. 애플리케이션 실행
```bash
uvicorn app.main:app --reload
```

## 📊 API 엔드포인트

### 유사도 관련
- `GET /similarity/user/[object Object]user_id}` - 특정 사용자 유사도 조회
- `POST /similarity/compute-all` - 전체 사용자 유사도 계산
- `GET /similarity/matrix` - 유사도 매트릭스 조회

### 스케줄러 관련
- `GET /scheduler/status` - 스케줄러 상태 조회
- `POST /scheduler/start` - 스케줄러 시작
- `POST /scheduler/stop` - 스케줄러 중지
- `POST /scheduler/run-similarity-batch` - 수동 배치 실행

## ⏰ 자동화된 작업

### 유사도 계산 자동화
1**사용자 업데이트 시**: 사용자 정보 변경 시 자동 재계산2**채용공고 생성 시**: 새로운 채용공고 등록 시 자동 재계산
3. **매일 아침 8시**: 전체 사용자 유사도 배치 재계산
4 **수동 실행**: API를 통한 수동 배치 실행

### 배치 작업 설정
- **FastAPI 내장 스케줄러**: 애플리케이션과 함께 실행
- **독립 배치 스크립트**: `python run_similarity_batch.py`
- **크론탭 설정**: `crontab_example.txt` 참조

## 🔧 개발 가이드

### 새로운 라우터 추가1. `app/routers/` 디렉토리에 새 파일 생성2. `app/main.py`에 라우터 등록

### 새로운 서비스 추가
1 `app/services/` 디렉토리에 새 파일 생성
2. 필요한 의존성을 `requirements.txt`에 추가

### 로깅
- `app/utils/logger.py`에서 로거 설정
- 각 모듈별 전용 로거 사용

## 📝 로그 확인

### 애플리케이션 로그
```bash
# FastAPI 로그
uvicorn app.main:app --log-level info

# 배치 작업 로그
tail -f /var/log/similarity_batch.log
```

### 스케줄러 상태 확인
```bash
curl http://localhost:8000/scheduler/status
```

## 🐛 문제 해결

### 스케줄러가 작동하지 않는 경우1 APScheduler 설치 확인: `pip install APScheduler==3.100.4
2상태 확인: `/scheduler/status` 엔드포인트 호출3 로그 확인

### 유사도 계산 오류
1데이터베이스 연결 확인
2사용자/채용공고 데이터 존재 확인
3 스킬 데이터 정합성 확인

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.
