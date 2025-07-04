# app/config.py

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()  # .env 파일 로드 (선택)

class Settings(BaseSettings):
    # SQLAlchemy DB 설정 (기본: SQLite, 운영 시 PostgreSQL로 변경)

    # --- SQLite (기본 테스트용) ---
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "SQLALCHEMY_DATABASE_URI", 
        "sqlite:///./test.db"
    )

    # --- PostgreSQL 사용 시 아래 주석 해제 후 적용 ---
    # SQLALCHEMY_DATABASE_URI: str = os.getenv(
    #     "SQLALCHEMY_DATABASE_URI", 
    #     "postgresql+psycopg2://user:password@localhost:5432/mydatabase"
    # )

    # MongoDB 설정 (JobPost 등 크롤링 데이터 용도)
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "jobs_db")

    # 보안 설정
    SECRET_KEY: str = os.getenv("SECRET_KEY", "SUPERSECRETKEY")  # 운영 시 안전하게 보관
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 액세스 토큰 만료 시간: 1시간

settings = Settings()  # 전역 설정 객체
