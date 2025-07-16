from app.database.PostgreSQL import Base, engine, SessionLocal

# DB 세션을 제공하는 의존성 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 모델들을 등록하기 위한 import (순환 import 방지)
# 각 모델 파일에서 Base를 import하여 자동으로 등록됨
