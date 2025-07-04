from app.database.PostgreSQL import Base, engine, SessionLocal

# DB 세션을 제공하는 의존성 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# SQLAlchemy Base에 모델들을 등록하기 위한 전체 임포트
from app import models
