from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from starlette.responses import JSONResponse
from datetime import datetime
from collections import Counter
import pytz
from app.database import get_db
from app.models.job_required_skill import JobRequiredSkill
from app.models.job_post import JobPost
from app.models.user_skill import UserSkill
from app.schemas.visualization import WeeklySkillStat, ResumeSkillComparison
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.services.gap_model import perform_gap_analysis_visualization
from app.services.weekly_stats_service import WeeklyStatsService
from app.models.weekly_skill_stat import WeeklySkillStat as WeeklySkillStatModel
from app.services.roadmap_model import get_roadmap_recommendations
from app.services.statistics_service import StatisticsService
from app.utils.text_utils import clean_markdown_text
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visualization", tags=["Visualization"])

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
    "/daily/{job_name}",
    summary="일간 스킬 통계 조회",
    description="""
특정 직무의 일간 스킬 통계를 조회합니다.

- field_type 파라미터로 분석할 필드를 선택할 수 있습니다.
- date 파라미터로 특정 날짜를 조회할 수 있습니다 (YYYY-MM-DD 형식).
- 기본값은 오늘 날짜입니다.
- 미리 계산된 통계 데이터를 빠르게 조회합니다.
- 실행 시점 날짜 기준으로 생성된 통계를 조회합니다.
"""
)
async def get_daily_stats(
    job_name: str,
    field_type: str = Query(
        "tech_stack",
        enum=["tech_stack", "required_skills", "preferred_skills", "main_tasks_skills"],
        description="분석할 필드 타입"
    ),
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
        job_role = db.query(JobRequiredSkill).filter(
            JobRequiredSkill.job_name == job_name
        ).first()
        
        if not job_role:
            raise HTTPException(status_code=404, detail=f"직무 '{job_name}'을 찾을 수 없습니다.")
        
        # 2. 해당 필드의 일간 통계 조회
        stats = db.query(WeeklySkillStatModel).filter(
            WeeklySkillStatModel.job_role_id == job_role.id,
            WeeklySkillStatModel.field_type == field_type,
            WeeklySkillStatModel.date == target_date
        ).order_by(
            WeeklySkillStatModel.count.desc(),
            WeeklySkillStatModel.skill.asc()
        ).all()
        
        # 3. 응답 형식으로 변환
        result = []
        for stat in stats:
            result.append({
                "week": stat.week,
                "date": stat.date.isoformat() if stat.date else None,
                "skill": stat.skill,
                "count": stat.count,
                "field_type": stat.field_type
            })
        
        return result
        
    except Exception as e:
        logger.error(f"일간 스킬 통계 조회 실패: {str(e)}")
        logger.error(f"요청된 직무명: {job_name}")
        logger.error(f"요청된 필드 타입: {field_type}")
        logger.error(f"요청된 날짜: {date}")
        raise HTTPException(
            status_code=500,
            detail=f"일간 통계 조회 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/weekly_stats/{job_name}",
    summary="주간 스킬 통계 조회 (평균 계산)",
    description="""
특정 직무의 주간 스킬 통계를 조회합니다.
- field_type 파라미터로 분석할 필드를 선택할 수 있습니다.
- week 파라미터로 특정 주차를 조회할 수 있습니다.
- 기본값은 현재 주차입니다.
- 같은 주차의 여러 날짜 데이터를 스킬별로 그룹화하여 평균값을 계산합니다.
- count는 해당 주차의 일별 count 평균값입니다.
- total_count는 해당 주차의 일별 count 총합입니다.
- date_count는 해당 주차에 데이터가 있는 날짜 수입니다.
""",
    response_model=List[Dict[str, Any]]
)
def get_weekly_stats_by_field(
    job_name: str,
    field_type: str = Query(
        "tech_stack",
        enum=["tech_stack", "required_skills", "preferred_skills", "main_tasks_skills"],
        description="분석할 필드 타입"
    ),
    week: Optional[int] = Query(None, description="특정 주차 (기본값: 현재 주차)"),
    db: Session = Depends(get_db)
):
    """특정 필드의 주간 스킬 통계를 조회합니다."""
    try:
        # 1. 직무 조회
        job_role = db.query(JobRequiredSkill).filter(
            JobRequiredSkill.job_name == job_name
        ).first()
        
        if not job_role:
            raise HTTPException(status_code=404, detail=f"직무 '{job_name}'을 찾을 수 없습니다.")
        
        # 2. 주차 설정
        if week is None:
            kst = pytz.timezone('Asia/Seoul')
            current_date = datetime.now(kst)
            week = current_date.isocalendar()[1]
        
        # 3. 해당 필드의 주간 통계 조회 (SQL 집계 사용)
        from sqlalchemy import func
        
        # 같은 주차의 여러 날짜 데이터를 스킬별로 그룹화하여 평균 계산
        aggregated_stats = db.query(
            WeeklySkillStatModel.skill,
            func.avg(WeeklySkillStatModel.count).label('avg_count'),
            func.sum(WeeklySkillStatModel.count).label('total_count'),
            func.count(WeeklySkillStatModel.date).label('date_count')
        ).filter(
            WeeklySkillStatModel.job_role_id == job_role.id,
            WeeklySkillStatModel.field_type == field_type,
            WeeklySkillStatModel.week == week
        ).group_by(
            WeeklySkillStatModel.skill
        ).order_by(
            func.avg(WeeklySkillStatModel.count).desc(),
            WeeklySkillStatModel.skill.asc()
        ).all()
        
        # 4. 응답 형식으로 변환 (평균값 사용)
        result = []
        for stat in aggregated_stats:
            result.append({
                "week": week,
                "date": None,  # 주간 평균이므로 개별 날짜는 None
                "skill": stat.skill,
                "count": round(stat.avg_count, 2),  # 평균값을 소수점 2자리까지 반올림
                "field_type": field_type,
                "total_count": stat.total_count,  # 총합 (참고용)
                "date_count": stat.date_count     # 데이터가 있는 날짜 수 (참고용)
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주간 스킬 통계 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"주간 통계 조회 중 오류가 발생했습니다: {str(e)}")

@router.get(
    "/weekly_skill_frequency",
    operation_id="weekly_skill_frequency",
    summary="직무별 주간 스킬 빈도 조회 (주차 범위 지정)",
    description="""
선택한 **직무명(`job_name`)**과 분석 필드(`field`)에 대해, 지정된 주차 범위의 채용공고에서 추출된 **기술/키워드의 주별 등장 빈도**를 집계하여 반환합니다.

- **직무명**은 등록된 직무 테이블(`JobRequiredSkill`)의 `job_name` 값으로 입력해야 합니다.
- 입력된 `job_name`이 존재하지 않을 경우 404 에러가 반환됩니다.
- 분석 대상 필드(`field`)는 아래 중 하나여야 하며, 해당 필드는 채용공고(`JobPost`) 모델에 존재해야 합니다.
    - tech_stack, qualifications, preferences, required_skills, preferred_skills
- `start_week`, `end_week`, `year` 파라미터로 조회할 주차 범위를 지정할 수 있습니다.
- 반환 데이터는 [연도, 주차, 스킬, 빈도] 형태의 리스트입니다.
- 워드클라우드, 트렌드 차트, 통계 등에 활용 가능합니다.

**응답 예시:**
```json
[
  { "year": 2025, "week": 28, "skill": "Python", "count": 12 },
  { "year": 2025, "week": 28, "skill": "SQL", "count": 7 },
  { "year": 2025, "week": 27, "skill": "Java", "count": 5 }
]
""",
    response_model=List[WeeklySkillStat]
)
def weekly_skill_frequency(
    job_name: str = Query(..., description="조회할 직무명 (예: 백엔드 개발자)"),
    field: str = Query(
        "tech_stack",
        enum=[
            "tech_stack", "qualifications", "preferences",
            "required_skills", "preferred_skills"
        ],
        description="분석 대상 필드명 (채용공고 모델에 존재하는 컬럼 중 선택)"
    ),
    start_week: int = Query(..., ge=1, le=53, description="시작 주차 (1-53)"),
    end_week: int = Query(..., ge=1, le=53, description="마감 주차 (1-53, start_week보다 크거나 같아야 함)"),
    year: int = Query(..., description="조회할 연도"),
    db: Session = Depends(get_db)
):
    try:
        # StatisticsService 사용
        result = StatisticsService.get_weekly_skill_frequency_range(
            job_name, start_week, end_week, year, field, db
        )
        
        # 응답 형식 변환
        response = []
        for week_data in result:
            week = week_data["week"]
            for skill_data in week_data["skills"]:
                response.append(WeeklySkillStat(
                    year=year,
                    week=week,
                    skill=skill_data["skill_name"],
                    count=skill_data["frequency"]
                ))
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")

@router.get(
    "/weekly_skill_frequency_current",
    operation_id="weekly_skill_frequency_current",
    summary="직무별 현재 주차 스킬 빈도 조회",
    description="""
선택한 **직무명(`job_name`)**과 분석 필드(`field`)에 대해, **현재 주차의 채용공고**에서 추출된 **기술/키워드의 등장 빈도**를 집계하여 반환합니다.

- **직무명**은 등록된 직무 테이블(`JobRequiredSkill`)의 `job_name` 값으로 입력해야 합니다.
- 입력된 `job_name`이 존재하지 않을 경우 404 에러가 반환됩니다.
- 분석 대상 필드(`field`)는 아래 중 하나여야 하며, 해당 필드는 채용공고(`JobPost`) 모델에 존재해야 합니다.
    - tech_stack, qualifications, preferences, required_skills, preferred_skills
- **현재 주차만** 조회하여 실시간 트렌드를 파악할 수 있습니다.
- 반환 데이터는 [연도, 주차, 스킬, 빈도] 형태의 리스트입니다.

**응답 예시:**
```json
[
  { "year": 2025, "week": 29, "skill": "Python", "count": 12 },
  { "year": 2025, "week": 29, "skill": "SQL", "count": 7 },
  { "year": 2025, "week": 29, "skill": "Java", "count": 5 }
]
""",
    response_model=List[WeeklySkillStat]
)
def weekly_skill_frequency_current(
    job_name: str = Query(..., description="조회할 직무명 (예: 백엔드 개발자)"),
    field: str = Query(
        "tech_stack",
        enum=[
            "tech_stack", "qualifications", "preferences",
            "required_skills", "preferred_skills"
        ],
        description="분석 대상 필드명 (채용공고 모델에 존재하는 컬럼 중 선택)"
    ),
    db: Session = Depends(get_db)
):
    try:
        # StatisticsService 사용
        result = StatisticsService.get_current_weekly_skill_frequency(job_name, field, db)
        
        # 응답 형식 변환
        response = []
        kst = pytz.timezone('Asia/Seoul')
        current_date = datetime.now(kst)
        year = current_date.year
        
        for week_data in result:
            week = week_data["week"]
            for skill_data in week_data["skills"]:
                response.append(WeeklySkillStat(
                    year=year,
                    week=week,
                    skill=skill_data["skill_name"],
                    count=skill_data["frequency"]
                ))
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")

@router.get(
    "/weekly_skill_frequency_comparison",
    operation_id="weekly_skill_frequency_comparison",
    summary="직무별 2주차 스킬 빈도 비교 분석",
    description="""
선택한 **직무명(`job_name`)**과 분석 필드(`field`)에 대해, **2개 주차의 스킬 빈도 차이**를 분석하여 반환합니다.

- **직무명**은 등록된 직무 테이블(`JobRequiredSkill`)의 `job_name` 값으로 입력해야 합니다.
- 입력된 `job_name`이 존재하지 않을 경우 404 에러가 반환됩니다.
- 분석 대상 필드(`field`)는 아래 중 하나여야 하며, 해당 필드는 채용공고(`JobPost`) 모델에 존재해야 합니다.
    - tech_stack, qualifications, preferences, required_skills, preferred_skills
- `week1`, `week2`, `year` 파라미터로 비교할 2개 주차를 지정할 수 있습니다.
- 반환 데이터는 전체 스킬 목록과 함께 다음 4개 필터링된 결과를 포함합니다:
    - **biggest_difference**: 절대값 차이가 가장 큰 스킬
    - **smallest_difference**: 절대값 차이가 가장 작은 스킬
    - **biggest_percentage**: 퍼센트 변화가 가장 큰 스킬
    - **smallest_percentage**: 퍼센트 변화가 가장 작은 스킬

**응답 예시:**
```json
{
  "all_skills": [
    { "skill": "Python", "week1_count": 15, "week2_count": 20, "difference": 5, "percentage_change": 33.33 }
  ],
  "biggest_difference": { "skill": "Java", "week1_count": 5, "week2_count": 15, "difference": 10, "percentage_change": 200.0 },
  "smallest_difference": { "skill": "SQL", "week1_count": 8, "week2_count": 8, "difference": 0, "percentage_change": 0.0 },
  "biggest_percentage": { "skill": "React", "week1_count": 2, "week2_count": 10, "difference": 8, "percentage_change": 400.0 },
  "smallest_percentage": { "skill": "SQL", "week1_count": 8, "week2_count": 8, "difference": 0, "percentage_change": 0.0 }
}
""",
    response_model=Dict[str, Any]
)
def weekly_skill_frequency_comparison(
    job_name: str = Query(..., description="조회할 직무명 (예: 백엔드 개발자)"),
    field: str = Query(
        "tech_stack",
        enum=[
            "tech_stack", "qualifications", "preferences",
            "required_skills", "preferred_skills"
        ],
        description="분석 대상 필드명 (채용공고 모델에 존재하는 컬럼 중 선택)"
    ),
    week1: int = Query(..., ge=1, le=53, description="첫 번째 주차 (1-53)"),
    week2: int = Query(..., ge=1, le=53, description="두 번째 주차 (1-53)"),
    year: int = Query(..., description="조회할 연도"),
    db: Session = Depends(get_db)
):
    try:
        # StatisticsService 사용하여 각 주차별 데이터 조회
        week1_data = StatisticsService.get_weekly_skill_frequency_range(
            job_name, week1, week1, year, field, db
        )
        week2_data = StatisticsService.get_weekly_skill_frequency_range(
            job_name, week2, week2, year, field, db
        )
        
        # 스킬별 데이터 병합
        skill_comparison = {}
        
        # week1 데이터 처리
        for week_data in week1_data:
            for skill_data in week_data["skills"]:
                skill_name = skill_data["skill_name"]
                if skill_name not in skill_comparison:
                    skill_comparison[skill_name] = {"week1_count": 0, "week2_count": 0}
                skill_comparison[skill_name]["week1_count"] = skill_data["frequency"]
        
        # week2 데이터 처리
        for week_data in week2_data:
            for skill_data in week_data["skills"]:
                skill_name = skill_data["skill_name"]
                if skill_name not in skill_comparison:
                    skill_comparison[skill_name] = {"week1_count": 0, "week2_count": 0}
                skill_comparison[skill_name]["week2_count"] = skill_data["frequency"]
        
        # 차이와 퍼센트 계산
        all_skills = []
        for skill_name, counts in skill_comparison.items():
            week1_count = counts["week1_count"]
            week2_count = counts["week2_count"]
            difference = week2_count - week1_count
            
            # 퍼센트 변화 계산 (0으로 나누기 방지)
            if week1_count == 0:
                percentage_change = 100.0 if week2_count > 0 else 0.0
            else:
                percentage_change = (difference / week1_count) * 100
            
            skill_info = {
                "skill": skill_name,
                "week1_count": week1_count,
                "week2_count": week2_count,
                "difference": difference,
                "percentage_change": round(percentage_change, 2)
            }
            all_skills.append(skill_info)
        
        # 필터링된 결과 찾기
        if not all_skills:
            return {
                "all_skills": [],
                "biggest_difference": None,
                "smallest_difference": None,
                "biggest_percentage": None,
                "smallest_percentage": None
            }
        
        # 절대값 차이 기준 정렬
        sorted_by_difference = sorted(all_skills, key=lambda x: abs(x["difference"]), reverse=True)
        biggest_difference = sorted_by_difference[0]
        smallest_difference = sorted_by_difference[-1]
        
        # 퍼센트 변화 기준 정렬
        sorted_by_percentage = sorted(all_skills, key=lambda x: abs(x["percentage_change"]), reverse=True)
        biggest_percentage = sorted_by_percentage[0]
        smallest_percentage = sorted_by_percentage[-1]
        
        return {
            "all_skills": all_skills,
            "biggest_difference": biggest_difference,
            "smallest_difference": smallest_difference,
            "biggest_percentage": biggest_percentage,
            "smallest_percentage": smallest_percentage
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스킬 비교 분석 실패: {str(e)}")

@router.get(
    "/resume_vs_job_skill_trend",
    summary="내 이력서 vs 직무별 주간 스킬 빈도 비교",
    description="내 이력서(보유 스킬)와 선택한 직무의 주간 스킬 빈도 통계를 비교하여 강점(보유)/약점(미보유) 스킬을 시각화할 수 있도록 반환합니다.",
    response_model=List[ResumeSkillComparison]
)
async def resume_vs_job_skill_trend(
    job_name: str = Query(..., description="비교할 직무명 (예: 백엔드 개발자)"),
    field: str = Query(
        "tech_stack",
        enum=[
            "tech_stack", "qualifications", "preferences",
            "required_skills", "preferred_skills"
        ],
        description="분석 대상 필드명 (채용공고 모델에 존재하는 컬럼 중 선택)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. 내 이력서(보유 스킬) 조회
    user_skills = db.query(UserSkill).filter(UserSkill.user_id == current_user.id).all()
    my_skill_set = set()
    for us in user_skills:
        if hasattr(us, 'skill') and us.skill and hasattr(us.skill, 'name'):
            my_skill_set.add(us.skill.name)
        elif hasattr(us, 'skill_name'):
            my_skill_set.add(us.skill_name)

    # 2. 현재 주차 계산
    seoul_tz = pytz.timezone('Asia/Seoul')
    current_date = datetime.now(seoul_tz)
    current_week = current_date.isocalendar()[1]  # 현재 ISO 주차
    
    # 3. 직무별 현재 주차 스킬 빈도 데이터 조회
    job_role = db.query(JobRequiredSkill).filter(JobRequiredSkill.job_name == job_name).first()
    if not job_role:
        raise HTTPException(status_code=404, detail="해당 직무명이 존재하지 않습니다.")
    job_role_id = job_role.id
    posts = db.query(
        JobPost.posting_date,
        getattr(JobPost, field)
    ).filter(
        JobPost.job_required_skill_id == job_role_id,
        JobPost.is_expired.is_(None) | JobPost.is_expired.is_(False)
    ).all()
    
    skill_counter = Counter()
    for row in posts:
        posting_date, field_value = row.posting_date, row[1]
        
        # 현재 주차의 공고만 처리
        post_week = posting_date.isocalendar()[1]
        if post_week == current_week:
                        # 필드 타입에 따른 처리
            if field == "tech_stack":
                # tech_stack은 문자열 필드
                if isinstance(field_value, str) and field_value.strip():
                    skills = [s.strip() for s in field_value.replace(';', ',').replace('/', ',').split(',') if s.strip()]
            else:
                # required_skills, preferred_skills, main_tasks_skills는 JSONB 필드
                if isinstance(field_value, list):
                    skills = [str(skill).strip() for skill in field_value if skill]
                elif isinstance(field_value, str) and field_value.strip():
                    # JSON 문자열인 경우 파싱 시도
                    try:
                        import json
                        parsed = json.loads(field_value)
                        if isinstance(parsed, list):
                            skills = [str(skill).strip() for skill in parsed if skill]
                    except:
                        # 파싱 실패 시 문자열로 처리
                        skills = [s.strip() for s in field_value.replace(';', ',').replace('/', ',').split(',') if s.strip()]
            
            # 스킬명 길이 제한 (500자)
            if skills:
                limited_skills = []
                for skill in skills:
                    if len(skill) > 500:
                        skill = skill[:497] + "..."  # 500자로 제한
                    limited_skills.append(skill)
                skill_counter.update(limited_skills)
    # 4. 강점/약점 비교 및 응답 생성 (현재 주차만)
    response = []
    for skill, count in skill_counter.items():
        status = "강점" if skill in my_skill_set else "약점"
        response.append(ResumeSkillComparison(
            skill=skill, count=count, status=status, week=current_week, date=current_date.date()
        ))
    return response

@router.get("/gap-analysis", response_class=JSONResponse,
    summary="GPT 기반 갭차이 분석",
    description="""
사용자의 이력 정보와 선택한 직무(카테고리)를 바탕으로 GPT(OpenRouter) 기반 갭차이 분석을 수행합니다.\n
- 분석 결과는 자연어 설명(gap_result)과 부족 역량 Top 5 리스트(top_skills)로 구성됩니다.\n
- 프론트엔드는 gap_result를 출력용으로, top_skills를 투두리스트 등 내부 활용에 사용할 수 있습니다.\n
- LLM 호출 실패 시 에러 메시지가 반환될 수 있습니다.
"""
)
def gap_analysis_endpoint(
    category: str = Query(..., description="직무 카테고리 (예: 프론트엔드 개발자)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    사용자의 이력 정보와 선택한 직무를 바탕으로 LLM 기반 갭차이 분석을 수행합니다.
    분석 결과는 자연어 설명과 부족 역량 Top 5 리스트로 구성됩니다.
    """
    try:
        user_id = getattr(current_user, "id", None)
        if user_id is None:
            raise HTTPException(status_code=400, detail="유저 ID를 확인할 수 없습니다.")
        if hasattr(user_id, "__int__"):
            user_id = int(user_id)
        if not isinstance(user_id, int):
            raise HTTPException(status_code=400, detail="유저 ID를 확인할 수 없습니다.")
        result = perform_gap_analysis_visualization(user_id, category, db=db)

        # 1. 프론트에 보여줄 자연어 결과 (마크다운 형식 제거)
        gap_result = result["gap_result"]
        
        # 마크다운 형식 제거
        gap_result = clean_markdown_text(gap_result)

        # 2. 내부 To-Do 시스템으로 보낼 Top 5 스킬
        top_skills = result["top_skills"]
        # 예시: 추후 비동기로 보내거나 DB에 저장
        # send_to_todo(user_id, top_skills)

        return {
            "gap_result": gap_result,      # 프론트에 출력할 자연어 (마크다운 제거됨)
            "top_skills": top_skills       # 프론트가 투두 리스트로 활용 가능
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        error_detail = f"갭 분석 중 오류가 발생했습니다: {str(e)}\n\n상세 정보:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

@router.get(
    "/skill_search",
    summary="스킬명 검색",
    description="""
스킬명으로 검색하여 직무별 스킬과 사용자 스킬 정보를 반환합니다.
- 부분 검색을 지원합니다 (예: "aw" 검색 시 "aws" 포함된 스킬들이 검색됨)
- 직무별 스킬과 사용자 스킬 정보를 함께 반환합니다.

**응답 예시:**
```json
{
  "job_skills": [
    {
      "skill_name": "AWS",
      "job_name": "백엔드 개발자",
      "importance": 5
    }
  ],
  "user_skills": [
    {
      "skill_name": "AWS",
      "user_id": 1,
      "proficiency_level": 3
    }
  ]
}
```
""",
    response_model=Dict[str, List[Dict[str, Any]]]
)
def skill_search(
    skill_name: str = Query(..., description="검색할 스킬명 (부분 검색 지원)"),
    db: Session = Depends(get_db)
):
    """
    스킬명으로 검색하여 직무별 스킬과 사용자 스킬 정보를 반환합니다.
    """
    try:
        result = StatisticsService.search_skills_by_keyword(skill_name, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스킬 검색 실패: {str(e)}")

@router.get(
    "/roadmap_recommendations",
    summary="로드맵 추천",
    description="""
사용자의 갭 분석 결과를 바탕으로 맞춤형 로드맵을 추천합니다.

- 갭 분석을 통해 부족한 스킬을 파악
- 트렌드 스킬과 사용자 스킬을 비교하여 점수 계산
- 점수가 높은 로드맵을 우선적으로 추천
- limit 파라미터로 각 타입별 추천 개수 조절 가능 (기본값: 10개씩, 총 20개)
- 부트캠프 limit개 + 강의 limit개를 반환
- type 파라미터로 부트캠프/강의 필터링 가능
""",
    response_model=List[Dict[str, Any]]
)
async def get_roadmap_recommendations_endpoint(
    category: str = Query(..., description="직무 카테고리 (예: 프론트엔드 개발자)"),
    limit: int = Query(10, description="각 타입별 추천받을 로드맵 개수 (최대 20개씩, 총 40개)"),
    type: Optional[str] = Query(None, description="필터링할 타입 (예: 부트캠프, 강의)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    사용자에게 맞는 로드맵을 추천합니다.
    """
    try:
        # limit 검증
        if limit > 20:
            limit = 20
        elif limit < 1:
            limit = 1
            
        user_id = getattr(current_user, "id", None)
        if user_id is None:
            raise HTTPException(status_code=400, detail="사용자 ID를 확인할 수 없습니다.")
        
        # 1. 갭 분석 수행
        gap_analysis_result = perform_gap_analysis_visualization(user_id, category, db)
        
        # 2. 로드맵 추천 수행
        recommended_roadmaps = get_roadmap_recommendations(
            user_id=user_id,
            category=category,
            gap_result_text=gap_analysis_result["gap_result"],
            db=db,
            limit=limit
        )
        
        # 3. type별 필터링
        if type:
            filtered_roadmaps = [roadmap for roadmap in recommended_roadmaps if roadmap.get('type') == type]
            return filtered_roadmaps
        
        return recommended_roadmaps
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        error_detail = f"로드맵 추천 중 오류가 발생했습니다: {str(e)}\n\n상세 정보:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

@router.get(
    "/roadmap_recommendations/direct",
    summary="직접 갭 분석 결과로 로드맵 추천",
    description="""
이미 수행된 갭 분석 결과를 직접 입력받아 로드맵을 추천합니다.

- 갭 분석 결과 텍스트를 직접 입력
- 별도의 갭 분석 과정 없이 바로 로드맵 추천
- 기존 갭 분석 결과를 재활용할 때 유용
- limit 파라미터로 각 타입별 추천 개수 조절 가능 (기본값: 10개씩, 총 20개)
- 부트캠프 limit개 + 강의 limit개를 반환
- type 파라미터로 부트캠프/강의 필터링 가능
""",
    response_model=List[Dict[str, Any]]
)
async def get_roadmap_recommendations_direct(
    category: str = Query(..., description="직무 카테고리 (예: 프론트엔드 개발자)"),
    gap_result_text: str = Query(..., description="갭 분석 결과 텍스트"),
    limit: int = Query(10, description="각 타입별 추천받을 로드맵 개수 (최대 20개씩, 총 40개)"),
    type: Optional[str] = Query(None, description="필터링할 타입 (예: 부트캠프, 강의)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    직접 입력된 갭 분석 결과로 로드맵을 추천합니다.
    """
    try:
        # limit 검증
        if limit > 20:
            limit = 20
        elif limit < 1:
            limit = 1
            
        user_id = getattr(current_user, "id", None)
        if user_id is None:
            raise HTTPException(status_code=400, detail="사용자 ID를 확인할 수 없습니다.")
        
        # 로드맵 추천 수행
        recommended_roadmaps = get_roadmap_recommendations(
            user_id=user_id,
            category=category,
            gap_result_text=gap_result_text,
            db=db,
            limit=limit
        )
        
        # type별 필터링
        if type:
            filtered_roadmaps = [roadmap for roadmap in recommended_roadmaps if roadmap.get('type') == type]
            return filtered_roadmaps
        
        return recommended_roadmaps
        
    except Exception as e:
        import traceback
        error_detail = f"로드맵 추천 중 오류가 발생했습니다: {str(e)}\n\n상세 정보:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)
