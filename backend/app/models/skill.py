from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base
from app.models.user_skill import UserSkill

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)    # 스킬 ID
    name = Column(String, nullable=False)                 # 기술명
    
    user_skills = relationship("UserSkill", back_populates="skill")
