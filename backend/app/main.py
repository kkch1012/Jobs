from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from fastmcp import MCPServer
from contextlib import asynccontextmanager
from app.models import user, user_skill, roadmap, user_roadmap,user_preference
from app.database import Base, engine
from app.database.mongo import init_mongo
from dotenv import load_dotenv
from app.mcp_client import parse_mcp # FASTMCP되면 삭제
#from app.mcp_prompt import custom_prompt
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
    preprocess,
    visualization,
    mcp # FASTMCP되면 삭제
)

load_dotenv()  # .env 파일에서 환경변수 로드 mcp api 키

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
app.include_router(visualization.router)
app.include_router(mcp.router) # 실제 쓸때는 삭제 테스트 코드


# MCPServer를 /mcp에 mount
#app.mount("/mcp", MCPServer(app, system_prompt=custom_prompt))