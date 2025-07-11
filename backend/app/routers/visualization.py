from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app.models.job_post import JobPost
from app.models.job_required_skill import JobRequiredSkill
from pydantic import BaseModel

router = APIRouter(prefix="/visualization", tags=["Visualization"])

class WeeklySkillStat(BaseModel):
    year: int
    week: int
    skill: str
    count: int

    class Config:
        from_attributes = True

@router.get(
    "/weekly_skill_frequency",
    operation_id="weekly_skill_frequency",
    summary="직무별 주간 스킬 빈도 조회",
    description="""
선택한 **직무명(`job_name`)**과 분석 필드(`field`)에 대해, 최근 채용공고에서 추출된 **기술/키워드의 주별 등장 빈도**를 집계하여 반환합니다.

- **직무명**은 등록된 직무 테이블(`JobRequiredSkill`)의 `job_name` 값으로 입력해야 합니다.
- 입력된 `job_name`이 존재하지 않을 경우 404 에러가 반환됩니다.
- 분석 대상 필드(`field`)는 아래 중 하나여야 하며, 해당 필드는 채용공고(`JobPost`) 모델에 존재해야 합니다.
    - tech_stack, qualifications, preferences, required_skills, preferred_skills, essential_tech_stack
- 반환 데이터는 [연도, 주차, 스킬, 빈도] 형태의 리스트입니다.
- 워드클라우드, 트렌드 차트, 통계 등에 활용 가능합니다.

**응답 예시:**
```json
[
  { "year": 2025, "week": 28, "skill": "Python", "count": 12 },
  { "year": 2025, "week": 28, "skill": "SQL", "count": 7 },
  { "year": 2025, "week": 27, "skill": "Java", "count": 5 }
]
bash
복사
편집
""",
    response_model=List[WeeklySkillStat]
)
def weekly_skill_frequency(
    job_name: str = Query(..., description="조회할 직무명 (예: 백엔드 개발자)"),
    field: str = Query(
        "tech_stack",
        enum=[
            "tech_stack", "qualifications", "preferences",
            "required_skills", "preferred_skills", "essential_tech_stack"
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
        func.date_part('year', JobPost.posting_date).label('year'),
        func.date_part('week', JobPost.posting_date).label('week'),
        getattr(JobPost, field)
    ).filter(
        JobPost.job_required_skill_id == job_role_id
    ).all()

    # 3. 주별로 기술 키워드 카운트
    from collections import Counter, defaultdict
    week_skill_counter = defaultdict(Counter)
    for row in posts:
        year, week, field_value = int(row.year), int(row.week), row[2]
        if isinstance(field_value, str) and field_value.strip():
            # 여러 구분자 지원
            skills = [s.strip() for s in field_value.replace(';', ',').replace('/', ',').split(',') if s.strip()]
            week_skill_counter[(year, week)].update(skills)

    # 4. 결과 응답
    response = []
    for (year, week), counter in week_skill_counter.items():
        for skill, count in counter.items():
            response.append(WeeklySkillStat(
                year=year, week=week, skill=skill, count=count
            ))
    return response
