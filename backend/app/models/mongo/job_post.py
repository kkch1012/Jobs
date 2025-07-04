from typing import Optional, List
from datetime import datetime
from beanie import Document
from pydantic import BaseModel, Field


class JobPost(Document):
    
    title: dict = Field(..., description="공고 제목 (다국어 지원)")
    company_name: dict = Field(..., description="회사명 (다국어 지원)")
    size: dict = Field(..., description="기업 규모")
    address: dict = Field(..., description="주소")
    job_position: dict = Field(..., description="직무명")
    employment_type: Optional[dict] = Field(None, description="고용 형태 (예: 정규직)")
    applicant_type: dict = Field(..., description="지원 자격")
    posting_date: dict = Field(..., description="공고 게시일")
    deadline: dict = Field(..., description="공고 마감일")
    main_tasks: Optional[dict] = Field(None, description="주요 업무")
    qualifications: Optional[dict] = Field(None, description="자격 요건")
    preferences: Optional[dict] = Field(None, description="우대 사항")
    tech_stack: Optional[dict] = Field(None, description="기술 스택 요약 (다국어)")

    created_at: datetime = Field(default_factory=datetime.utcnow, description="문서 생성 시각")

    class Settings:
        name = "job_posts"

    class Config:
        schema_extra = {
            "example": {
                "title": {"ko": "백엔드 개발자", "en": "Backend Developer"},
                "company_name": {"ko": "ABC회사"},
                "size": {"ko": "중소기업"},
                "address": {"ko": "서울 강남구"},
                "job_position": {"ko": "웹개발"},
                "employment_type": {"ko": "정규직"},
                "applicant_type": {"ko": "신입"},
                "posting_date": {"ko": "2025-07-01"},
                "deadline": {"ko": "2025-07-31"},
                "main_tasks": {"ko": "웹 서버 개발"},
                "qualifications": {"ko": "Python 숙련자"},
                "preferences": {"ko": "FastAPI 경험자"},
                "tech_stack": {"ko": ["Python", "FastAPI"]}
            }
        }
