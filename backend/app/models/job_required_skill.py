from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.PostgreSQL import Base

class JobRequiredSkill(Base):
    __tablename__ = "job_required_skills"
    
    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, nullable=False, unique=True)
    
    # 관계 설정
    weekly_skill_stats = relationship("WeeklySkillStat", back_populates="job_role", cascade="all, delete-orphan")
