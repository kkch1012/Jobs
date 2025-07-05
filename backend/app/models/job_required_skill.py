from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database.PostgreSQL import Base

class JobRequiredSkill(Base):
    __tablename__ = "job_required_skill"
    
    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, nullable=False)                     # 직무 이름
    skill = Column(String, nullable=False)                        # 직무에 필요한 기술명
    skill_type = Column(String, nullable=False)                   # 요구 유형 (예: "required" or "preferred")
    priority = Column(Integer, nullable=False, default=1)         # 중요도/우선순위
    job_date = Column(DateTime, nullable=False, server_default=func.now())  # 생성 날짜
    