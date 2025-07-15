from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import List, Optional
from app.database import get_db
from app.models.job_post import JobPost
from app.models.job_required_skill import JobRequiredSkill
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
    job_data = job_post.dict()
    
    # full_embedding이 제공되지 않은 경우 기본값을 빈 리스트로 설정
    if job_data.get('full_embedding') is None:
        job_data['full_embedding'] = []
    
    db_job = JobPost(**job_data)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


@router.get(
    "/",
    response_model=List[JobPostResponse],
    operation_id="read_job_posts",
    summary="전체 채용공고 조회 (필터/페이징 지원)",
    description="""
    회사명, 직무명, 지원자격, 고용형태, 기술스택 등 다양한 조건으로 채용공고를 필터링하여 조회합니다.\n
    - 기본적으로 50건씩 페이징하여 반환합니다.\n
    - `company_name`, `job_name`, `applicant_type`, `employment_type`, `tech_stack` 쿼리 파라미터로 필터링이 가능합니다.\n
    - `limit`(최대 반환 개수, 기본 50, 최대 100), `offset`(시작 위치) 쿼리 파라미터로 페이지네이션이 가능합니다.\n
    - 마감일(deadline)이 null인 경우 "상시채용"으로 반환합니다.
    """
)
def read_job_posts(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="한 번에 가져올 최대 공고 수 (최대 100, 기본 50)"),
    offset: int = Query(0, ge=0, description="가져올 시작 위치 (0부터 시작)"),
    company_name: Optional[str] = Query(None, description="회사명으로 필터링"),
    job_name: Optional[str] = Query(None, description="직무명으로 필터링"),
    applicant_type: Optional[str] = Query(None, description="지원자격으로 필터링"),
    employment_type: Optional[str] = Query(None, description="고용형태로 필터링"),
    tech_stack: Optional[str] = Query(None, description="기술스택(포함여부)로 필터링")
):
    query = db.query(JobPost).options(joinedload(JobPost.job_required_skill))
    # 동적 필터링
    filters = []
    if company_name:
        filters.append(
            or_(
                JobPost.company_name.ilike(f"%{company_name}%"),
                JobPost.title.ilike(f"%{company_name}%")
            )
        )
    if applicant_type:
        filters.append(JobPost.applicant_type.ilike(f"%{applicant_type}%"))
    if employment_type:
        filters.append(JobPost.employment_type.ilike(f"%{employment_type}%"))
    if tech_stack:
        filters.append(JobPost.tech_stack.ilike(f"%{tech_stack}%"))
    if job_name:
        # 직무명으로 조인 후 필터
        query = query.join(JobPost.job_required_skill)
        filters.append(JobRequiredSkill.job_name.ilike(f"%{job_name}%"))
    if filters:
        query = query.filter(and_(*filters))
    job_posts = query.offset(offset).limit(limit).all()
    result = []
    for job in job_posts:
        # SQLAlchemy 객체의 __dict__에는 _sa_instance_state 등이 포함되므로, Pydantic 변환 사용
        job_data = JobPostResponse.model_validate(job)
        job_data = job_data.model_dump()
        # deadline이 None이면 그대로 둠 (프론트에서 "상시채용" 처리)
        result.append(job_data)
    return result


# === 유니크 리스트 엔드포인트 (정적 경로) ===
@router.get(
    "/unique_company_names",
    response_model=List[str],
    summary="회사명 유니크 리스트 조회",
    description="등록된 모든 채용공고의 회사명(중복제거) 리스트를 반환합니다."
)
def get_unique_company_names(db: Session = Depends(get_db)):
    names = db.query(JobPost.company_name).distinct().all()
    return [n[0] for n in names if n[0]]

@router.get(
    "/unique_applicant_types",
    response_model=List[str],
    summary="지원자격 유니크 리스트 조회",
    description="등록된 모든 채용공고의 지원자격(중복제거) 리스트를 반환합니다."
)
def get_unique_applicant_types(db: Session = Depends(get_db)):
    types = db.query(JobPost.applicant_type).distinct().all()
    return [t[0] for t in types if t[0]]

@router.get(
    "/unique_employment_types",
    response_model=List[str],
    summary="고용형태 유니크 리스트 조회",
    description="등록된 모든 채용공고의 고용형태(중복제거) 리스트를 반환합니다."
)
def get_unique_employment_types(db: Session = Depends(get_db)):
    types = db.query(JobPost.employment_type).distinct().all()
    return [t[0] for t in types if t[0]]

@router.get(
    "/unique_tech_stacks",
    response_model=List[str],
    summary="기술스택 유니크 리스트 조회",
    description="등록된 모든 채용공고의 기술스택(중복제거) 리스트를 반환합니다. 여러 기술이 콤마로 구분되어 있을 경우 모두 분리하여 유니크하게 반환합니다."
)
def get_unique_tech_stacks(db: Session = Depends(get_db)):
    stacks = db.query(JobPost.tech_stack).distinct().all()
    tech_set = set()
    for s in stacks:
        if s[0]:
            for tech in s[0].split(","):
                tech = tech.strip()
                if tech:
                    tech_set.add(tech)
    return sorted(list(tech_set))