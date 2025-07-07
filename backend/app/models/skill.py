from sqlalchemy import Column, Integer, String
from app.database.PostgreSQL import Base

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)    # 스킬 ID
    name = Column(String, nullable=False)                 # 기술명