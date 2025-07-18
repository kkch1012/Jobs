from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from starlette.responses import JSONResponse
from app.database import get_db
from app.models.job_post import JobPost
from app.models.job_required_skill import JobRequiredSkill
from app.schemas.visualization import WeeklySkillStat, ResumeSkillComparison
from app.utils.dependencies import get_current_user
from app.models.user_skill import UserSkill
from app.models.user import User
from app.models.certificate import Certificate
from app.services.gap_model import perform_gap_analysis_visualization
from app.services.weekly_stats_service import WeeklyStatsService
from app.models.weekly_skill_stat import WeeklySkillStat as WeeklySkillStatModel
from app.services.roadmap_model import get_roadmap_recommendations

router = APIRouter(prefix="/visualization", tags=["Visualization"])

@router.get(
    "/weekly_skill_frequency",
    operation_id="weekly_skill_frequency",
    summary="직무별 주간 스킬 빈도 조회",
    description="""
선택한 **직무명(`job_name`)**과 분석 필드(`field`)에 대해, 최근 채용공고에서 추출된 **기술/키워드의 주별 등장 빈도**를 집계하여 반환합니다.

- **직무명**은 등록된 직무 테이블(`JobRequiredSkill`)의 `job_name` 값으로 입력해야 합니다.
- 입력된 `job_name`이 존재하지 않을 경우 404 에러가 반환됩니다.
- 분석 대상 필드(`field`)는 아래 중 하나여야 하며, 해당 필드는 채용공고(`JobPost`) 모델에 존재해야 합니다.
    - tech_stack, qualifications, preferences, required_skills, preferred_skills
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
    db: Session = Depends(get_db)
):
    # 1. 직무명 → id 매핑
    job_role = db.query(JobRequiredSkill).filter(JobRequiredSkill.job_name == job_name).first()
    if not job_role:
        raise HTTPException(status_code=404, detail="해당 직무명이 존재하지 않습니다.")
    job_role_id = job_role.id

    # 2. 해당 직무id로 JobPost 필터링 & 주별 집계
    posts = db.query(
        JobPost.posting_date,
        getattr(JobPost, field)
    ).filter(
        JobPost.job_required_skill_id == job_role_id
    ).all()

    # 3. 주별로 기술 키워드 카운트 (ISO 주차 사용)
    from collections import Counter, defaultdict
    from datetime import datetime
    week_skill_counter = defaultdict(Counter)
    for row in posts:
        posting_date, field_value = row.posting_date, row[1]
        
        # ISO 주차 계산
        week_number = posting_date.isocalendar()[1]  # ISO 주차
        posting_date_only = posting_date.date()  # 날짜만 추출
        
        skills = []
        
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
        
        if skills:
            week_skill_counter[(week_number, posting_date_only)].update(skills)

    # 4. 결과 응답
    response = []
    for (week, date_val), counter in week_skill_counter.items():
        for skill, count in counter.items():
            response.append(WeeklySkillStat(
                week=week, date=date_val, skill=skill, count=count
            ))
    # count 기준 내림차순 정렬
    response = sorted(response, key=lambda x: x.count, reverse=True)
    return response

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

    # 2. 직무별 주간 스킬 빈도 데이터 조회 (기존 함수 재활용)
    job_role = db.query(JobRequiredSkill).filter(JobRequiredSkill.job_name == job_name).first()
    if not job_role:
        raise HTTPException(status_code=404, detail="해당 직무명이 존재하지 않습니다.")
    job_role_id = job_role.id
    posts = db.query(
        JobPost.posting_date,
        getattr(JobPost, field)
    ).filter(
        JobPost.job_required_skill_id == job_role_id
    ).all()
    from collections import Counter, defaultdict
    from datetime import datetime
    week_skill_counter = defaultdict(Counter)
    for row in posts:
        posting_date, field_value = row.posting_date, row[1]
        
        # ISO 주차와 날짜 계산
        week_number = posting_date.isocalendar()[1]  # ISO 주차
        posting_date_only = posting_date.date()  # 날짜만 추출
        
        skills = []
        
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
            week_skill_counter[(week_number, posting_date_only)].update(limited_skills)
    # 3. 강점/약점 비교 및 응답 생성
    response = []
    for (week, date_val), counter in week_skill_counter.items():
        for skill, count in counter.items():
            status = "강점" if skill in my_skill_set else "약점"
            response.append(ResumeSkillComparison(
                skill=skill, count=count, status=status, week=week, date=date_val
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

        # 1. 프론트에 보여줄 자연어 결과
        gap_result = result["gap_result"]

        # 2. 내부 To-Do 시스템으로 보낼 Top 5 스킬
        top_skills = result["top_skills"]
        # 예시: 추후 비동기로 보내거나 DB에 저장
        # send_to_todo(user_id, top_skills)

        return {
            "gap_result": gap_result,      # 프론트에 출력할 자연어
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
weekly_skill_stats 테이블에서 스킬명을 검색하여 해당 스킬의 통계 정보를 반환합니다.
- 부분 검색을 지원합니다 (예: "aw" 검색 시 "aws" 포함된 스킬들이 검색됨)
- count, 직무명, field_type 정보를 함께 반환합니다.

**응답 예시:**
```json
[
  {
    "skill": "AWS",
    "count": 15,
    "job_name": "백엔드 개발자",
    "field_type": "tech_stack",
    "week": 29,
    "date": "2025-01-15"
  }
]
```
""",
    response_model=List[Dict[str, Any]]
)
def skill_search(
    skill_name: str = Query(..., description="검색할 스킬명 (부분 검색 지원)"),
    db: Session = Depends(get_db)
):
    """
    weekly_skill_stats 테이블에서 스킬명을 검색합니다.
    """
    try:
        # 스킬명으로 검색 (대소문자 구분 없이 부분 검색)
        stats = db.query(
            WeeklySkillStatModel.skill,
            WeeklySkillStatModel.count,
            WeeklySkillStatModel.field_type,
            WeeklySkillStatModel.week,
            WeeklySkillStatModel.date,
            JobRequiredSkill.job_name
        ).join(
            JobRequiredSkill,
            WeeklySkillStatModel.job_role_id == JobRequiredSkill.id
        ).filter(
            WeeklySkillStatModel.skill.ilike(f"%{skill_name}%")
        ).order_by(
            WeeklySkillStatModel.count.desc(),
            WeeklySkillStatModel.skill.asc()
        ).all()
        
        # 응답 형식으로 변환
        result = []
        for stat in stats:
            result.append({
                "skill": stat.skill,
                "count": stat.count,
                "job_name": stat.job_name,
                "field_type": stat.field_type,
                "week": stat.week,
                "date": stat.date.isoformat() if stat.date else None
            })
        
        return result
        
    except Exception as e:
        import traceback
        error_detail = f"스킬 검색 중 오류가 발생했습니다: {str(e)}\n\n상세 정보:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

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
