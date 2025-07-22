from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class JobPostBase(BaseModel):
    """채용공고 기본 필드 스키마"""
    id: int
    title: str
    company_name: str
    address: Optional[str] = None
    posting_date: datetime
    deadline: Optional[datetime] = None
    is_expired: Optional[bool] = False  # 공고 만료 여부
    similarity: Optional[float] = None

    class Config:
        from_attributes = True

class JobPostBasicResponse(JobPostBase):
    """채용공고 기본 정보 스키마 (필수 필드만 포함)"""
    pass

class JobPostSimpleResponse(BaseModel):
    """추천 시스템용 최소 스키마"""
    id: int
    title: str
    tech_stack: Optional[str] = None
    similarity: Optional[float] = None

    class Config:
        from_attributes = True

class JobPostSearchResponse(JobPostBase):
    """채용공고 검색용 간소화된 스키마 (긴 텍스트 필드 제외)"""
    size: Optional[str] = None
    employment_type: Optional[str] = None
    applicant_type: str
    tech_stack: Optional[str] = None

class JobPostResponse(JobPostSearchResponse):
    """채용공고 상세 조회용 스키마 (모든 필드 포함)"""
    job_required_skill_id: Optional[int] = None
    main_tasks: Optional[str] = None
    qualifications: Optional[str] = None
    preferences: Optional[str] = None
    created_at: datetime

