from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.job_required_skill import JobRequiredSkill
from app.schemas.job_required_skill import JobNameResponse

router = APIRouter(prefix="/job-skills", tags=["Job Required Skills"])

@router.get(
    "/job-names",
    operation_id="get_job_names",
    response_model=List[JobNameResponse],
    summary="직무명(이름만) 리스트 조회"
)
def get_job_names(db: Session = Depends(get_db)):
    """
    등록된 모든 직무명(name) 리스트를 반환합니다.
    (중복 불가능, unique constraint로 보장)
    """
    job_names = db.query(JobRequiredSkill.job_name).all()
    return [{"name": name[0]} for name in job_names]
