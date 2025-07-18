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
    "/generate/daily",
    summary="일간 스킬 통계 생성",
    description="""
모든 직무에 대해 일간 스킬 통계를 생성합니다.

- tech_stack, required_skills, preferred_skills, main_tasks_skills 4개 필드에 대해 통계 생성
- 실행 시점 날짜 기준으로 통계를 생성합니다.
- 같은 날짜에 실행하면 기존 통계를 덮어쓰고, 다른 날짜면 새로운 통계를 생성합니다.
- date 컬럼에 실행 시점 날짜가 저장됩니다 (예: "2025-01-15")
- week 컬럼에는 해당 날짜의 ISO 주차가 자동으로 계산되어 저장됩니다.
- 백그라운드에서 실행되어 대용량 데이터도 처리 가능합니다.
"""
)
async def generate_daily_stats(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        logger.info("일간 스킬 통계 생성 요청: 모든 필드 타입")
        
        # 백그라운드에서 모든 필드 타입에 대해 통계 생성 실행
        background_tasks.add_task(
            WeeklyStatsService._generate_all_field_types_stats,
            db
        )
        
        return {
            "message": "일간 스킬 통계 생성이 시작되었습니다.",
            "field_types": ["tech_stack", "required_skills", "preferred_skills", "main_tasks_skills"],
            "status": "processing",
            "note": "오늘 날짜의 기존 통계는 자동으로 삭제되고 새로운 통계로 덮어쓰기됩니다. date 컬럼에 실행 시점 날짜가 저장됩니다."
        }
        
    except Exception as e:
        logger.error(f"일간 스킬 통계 생성 요청 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"일간 통계 생성 요청 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/weekly/{job_name}",
    summary="주간 스킬 통계 조회",
    description="""
특정 직무의 주간 스킬 통계를 조회합니다.

- tech_stack, required_skills, preferred_skills, main_tasks_skills 4개 필드 통계를 모두 조회
- 미리 계산된 통계 데이터를 빠르게 조회합니다.
- week 파라미터로 특정 주차를 조회할 수 있습니다.
- week는 int 타입의 ISO 주차입니다 (예: 29)
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
            # 특정 주차의 데이터만 조회 (효율적인 쿼리)
            stats = db.query(WeeklySkillStat).filter(
                WeeklySkillStat.job_role_id == job_role.id,
                WeeklySkillStat.field_type == field_type,
                WeeklySkillStat.week == week
            ).order_by(
                WeeklySkillStat.date.desc(),
                WeeklySkillStat.count.desc()
            ).all()
            
            # 응답 형식으로 변환
            formatted_stats = []
            for stat in stats:
                formatted_stats.append({
                    "week": stat.week,
                    "date": stat.date.isoformat(),
                    "skill": stat.skill,
                    "count": stat.count
                })
            
            all_stats[field_type] = formatted_stats
        
        return {
            "job_name": job_name,
            "field_types": field_types,
            "week": week,
            "year": year,
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
    "/daily/{job_name}",
    summary="일간 스킬 통계 조회",
    description="""
특정 직무의 일간 스킬 통계를 조회합니다.

- tech_stack, required_skills, preferred_skills, main_tasks_skills 4개 필드 통계를 모두 조회
- 미리 계산된 통계 데이터를 빠르게 조회합니다.
- date 파라미터로 특정 날짜를 조회할 수 있습니다 (YYYY-MM-DD 형식).
- 기본값은 오늘 날짜입니다.
- 실행 시점 날짜 기준으로 생성된 통계를 조회합니다.
"""
)
async def get_daily_stats(
    job_name: str,
    date: str | None = None,  # 특정 날짜 입력 (YYYY-MM-DD 형식, 기본값: 오늘 날짜)
    db: Session = Depends(get_db)
):
    # 현재 날짜 계산 (서울 시간대)
    seoul_tz = pytz.timezone('Asia/Seoul')
    current_date = datetime.now(seoul_tz).date()
    
    # date가 None이면 현재 날짜로 설정
    if date is None:
        target_date = current_date
    else:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요.")
        
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
            # 특정 날짜의 데이터만 조회 (효율적인 쿼리)
            stats = db.query(WeeklySkillStat).filter(
                WeeklySkillStat.job_role_id == job_role.id,
                WeeklySkillStat.field_type == field_type,
                WeeklySkillStat.date == target_date
            ).order_by(
                WeeklySkillStat.count.desc(),
                WeeklySkillStat.skill.asc()
            ).all()
            
            # 응답 형식으로 변환
            formatted_stats = []
            for stat in stats:
                formatted_stats.append({
                    "week": stat.week,
                    "date": stat.date.isoformat(),
                    "skill": stat.skill,
                    "count": stat.count
                })
            
            all_stats[field_type] = formatted_stats
        
        return {
            "job_name": job_name,
            "field_types": field_types,
            "date": target_date.isoformat(),
            "stats": all_stats,
            "total_count": sum(len(stats) for stats in all_stats.values())
        }
        
    except Exception as e:
        logger.error(f"일간 스킬 통계 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"일간 통계 조회 중 오류가 발생했습니다: {str(e)}"
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
        
        # 2. 특정 필드 타입의 특정 주차 데이터 조회 (효율적인 쿼리)
        stats = db.query(WeeklySkillStat).filter(
            WeeklySkillStat.job_role_id == job_role.id,
            WeeklySkillStat.field_type == field_type,
            WeeklySkillStat.week == week
        ).order_by(
            WeeklySkillStat.count.desc(),
            WeeklySkillStat.skill.asc()
        ).all()
        
        # 3. 응답 형식으로 변환
        trend_data = []
        for stat in stats:
            trend_data.append({
                "week": stat.week,
                "date": stat.date.isoformat(),
                "skill": stat.skill,
                "count": stat.count,
                "date_label": f"Week {stat.week} - {stat.date.isoformat()}"
            })
        
        return {
            "job_name": job_name,
            "field_type": field_type,
            "week": week,
            "year": year,
            "trend_data": trend_data,
            "total_points": len(trend_data)
        }
        
    except Exception as e:
        logger.error(f"스킬 트렌드 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"트렌드 조회 중 오류가 발생했습니다: {str(e)}"
        ) 