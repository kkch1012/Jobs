from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from starlette.responses import JSONResponse
from app.database import get_db
from app.models.job_post import JobPost
from app.models.job_required_skill import JobRequiredSkill
from app.schemas.visualization import WeeklySkillStat, ResumeSkillComparison
from app.utils.dependencies import get_current_user
from app.models.user_skill import UserSkill
from app.models.user import User
from app.services.gap_model import perform_gap_analysis_visualization

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

    # 3. 주별로 기술 키워드 카운트 (연속 주차 사용)
    from collections import Counter, defaultdict
    from datetime import datetime
    week_skill_counter = defaultdict(Counter)
    for row in posts:
        posting_date, field_value = row.posting_date, row[1]
        
        # 연속 주차 계산 (2020년 1월 1일부터 시작)
        base_date = datetime(2020, 1, 1)
        days_diff = (posting_date - base_date).days
        week_number = (days_diff // 7) + 1  # 1부터 시작하는 연속 주차
        
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
            week_skill_counter[week_number].update(skills)

    # 4. 결과 응답
    response = []
    for week_day, counter in week_skill_counter.items():
        for skill, count in counter.items():
            response.append(WeeklySkillStat(
                week_day=week_day, skill=skill, count=count
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
        
        # 주차.요일 계산 (2020년 1월 1일부터 시작)
        base_date = datetime(2020, 1, 1)
        days_diff = (posting_date - base_date).days
        week_number = (days_diff // 7) + 1  # 1부터 시작하는 연속 주차
        day_of_week = posting_date.isoweekday()  # 월요일=1, 일요일=7
        week_day = f"{week_number}.{day_of_week}"
        
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
            week_skill_counter[week_day].update(limited_skills)
    # 3. 강점/약점 비교 및 응답 생성
    response = []
    for week_day, counter in week_skill_counter.items():
        for skill, count in counter.items():
            status = "강점" if skill in my_skill_set else "약점"
            response.append(ResumeSkillComparison(
                skill=skill, count=count, status=status, week_day=week_day
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
        result = perform_gap_analysis(user_id, category, db=db)

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
