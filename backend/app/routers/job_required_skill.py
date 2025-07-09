from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.job_required_skill import JobRequiredSkill
from app.schemas.job_required_skill import JobRequiredSkillResponse, JobNameResponse

router = APIRouter(prefix="/job-skills", tags=["Job Required Skills"])

@router.get("/", summary="직무 기반 스킬 요구사항 조회", response_model=List[JobRequiredSkillResponse])
def get_job_required_skills(
    job_name: str = Query(None, description="직무 이름 (예: 백엔드 개발자)"),
    skill_type: str = Query(None, description="요구 유형 (예: 필수, 우대)"),
    db: Session = Depends(get_db)
):
    """
    관리자가 등록한 직무별 기술 요구사항 목록을 조회합니다.
    - 직무 이름 또는 요구 유형으로 필터링할 수 있습니다.
    - 예: 백엔드 개발자의 필수 스킬만 보기 등.
    """
    query = db.query(JobRequiredSkill)
    if job_name:
        query = query.filter(JobRequiredSkill.job_name == job_name)
    if skill_type:
        query = query.filter(JobRequiredSkill.skill_type == skill_type)
    return query.all()

@router.get("/job-names", response_model=List[JobNameResponse], summary="직무명 리스트 조회")
def get_job_names(db: Session = Depends(get_db)):
    """
    등록된 모든 직무명(name)만 리스트로 반환합니다.
    """
    job_names = db.query(JobRequiredSkill.job_name).distinct().all()  # ← name인지 job_name인지 모델 필드명 맞게!
    return [{"name": name[0]} for name in job_names]