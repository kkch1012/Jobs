from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)    # 스킬 ID
    name = Column(String, nullable=False)                 # 기술명

    # 중간 테이블(UserSkill)을 통한 사용자들과의 관계 설정
    users = relationship("UserSkill", back_populates="skill", cascade="all, delete-orphan")
