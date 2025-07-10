from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.job_post import JobPost
from app.schemas.job_post import JobPostCreate, JobPostResponse

router = APIRouter(prefix="/job_posts", tags=["job_posts"])


@router.post(
    "/",
    response_model=JobPostResponse,
    operation_id="create_job_post",
    summary="공고 등록",
    description="""
관리자 또는 크롤링 도구가 새로운 채용공고를 등록할 때 사용합니다.

- `JobPostCreate` 스키마를 기반으로 공고 정보를 입력받습니다.
- 모든 필수 필드(`title`, `company_name`, `job_position`, `posting_date` 등)는 누락 없이 전달되어야 합니다.
- 공고 ID는 자동으로 생성되며, 생성된 공고 정보를 반환합니다.
"""
)
def create_job_post(job_post: JobPostCreate, db: Session = Depends(get_db)):
    db_job = JobPost(**job_post.dict())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


@router.get(
    "/",
    response_model=List[JobPostResponse],
    operation_id="read_job_posts",
    summary="전체 채용공고 조회",
    description="""
모든 채용공고 데이터를 리스트로 조회합니다.

- 필터 없이 전체 공고 데이터를 반환합니다.
- 프론트엔드에서 전체 공고를 보여주는 데 사용됩니다.
"""
)
def read_job_posts(db: Session = Depends(get_db)):
    return db.query(JobPost).all()


@router.get(
    "/{job_post_id}",
    response_model=JobPostResponse,
    operation_id="get_job_post",
    summary="단일 채용공고 상세 조회",
    description="""
특정 채용공고의 상세 정보를 조회합니다.

- `job_post_id`는 조회하려는 공고의 고유 ID입니다.
- 존재하지 않는 경우 404 에러를 반환합니다.
"""
)
def get_job_post(job_post_id: int, db: Session = Depends(get_db)):
    job_post = db.query(JobPost).filter(JobPost.id == job_post_id).first()
    if not job_post:
        raise HTTPException(status_code=404, detail="Job post not found")
    return job_post
