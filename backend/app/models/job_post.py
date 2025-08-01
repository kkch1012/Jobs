from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base
from app.models.job_role import JobRole
from app.models.user_similarity import UserSimilarity
from pgvector.sqlalchemy import Vector

class JobPost(Base):
    __tablename__ = "job_posts"

    id = Column(Integer, primary_key=True, index=True)  # 공고 ID
    title = Column(String(255), nullable=False)  # 공고 제목
    company_name = Column(String(255), nullable=False)  # 회사명
    size = Column(String(255), nullable=True)  # 기업 규모
    address = Column(String(255), nullable=True)  # 주소

    job_required_skill_id = Column(Integer, ForeignKey("job_roles.id", ondelete="SET NULL"), nullable=True)  # 직무 ID 참조

    employment_type = Column(String(255), nullable=True)  # 고용형태
    applicant_type = Column(Text, nullable=False)  # 지원 자격
    posting_date = Column(DateTime(timezone=True), nullable=False)  # 공고 게시일 (한국 시간대)
    deadline = Column(DateTime, nullable=True)  # 공고 마감일
    is_expired = Column(Boolean, nullable=True, default=False)  # 공고 만료 여부 (기본값: False)
    main_tasks = Column(Text, nullable=True)  # 주요 업무
    qualifications = Column(Text, nullable=True)  # 자격 요건
    preferences = Column(Text, nullable=True)  # 우대 사항
    tech_stack = Column(Text, nullable=True)  # 기술 스택 요약

    # JSONB 타입 컬럼
    required_skills = Column(JSONB, nullable=True)  
    preferred_skills = Column(JSONB, nullable=True)  
    main_tasks_skills = Column(JSONB, nullable=True) 

    full_embedding = Column(Vector(1024), nullable=True)  # 전체 임베딩 추가

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # 생성 시각

    # 관계 설정 (선택사항)
    job_role = relationship("JobRole", backref="job_posts")
    liked_by = relationship("UserPreference", back_populates="job_posting", cascade="all, delete-orphan")
    user_similarities = relationship("UserSimilarity", back_populates="job_post", cascade="all, delete-orphan")
