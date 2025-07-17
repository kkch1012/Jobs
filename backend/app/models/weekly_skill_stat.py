from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.PostgreSQL import Base

class WeeklySkillStat(Base):
    __tablename__ = "weekly_skill_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 직무 정보
    job_role_id = Column(Integer, ForeignKey("job_required_skills.id", ondelete="CASCADE"), nullable=False) 
    # 시간 정보 (주차.요일 형태: 1.1=1주차 월요일, 2.3=2주차 화요일)
    week_day = Column(String(50), nullable=False)  # 예: "1.1", "2.3", "15.7"
    
    # 스킬 정보
    skill = Column(String(500), nullable=False)
    count = Column(Integer, nullable=False, default=0)
    
    # 분석 필드 타입
    field_type = Column(String(50), nullable=False)  # tech_stack, required_skills, preferred_skills, main_tasks_skills
    
    # 통계 생성 날짜 (년-월-일)
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 관계 설정
    job_role = relationship("JobRequiredSkill", back_populates="weekly_skill_stats")
    
    # 복합 인덱스 (성능 최적화)
    __table_args__ = (
        Index('idx_job_week_day_field', 'job_role_id', 'week_day', 'field_type'),
        Index('idx_skill_count', 'skill', 'count'),
        Index('idx_created_date', 'created_date'),
    ) 