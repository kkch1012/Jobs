from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- SQLite용 (기본 테스트용) ---
SQLALCHEMY_DATABASE_URI = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    connect_args={"check_same_thread": False},  # SQLite 전용 옵션
    echo=False
)

# --- PostgreSQL용 (운영 시 아래 주석 해제해서 사용) ---
# from app.config import settings
# SQLALCHEMY_DATABASE_URI = settings.SQLALCHEMY_DATABASE_URI
# engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=False)

# 공통 설정
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DB 세션 의존성 주입
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
