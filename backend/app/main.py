from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import Base, engine
from app.database.mongo import init_mongo, close_mongo
from app.utils.database_events import setup_database_events
from app.services.scheduler import start_scheduler, stop_scheduler
from dotenv import load_dotenv
from app.routers import (
    auth,
    user,
    skill,
    certificate,
    roadmap,
    job_required_skill,
    user_preference,
    user_roadmap,
    job_post,
    user_certificate,
    user_skill,
    visualization,
    chat,
    session,
    todo_list,
    recommender,
    similarity,
    scheduler,
    mcp
)

load_dotenv()  # .env 파일에서 환경변수 로드 mcp api 키

# 앱 시작 시 데이터베이스 초기화 (PostgreSQL 테이블 생성 및 MongoDB 연결)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # PostgreSQL: 테이블 생성
    Base.metadata.create_all(bind=engine)
    # MongoDB: 비니(Beanie) 초기화
    await init_mongo()
    # 데이터베이스 이벤트 리스너 설정
    setup_database_events()
    # 스케줄러 시작
    start_scheduler()
    # 애플리케이션 실행
    yield
    # 앱 종료 시 스케줄러 중지
    stop_scheduler()
    # 앱 종료 시 MongoDB 연결 정리
    await close_mongo()

# FastAPI 앱 생성
app = FastAPI(
    title="Recruitment Platform API",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """API 루트 경로"""
    return {
        "message": "Recruitment Platform API",
        "version": "1.0.0",
        "docs": "/docs",
        "mcp_endpoints": [
            "/chat/",
            "/mcp/tools",
            "/mcp/health"
        ]
    }

# CORS 설정 (임시 전체 허용)
# TODO: 운영 환경에서는 allow_origins에 실제 도메인만 허용하도록 제한 필요
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(skill.router)
app.include_router(certificate.router)
app.include_router(roadmap.router)
app.include_router(job_required_skill.router)
app.include_router(user_preference.router)
app.include_router(user_roadmap.router)
app.include_router(job_post.router)
app.include_router(user_certificate.router)
app.include_router(user_skill.router)
app.include_router(visualization.router)
app.include_router(chat.router)
app.include_router(session.router)
app.include_router(todo_list.router)
app.include_router(recommender.router)
app.include_router(similarity.router)
app.include_router(scheduler.router)
app.include_router(mcp.router)