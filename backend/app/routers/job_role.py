from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.job_role import JobRole
from app.models.job_post import JobPost
from app.schemas.job_role import JobNameResponse

router = APIRouter(prefix="/job-role", tags=["Job Role"])

@router.get(
    "/job-names",
    operation_id="get_job_names",
    response_model=List[JobNameResponse],
    summary="직무명(이름만) 리스트 조회"
)
async def get_job_names(
    db: Session = Depends(get_db)
):
    """
    등록된 모든 직무명(name) 리스트를 반환합니다.
    (중복 불가능, unique constraint로 보장)
    """
    # DB에서 조회
    job_names = db.query(JobRole.job_name).all()
    result = [{"name": name[0]} for name in job_names]
    
    return result

@router.get(
    "/job-names/no-posts",
    operation_id="get_job_names_without_posts",
    response_model=List[JobNameResponse],
    summary="채용공고가 없는 직무명 리스트 조회"
)
async def get_job_names_without_posts(
    db: Session = Depends(get_db)
):
    """
    채용공고가 없는 직무명(name) 리스트를 반환합니다.
    (JobRole에는 있지만 JobPost에 연결된 데이터가 없는 직무들)
    """
    # LEFT JOIN을 사용해서 JobPost가 없는 JobRole 조회
    jobs_without_posts = db.query(JobRole.job_name).outerjoin(
        JobPost, JobRole.id == JobPost.job_required_skill_id
    ).filter(
        JobPost.id.is_(None)  # JobPost가 없는 경우
    ).all()
    
    result = [{"name": name[0]} for name in jobs_without_posts]
    
    return result

@router.get(
    "/job-names/with-posts",
    operation_id="get_job_names_with_posts",
    response_model=List[JobNameResponse],
    summary="채용공고가 있는 직무명 리스트 조회"
)
async def get_job_names_with_posts(
    db: Session = Depends(get_db)
):
    """
    채용공고가 있는 직무명(name) 리스트를 반환합니다.
    (JobPost에 연결된 데이터가 있는 직무들)
    """
    # INNER JOIN을 사용해서 JobPost가 있는 JobRole 조회
    jobs_with_posts = db.query(JobRole.job_name).join(
        JobPost, JobRole.id == JobPost.job_required_skill_id
    ).distinct().all()
    
    result = [{"name": name[0]} for name in jobs_with_posts]
    
    return result 