from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.weekly_stats_service import WeeklyStatsService
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["Statistics"])

@router.post(
    "/generate/weekly",
    summary="주간 스킬 통계 생성",
    description="""
모든 직무에 대해 주간 스킬 통계를 생성합니다.

- tech_stack, required_skills, preferred_skills, main_tasks_skills 4개 필드에 대해 통계 생성
- 매일 실행하여 최신 통계를 생성합니다.
- 기존 통계는 삭제하고 새로운 통계로 교체합니다.
- 백그라운드에서 실행되어 대용량 데이터도 처리 가능합니다.
"""
)
async def generate_weekly_stats(
    background_tasks: BackgroundTasks,
    field_type: str = "tech_stack",
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"주간 스킬 통계 생성 요청: field_type={field_type}")
        
        # 백그라운드에서 통계 생성 실행
        background_tasks.add_task(
            WeeklyStatsService.generate_weekly_stats,
            db,
            field_type
        )
        
        return {
            "message": "주간 스킬 통계 생성이 시작되었습니다.",
            "field_type": field_type,
            "status": "processing",
            "note": "기존 통계는 자동으로 삭제되고 새로운 통계로 덮어쓰기됩니다."
        }
        
    except Exception as e:
        logger.error(f"주간 스킬 통계 생성 요청 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"통계 생성 요청 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/weekly/{job_name}",
    summary="주간 스킬 통계 조회",
    description="""
특정 직무의 주간 스킬 통계를 조회합니다.

- tech_stack, required_skills, preferred_skills, main_tasks_skills 4개 필드 통계 조회
- 미리 계산된 통계 데이터를 빠르게 조회합니다.
- weeks_back 파라미터로 조회 기간을 설정할 수 있습니다.
"""
)
async def get_weekly_stats(
    job_name: str,
    field_type: str = "tech_stack",
    weeks_back: int = 12,
    db: Session = Depends(get_db)
):
    try:
        stats = WeeklyStatsService.get_weekly_stats(
            db, job_name, field_type, weeks_back
        )
        
        return {
            "job_name": job_name,
            "field_type": field_type,
            "weeks_back": weeks_back,
            "stats": stats,
            "total_count": len(stats)
        }
        
    except Exception as e:
        logger.error(f"주간 스킬 통계 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/trend/{job_name}/{skill}",
    summary="스킬 트렌드 데이터 조회",
    description="""
특정 직무의 특정 스킬 트렌드를 조회합니다.

- tech_stack, required_skills, preferred_skills, main_tasks_skills 4개 필드 중 선택하여 트렌드 조회
- 시간에 따른 스킬 인기도 변화를 확인할 수 있습니다.
- 차트 시각화에 적합한 데이터 형식으로 반환됩니다.
"""
)
async def get_skill_trend(
    job_name: str,
    skill: str,
    field_type: str = "tech_stack",
    weeks_back: int = 12,
    db: Session = Depends(get_db)
):
    try:
        trend_data = WeeklyStatsService.get_trend_data(
            db, job_name, skill, field_type, weeks_back
        )
        
        return {
            "job_name": job_name,
            "skill": skill,
            "field_type": field_type,
            "weeks_back": weeks_back,
            "trend_data": trend_data,
            "total_points": len(trend_data)
        }
        
    except Exception as e:
        logger.error(f"스킬 트렌드 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"트렌드 조회 중 오류가 발생했습니다: {str(e)}"
        ) 