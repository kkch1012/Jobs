from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.job_post import JobPost
from app.models.job_required_skill import JobRequiredSkill
from typing import List
router = APIRouter(prefix="/visualization", tags=["Visualization"])

# 1. 주별 스킬 빈도
@router.get(
    "/weekly_skill_frequency",
    summary="직무별 주간 스킬 빈도 조회",
    description="""
선택한 직무(`job_name`)와 분석 필드(`field`)에 대해 최근 채용공고의 해당 항목(예: 기술스택, 자격요건 등)에서 추출한 **기술/키워드의 주별 빈도**를 집계하여 반환합니다.

- 프론트엔드는 `job_name`(직무명)과 `field`(분석 필드: tech_stack, qualifications, preferences, required_skills, preferred_skills, essential_tech_stack 중 하나)를 쿼리 파라미터로 전달합니다.
- 반환 데이터는 연도, 주차, 키워드/스킬, 등장 빈도(count)로 구성된 리스트입니다.
- 워드클라우드, 트렌드 차트 등 시각화에 바로 활용할 수 있습니다.

**응답 예시**
```json
[
  { "year": 2025, "week": 28, "skill": "Python", "count": 12 },
  { "year": 2025, "week": 28, "skill": "SQL", "count": 7 },
  { "year": 2025, "week": 27, "skill": "Java", "count": 5 }
]
""")
def weekly_skill_frequency(
    job_name: str,
    field: str = Query("tech_stack", enum=["tech_stack", "qualifications", "preferences", "required_skills", "preferred_skills", "essential_tech_stack"]),
    db: Session = Depends(get_db)
):
    valid_fields = [
        "tech_stack", "qualifications", "preferences",
        "required_skills", "preferred_skills", "essential_tech_stack"
    ]
    if field not in valid_fields:
        raise HTTPException(status_code=400, detail="지원하지 않는 field입니다.")

    posts = db.query(
        func.date_part('year', JobPost.posting_date).label('year'),
        func.date_part('week', JobPost.posting_date).label('week'),
        getattr(JobPost, field)
    ).filter(
        JobPost.title.ilike(f"%{job_name}%")
    ).all()

    from collections import Counter, defaultdict
    week_skill_counter = defaultdict(Counter)
    for row in posts:
        year, week, field_value = int(row.year), int(row.week), row[2]
        if isinstance(field_value, str) and field_value.strip():
            skills = [s.strip() for s in field_value.replace(';', ',').replace('/', ',').split(',') if s.strip()]
            week_skill_counter[(year, week)].update(skills)

    response = []
    for (year, week), counter in week_skill_counter.items():
        for skill, count in counter.items():
            response.append({
                "year": year,
                "week": week,
                "skill": skill,
                "count": count
            })
    return response