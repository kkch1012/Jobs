from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.models import user, user_skill, roadmap, user_roadmap,user_preference
from app.database import Base, engine
from app.database.mongo import init_mongo
from app.mcp_client import parse_mcp
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
    preprocess
)

# 앱 시작 시 데이터베이스 초기화 (PostgreSQL 테이블 생성 및 MongoDB 연결)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # PostgreSQL: 테이블 생성
    Base.metadata.create_all(bind=engine)
    # MongoDB: 비니(Beanie) 초기화
    await init_mongo()
    # 애플리케이션 실행
    yield

# FastAPI 앱 생성
app = FastAPI(
    title="Recruitment Platform API",
    lifespan=lifespan
)

# CORS 설정 (임시 전체 허용)
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
app.include_router(preprocess.router)

# MCP 모의 API
@app.get("/")
def hello():
    return {"message": "MCP mock 서버가 실행 중입니다."}

@app.get("/mcp", summary="mcp 엔드포인트", description="프론트엔드에서 전달된 자연어 명령을 처리하는 MCP 엔드포인트")
async def mcp_endpoint(message: str, user_id: int):
    """
    Frontend에서 전달된 자연어 명령을 처리하는 MCP 엔드포인트.
    예: /mcp?message=파이썬+로드맵+추천해줘&user_id=1
    """
    try:
        response_data = await parse_mcp(message, user_id)
        return response_data
    except Exception as e:
        return {
            "status": "error",
            "message": "MCP 요청 처리 실패",
            "detail": str(e)
        }
