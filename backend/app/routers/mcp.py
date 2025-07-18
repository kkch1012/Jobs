from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.services.mcp_client import mcp_client
from app.schemas.mcp import (
    MessageIn, GapAnalysisRequest, GapAnalysisResponse, SkillSearchRequest, 
    SkillSearchResponse, RoadmapRecommendationsRequest, RoadmapRecommendationsResponse,
    RoadmapRecommendationsDirectRequest, ResumeVsJobSkillTrendRequest, 
    ResumeVsJobSkillTrendResponse, WeeklySkillFrequencyRequest, 
    WeeklySkillFrequencyResponse, JobRecommendationRequest, JobRecommendationResponse,
    ResumeRequest, ResumeResponse, ResumeUpdateResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP"])

@router.get("/tools", summary="MCP 도구 목록 조회", description="MCP 서버에서 사용 가능한 모든 도구 목록을 조회합니다.")
async def list_mcp_tools():
    """MCP 서버의 사용 가능한 도구 목록을 반환합니다."""
    try:
        tools = await mcp_client.list_tools()
        return {"tools": tools}
    except Exception as e:
        logger.error(f"MCP 도구 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MCP 서버 연결 실패: {str(e)}")

@router.get("/health", summary="MCP 서버 상태 확인", description="MCP 서버의 상태를 확인합니다.")
async def check_mcp_health():
    """MCP 서버의 상태를 확인합니다."""
    try:
        health = await mcp_client.health_check()
        return health
    except Exception as e:
        logger.error(f"MCP 서버 상태 확인 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MCP 서버 상태 확인 실패: {str(e)}")

@router.post("/gap-analysis", response_model=GapAnalysisResponse, summary="MCP를 통한 갭 분석", description="MCP 서버를 통해 사용자의 갭 분석을 수행합니다.")
async def perform_gap_analysis_via_mcp(
    request: GapAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """MCP 서버를 통해 갭 분석을 수행합니다."""
    try:
        # 실제 구현에서는 인증 토큰을 전달해야 합니다
        # 여기서는 간단히 사용자 ID를 사용
        auth_token = f"Bearer user_{current_user.id}"
        
        result = await mcp_client.perform_gap_analysis(request.category, auth_token)
        
        return GapAnalysisResponse(
            gap_result=result.get("gap_result", ""),
            top_skills=result.get("top_skills", [])
        )
    except Exception as e:
        logger.error(f"MCP 갭 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"갭 분석 실패: {str(e)}")

@router.get("/skill-search", response_model=SkillSearchResponse, summary="MCP를 통한 스킬 검색", description="MCP 서버를 통해 스킬을 검색합니다.")
async def search_skills_via_mcp(
    skill_name: str = Query(..., description="검색할 스킬명")
):
    """MCP 서버를 통해 스킬을 검색합니다."""
    try:
        result = await mcp_client.search_skills(skill_name)
        
        return SkillSearchResponse(
            skills=result.get("skills", []),
            total=result.get("total", 0)
        )
    except Exception as e:
        logger.error(f"MCP 스킬 검색 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"스킬 검색 실패: {str(e)}")

@router.post("/roadmap-recommendations", response_model=RoadmapRecommendationsResponse, summary="MCP를 통한 로드맵 추천", description="MCP 서버를 통해 로드맵을 추천받습니다.")
async def get_roadmap_recommendations_via_mcp(
    request: RoadmapRecommendationsRequest,
    current_user: User = Depends(get_current_user)
):
    """MCP 서버를 통해 로드맵 추천을 받습니다."""
    try:
        auth_token = f"Bearer user_{current_user.id}"
        
        result = await mcp_client.get_roadmap_recommendations(
            request.category, request.limit, auth_token
        )
        
        return RoadmapRecommendationsResponse(
            roadmaps=result.get("roadmaps", []),
            total=result.get("total", 0)
        )
    except Exception as e:
        logger.error(f"MCP 로드맵 추천 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"로드맵 추천 실패: {str(e)}")

@router.post("/roadmap-recommendations/direct", response_model=RoadmapRecommendationsResponse, summary="MCP를 통한 직접 로드맵 추천", description="MCP 서버를 통해 기존 갭 분석 결과로 로드맵을 추천받습니다.")
async def get_roadmap_recommendations_direct_via_mcp(
    request: RoadmapRecommendationsDirectRequest,
    current_user: User = Depends(get_current_user)
):
    """MCP 서버를 통해 직접 로드맵 추천을 받습니다."""
    try:
        auth_token = f"Bearer user_{current_user.id}"
        
        result = await mcp_client.get_roadmap_recommendations_direct(
            request.category, request.gap_result_text, request.limit, auth_token
        )
        
        return RoadmapRecommendationsResponse(
            roadmaps=result.get("roadmaps", []),
            total=result.get("total", 0)
        )
    except Exception as e:
        logger.error(f"MCP 직접 로드맵 추천 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"로드맵 추천 실패: {str(e)}")

@router.post("/resume-vs-job-skill-trend", response_model=ResumeVsJobSkillTrendResponse, summary="MCP를 통한 이력서 vs 직무 스킬 비교", description="MCP 서버를 통해 이력서 스킬과 직무 스킬을 비교합니다.")
async def compare_resume_vs_job_skills_via_mcp(
    request: ResumeVsJobSkillTrendRequest,
    current_user: User = Depends(get_current_user)
):
    """MCP 서버를 통해 이력서 스킬과 직무 스킬을 비교합니다."""
    try:
        auth_token = f"Bearer user_{current_user.id}"
        
        result = await mcp_client.compare_resume_vs_job_skills(
            request.job_name, request.field, auth_token
        )
        
        return ResumeVsJobSkillTrendResponse(
            comparison=result.get("comparison", []),
            total=result.get("total", 0)
        )
    except Exception as e:
        logger.error(f"MCP 스킬 비교 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"스킬 비교 실패: {str(e)}")

@router.post("/weekly-skill-frequency", response_model=WeeklySkillFrequencyResponse, summary="MCP를 통한 주간 스킬 빈도 조회", description="MCP 서버를 통해 주간 스킬 빈도를 조회합니다.")
async def get_weekly_skill_frequency_via_mcp(
    request: WeeklySkillFrequencyRequest
):
    """MCP 서버를 통해 주간 스킬 빈도를 조회합니다."""
    try:
        result = await mcp_client.get_weekly_skill_frequency(
            request.job_name, request.field
        )
        
        return WeeklySkillFrequencyResponse(
            weekly_skill_frequency=result.get("weekly_skill_frequency", []),
            total=result.get("total", 0)
        )
    except Exception as e:
        logger.error(f"MCP 주간 스킬 빈도 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"주간 스킬 빈도 조회 실패: {str(e)}")

@router.post("/job-recommendations", response_model=JobRecommendationResponse, summary="MCP를 통한 채용공고 추천", description="MCP 서버를 통해 맞춤형 채용공고를 추천받습니다.")
async def get_job_recommendations_via_mcp(
    request: JobRecommendationRequest,
    current_user: User = Depends(get_current_user)
):
    """MCP 서버를 통해 맞춤형 채용공고를 추천받습니다."""
    try:
        auth_token = f"Bearer user_{current_user.id}"
        
        result = await mcp_client.get_job_recommendations(
            request.top_n, auth_token
        )
        
        return JobRecommendationResponse(
            recommendation=result.get("recommendation", ""),
            job_count=result.get("job_count", 0)
        )
    except Exception as e:
        logger.error(f"MCP 채용공고 추천 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"채용공고 추천 실패: {str(e)}")

@router.get("/my-resume", response_model=ResumeResponse, summary="MCP를 통한 내 이력서 조회", description="MCP 서버를 통해 내 이력서 정보를 조회합니다.")
async def get_my_resume_via_mcp(
    current_user: User = Depends(get_current_user)
):
    """MCP 서버를 통해 내 이력서 정보를 조회합니다."""
    try:
        auth_token = f"Bearer user_{current_user.id}"
        
        result = await mcp_client.get_my_resume(auth_token)
        
        return ResumeResponse(resume=result.get("resume", {}))
    except Exception as e:
        logger.error(f"MCP 이력서 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"이력서 조회 실패: {str(e)}")

@router.put("/my-resume", response_model=ResumeUpdateResponse, summary="MCP를 통한 이력서 업데이트", description="MCP 서버를 통해 이력서 정보를 업데이트합니다.")
async def update_my_resume_via_mcp(
    request: ResumeRequest,
    current_user: User = Depends(get_current_user)
):
    """MCP 서버를 통해 이력서 정보를 업데이트합니다."""
    try:
        auth_token = f"Bearer user_{current_user.id}"
        
        result = await mcp_client.update_resume(request.resume_data, auth_token)
        
        return ResumeUpdateResponse(message=result.get("message", "업데이트 완료"))
    except Exception as e:
        logger.error(f"MCP 이력서 업데이트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"이력서 업데이트 실패: {str(e)}")

@router.post("/chat", summary="MCP 채팅", description="MCP 프로토콜을 통한 채팅을 수행합니다.")
async def chat_with_mcp(
    request: MessageIn,
    current_user: User = Depends(get_current_user)
):
    """MCP 프로토콜을 통한 채팅을 수행합니다."""
    try:
        # 여기서는 간단한 예시로 tools/list 메서드를 호출
        result = await mcp_client.chat_with_mcp(
            method="tools/list",
            params={},
            request_id=str(request.session_id)
        )
        
        return result
    except Exception as e:
        logger.error(f"MCP 채팅 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MCP 채팅 실패: {str(e)}") 