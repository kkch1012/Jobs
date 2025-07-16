from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.PostgreSQL import Base

class WeeklySkillStat(Base):
    __tablename__ = "weekly_skill_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 직무 정보
    job_role_id = Column(Integer, ForeignKey("job_required_skills.id", ondelete="CASCADE"), nullable=False) 
    # 시간 정보
    year = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    
    # 스킬 정보
    skill = Column(String(255), nullable=False)
    count = Column(Integer, nullable=False, default=0)
    
    # 분석 필드 타입
    field_type = Column(String(50), nullable=False)  # tech_stack, required_skills, preferred_skills, main_tasks_skills
    
    # 통계 생성 시간
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 관계 설정
    job_role = relationship("JobRequiredSkill", back_populates="weekly_skill_stats")
    
    # 복합 인덱스 (성능 최적화)
    __table_args__ = (
        Index('idx_job_year_week_field', 'job_role_id', 'year', 'week', 'field_type'),
        Index('idx_skill_count', 'skill', 'count'),
        Index('idx_created_at', 'created_at'),
    ) 