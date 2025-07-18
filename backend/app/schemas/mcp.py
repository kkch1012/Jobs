from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class MessageIn(BaseModel):
    session_id: int = Field(..., description="채팅 세션 ID")
    message: str = Field(..., description="사용자 메시지")

class GapAnalysisRequest(BaseModel):
    category: str = Field(..., description="직무 카테고리 (예: 프론트엔드 개발자)")

class GapAnalysisResponse(BaseModel):
    gap_result: str = Field(..., description="자연어 갭 분석 결과")
    top_skills: List[str] = Field(..., description="부족한 스킬 Top 5")

class SkillSearchRequest(BaseModel):
    skill_name: str = Field(..., description="검색할 스킬명 (부분 검색 지원)")

class SkillSearchResponse(BaseModel):
    skills: List[Dict[str, Any]] = Field(..., description="검색된 스킬 정보 목록")
    total: int = Field(..., description="검색된 스킬 총 개수")

class RoadmapRecommendationsRequest(BaseModel):
    category: str = Field(..., description="직무 카테고리 (예: 프론트엔드 개발자)")
    limit: int = Field(10, description="추천받을 로드맵 개수 (최대 20개)")

class RoadmapRecommendationsDirectRequest(BaseModel):
    category: str = Field(..., description="직무 카테고리 (예: 프론트엔드 개발자)")
    gap_result_text: str = Field(..., description="갭 분석 결과 텍스트")
    limit: int = Field(10, description="추천받을 로드맵 개수 (최대 20개)")

class RoadmapRecommendationsResponse(BaseModel):
    roadmaps: List[Dict[str, Any]] = Field(..., description="추천된 로드맵 목록")
    total: int = Field(..., description="추천된 로드맵 총 개수")

class ResumeVsJobSkillTrendRequest(BaseModel):
    job_name: str = Field(..., description="비교할 직무명 (예: 백엔드 개발자)")
    field: str = Field("tech_stack", description="분석 대상 필드명")

class ResumeVsJobSkillTrendResponse(BaseModel):
    comparison: List[Dict[str, Any]] = Field(..., description="스킬 비교 결과 목록")
    total: int = Field(..., description="비교 결과 총 개수")

class WeeklySkillFrequencyRequest(BaseModel):
    job_name: str = Field(..., description="조회할 직무명 (예: 백엔드 개발자)")
    field: str = Field("tech_stack", description="분석 대상 필드명")

class WeeklySkillFrequencyResponse(BaseModel):
    weekly_skill_frequency: List[Dict[str, Any]] = Field(..., description="주간 스킬 빈도 데이터")
    total: int = Field(..., description="데이터 총 개수")

class JobRecommendationRequest(BaseModel):
    top_n: int = Field(20, description="유사도 상위 N개에서 추천")

class JobRecommendationResponse(BaseModel):
    recommendation: str = Field(..., description="추천 결과 및 설명")
    job_count: int = Field(..., description="추천된 공고 수")

class ResumeRequest(BaseModel):
    resume_data: Dict[str, Any] = Field(..., description="이력서 데이터")

class ResumeResponse(BaseModel):
    resume: Dict[str, Any] = Field(..., description="이력서 정보")

class ResumeUpdateResponse(BaseModel):
    message: str = Field(..., description="수정 결과 메시지")
