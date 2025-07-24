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
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://admin:yourpassword@localhost:27017/?authSource=admin")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "jobs_db")

    # 보안 설정
    SECRET_KEY: str = os.getenv("SECRET_KEY", "SUPERSECRETKEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # Redis 설정
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Server URLs
    FASTAPI_SERVER_URL: str = os.getenv("FASTAPI_SERVER_URL", "http://localhost:8000")
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8001")
    
    # CORS 설정
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
    
    # 배치 작업 설정
    BATCH_SCHEDULE_HOUR: int = int(os.getenv("BATCH_SCHEDULE_HOUR", "8"))
    BATCH_SCHEDULE_MINUTE: int = int(os.getenv("BATCH_SCHEDULE_MINUTE", "0"))
    
    # 유사도 계산 설정
    SIMILARITY_TOP_K: int = int(os.getenv("SIMILARITY_TOP_K", "30"))
    SIMILARITY_LIMIT: int = int(os.getenv("SIMILARITY_LIMIT", "20"))

settings = Settings()
