from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.PostgreSQL import Base


class JobPost(Base):
    __tablename__ = "job_post"

    id = Column(Integer, primary_key=True, index=True)  # 공고 ID
    title = Column(String(255), nullable=False)  # 공고 제목
    company_name = Column(String(255), nullable=False, unique=True)  # 회사명
    size = Column(String(255), nullable=False)  # 기업 규모
    address = Column(String(255), nullable=False)  # 주소

    job_required_skill_id = Column(Integer, ForeignKey("job_required_skill.id", ondelete="SET NULL"), nullable=True)  # 직무 ID 참조

    employment_type = Column(String(255), nullable=True)  # 고용형태
    applicant_type = Column(Text, nullable=False)  # 지원 자격
    posting_date = Column(DateTime, nullable=False)  # 공고 게시일
    deadline = Column(DateTime, nullable=False)  # 공고 마감일
    main_tasks = Column(Text, nullable=True)  # 주요 업무
    qualifications = Column(Text, nullable=True)  # 자격 요건
    preferences = Column(Text, nullable=True)  # 우대 사항
    tech_stack = Column(Text, nullable=True)  # 기술 스택 요약

    required_skills = Column(Text, nullable=True)  # 요구 기술 스택 (콤마로 구분된 문자열 등)
    preferred_skills = Column(Text, nullable=True)  # 선호 기술 스택
    essential_tech_stack = Column(Text, nullable=True)  # 필수 기술 스택

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # 생성 시각

    # 관계 설정 (선택사항)
    job_required_skill = relationship("JobRequiredSkill", backref="job_posts")
