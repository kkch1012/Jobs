from sqlalchemy import Column, Integer, String, ForeignKey, Index, Date
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base

class WeeklySkillStat(Base):
    __tablename__ = "weekly_skill_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 직무 정보
    job_role_id = Column(Integer, ForeignKey("job_required_skills.id", ondelete="CASCADE"), nullable=False) 
    
    # 시간 정보 (주차와 날짜 분리)
    week = Column(Integer, nullable=False)  # ISO 주차 (예: 29)
    date = Column(Date, nullable=False)     # 날짜 (예: 2025-01-15)
    
    # 스킬 정보
    skill = Column(String(500), nullable=False)
    count = Column(Integer, nullable=False, default=0)
    
    # 분석 필드 타입
    field_type = Column(String(50), nullable=False)  # tech_stack, required_skills, preferred_skills, main_tasks_skills
    
    # 관계 설정
    job_role = relationship("JobRequiredSkill", back_populates="weekly_skill_stats")
    
    # 복합 인덱스 (성능 최적화)
    __table_args__ = (
        Index('idx_job_week_date_field', 'job_role_id', 'week', 'date', 'field_type'),
        Index('idx_skill_count', 'skill', 'count'),
        Index('idx_date', 'date'),
        Index('idx_week', 'week'),
    ) 