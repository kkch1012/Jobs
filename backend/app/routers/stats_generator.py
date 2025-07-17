from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer
from app.database import get_db
from app.services.weekly_stats_service import WeeklyStatsService
from typing import Dict, Any
import logging
from datetime import datetime, timedelta
from app.models.weekly_skill_stat import WeeklySkillStat
import pytz

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
    db: Session = Depends(get_db)
):
    try:
        logger.info("주간 스킬 통계 생성 요청: 모든 필드 타입")
        
        # 백그라운드에서 모든 필드 타입에 대해 통계 생성 실행
        background_tasks.add_task(
            WeeklyStatsService._generate_all_field_types_stats,
            db
        )
        
        return {
            "message": "주간 스킬 통계 생성이 시작되었습니다.",
            "field_types": ["tech_stack", "required_skills", "preferred_skills", "main_tasks_skills"],
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

- tech_stack, required_skills, preferred_skills, main_tasks_skills 4개 필드 통계를 모두 조회
- 미리 계산된 통계 데이터를 빠르게 조회합니다.
- weeks_back 파라미터로 조회 기간을 설정할 수 있습니다.
"""
)
async def get_weekly_stats(
    job_name: str,
    week: int | None = None,  # 특정 주차 입력 (기본값: 현재 주차)
    db: Session = Depends(get_db)
):
    # 현재 주차 계산 (ISO 주차 기준, 서울 시간대)
    seoul_tz = pytz.timezone('Asia/Seoul')
    current_date = datetime.now(seoul_tz)
    year, current_week, day_of_week = current_date.isocalendar()
    
    # week가 None이면 현재 주차로 설정
    if week is None:
        week = current_week
    try:
        # 1. 직무 조회
        from app.models.job_required_skill import JobRequiredSkill
        job_role = db.query(JobRequiredSkill).filter(
            JobRequiredSkill.job_name == job_name
        ).first()
        
        if not job_role:
            raise HTTPException(status_code=404, detail=f"직무 '{job_name}'을 찾을 수 없습니다.")
        
        field_types = ["tech_stack", "required_skills", "preferred_skills", "main_tasks_skills"]
        all_stats = {}
        
        for field_type in field_types:
            # 특정 주차의 데이터만 조회 (기본값: 현재 주차)
            stats = db.query(WeeklySkillStat).filter(
                WeeklySkillStat.job_role_id == job_role.id,
                WeeklySkillStat.field_type == field_type,
                func.cast(func.split_part(WeeklySkillStat.week_day, '.', 1), Integer) == week
            ).order_by(
                WeeklySkillStat.week_day.desc(),
                WeeklySkillStat.count.desc()
            ).all()
            
            # 응답 형식으로 변환
            formatted_stats = []
            for stat in stats:
                formatted_stats.append({
                    "week_day": stat.week_day,
                    "skill": stat.skill,
                    "count": stat.count,
                    "created_date": stat.created_date.isoformat() if stat.created_date is not None else None
                })
            
            all_stats[field_type] = formatted_stats
        
        return {
            "job_name": job_name,
            "field_types": field_types,
            "week": week,
            "stats": all_stats,
            "total_count": sum(len(stats) for stats in all_stats.values())
        }
        
    except Exception as e:
        logger.error(f"주간 스킬 통계 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/trend/{job_name}",
    summary="직무별 필드 타입 트렌드 데이터 조회",
    description="""
특정 직무의 특정 필드 타입 트렌드를 조회합니다.

- tech_stack, required_skills, preferred_skills, main_tasks_skills 4개 필드 중 선택하여 트렌드 조회
- 해당 필드 타입의 모든 스킬 통계를 주차별로 조회합니다.
- 차트 시각화에 적합한 데이터 형식으로 반환됩니다.
"""
)
async def get_job_field_trend(
    job_name: str,
    field_type: str = "tech_stack",
    week: int | None = None,  # 특정 주차 입력 (기본값: 현재 주차)
    db: Session = Depends(get_db)
):
    # 현재 주차 계산 (ISO 주차 기준, 서울 시간대)
    seoul_tz = pytz.timezone('Asia/Seoul')
    current_date = datetime.now(seoul_tz)
    year, current_week, day_of_week = current_date.isocalendar()
    
    # week가 None이면 현재 주차로 설정
    if week is None:
        week = current_week
        
    try:
        # 1. 직무 조회
        from app.models.job_required_skill import JobRequiredSkill
        job_role = db.query(JobRequiredSkill).filter(
            JobRequiredSkill.job_name == job_name
        ).first()
        
        if not job_role:
            raise HTTPException(status_code=404, detail=f"직무 '{job_name}'을 찾을 수 없습니다.")
        
        # 2. 특정 필드 타입의 특정 주차 트렌드 조회
        stats = db.query(WeeklySkillStat).filter(
            WeeklySkillStat.job_role_id == job_role.id,
            WeeklySkillStat.field_type == field_type,
            func.cast(func.split_part(WeeklySkillStat.week_day, '.', 1), Integer) == week
        ).order_by(
            WeeklySkillStat.count.desc(),
            WeeklySkillStat.skill.asc()
        ).all()
        
        # 3. 응답 형식으로 변환
        trend_data = []
        for stat in stats:
            trend_data.append({
                "week_day": stat.week_day,
                "skill": stat.skill,
                "count": stat.count,
                "date": f"Week {stat.week_day}"
            })
        
        return {
            "job_name": job_name,
            "field_type": field_type,
            "week": week,
            "trend_data": trend_data,
            "total_points": len(trend_data)
        }
        
    except Exception as e:
        logger.error(f"스킬 트렌드 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"트렌드 조회 중 오류가 발생했습니다: {str(e)}"
        ) 