import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    # PostgreSQL 설정 (주 DB)
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "SQLALCHEMY_DATABASE_URI", 
        "postgresql://myuser:mypassword@localhost:5432/jobs"
    )

    # MongoDB 설정 (크롤링 원본 데이터 저장용)
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "jobs_db")

    # 보안 설정
    SECRET_KEY: str = os.getenv("SECRET_KEY", "SUPERSECRETKEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

settings = Settings()
