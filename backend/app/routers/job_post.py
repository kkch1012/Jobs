from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, null
from typing import List, Optional
from app.database import get_db
from app.models.job_post import JobPost
from app.models.job_required_skill import JobRequiredSkill
from app.models.user import User
from app.models.user_similarity import UserSimilarity
from app.schemas.job_post import JobPostResponse
from app.utils.dependencies import get_optional_current_user
from app.utils.logger import app_logger

router = APIRouter(prefix="/job_posts", tags=["job_posts"])

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
    - **로그인 시, 해당 유저와 공고의 유사도(적합도)를 함께 반환합니다.**
    - 마감일(deadline)이 null인 경우 "상시채용"으로 반환합니다.
    """
)
def read_job_posts(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="한 번에 가져올 최대 공고 수 (최대 100, 기본 50)"),
    offset: int = Query(0, ge=0, description="가져올 시작 위치 (0부터 시작)"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    company_name: Optional[str] = Query(None, description="회사명으로 필터링"),
    job_name: Optional[str] = Query(None, description="직무명으로 필터링"),
    applicant_type: Optional[str] = Query(None, description="지원자격으로 필터링"),
    employment_type: Optional[str] = Query(None, description="고용형태로 필터링"),
    tech_stack: Optional[str] = Query(None, description="기술스택(포함여부)로 필터링")
):
    try:
        # 기본 쿼리 구성 - 유사도 점수와 함께 조회
        if current_user:
            query = db.query(JobPost, UserSimilarity.similarity).outerjoin(
                UserSimilarity,
                and_(
                    JobPost.id == UserSimilarity.job_post_id,
                    UserSimilarity.user_id == current_user.id
                )
            )
        else:
            query = db.query(JobPost, null().label('similarity'))

        # 관계 데이터 미리 로드 (N+1 쿼리 방지)
        query = query.options(
            joinedload(JobPost.job_required_skill)
        )

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
        
        # 정렬 및 페이징
        if current_user:
            # 로그인한 사용자의 경우 유사도 점수로 정렬 (높은 순)
            query = query.order_by(UserSimilarity.similarity.desc().nullslast(), JobPost.posting_date.desc())
        else:
            # 비로그인 사용자의 경우 게시일 순으로 정렬
            query = query.order_by(JobPost.posting_date.desc())
            
        job_posts_with_similarity = query.offset(offset).limit(limit).all()

        result = []
        for job, similarity in job_posts_with_similarity:
            # JobPostResponse 객체 생성
            response_item = JobPostResponse.model_validate(job)
            # 유사도 점수 설정
            response_item.similarity = similarity
            result.append(response_item)

        app_logger.info(f"채용공고 조회 완료: {len(result)}건, 사용자: {current_user.id if current_user else '비로그인'}")
        return result
        
    except Exception as e:
        app_logger.error(f"채용공고 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"채용공고 조회 중 오류가 발생했습니다: {str(e)}")

# === 유니크 리스트 엔드포인트 (정적 경로) ===
@router.get(
    "/unique_company_names",
    response_model=List[str],
    summary="회사명 유니크 리스트 조회",
    description="등록된 모든 채용공고의 회사명(중복제거) 리스트를 반환합니다."
)
def get_unique_company_names(db: Session = Depends(get_db)):
    try:
        names = db.query(JobPost.company_name).distinct().filter(JobPost.company_name.isnot(None)).all()
        result = [n[0] for n in names if n[0]]
        app_logger.info(f"회사명 유니크 리스트 조회 완료: {len(result)}건")
        return result
    except Exception as e:
        app_logger.error(f"회사명 유니크 리스트 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"회사명 리스트 조회 중 오류가 발생했습니다: {str(e)}")

@router.get(
    "/unique_applicant_types",
    response_model=List[str],
    summary="지원자격 유니크 리스트 조회",
    description="등록된 모든 채용공고의 지원자격(중복제거) 리스트를 반환합니다."
)
def get_unique_applicant_types(db: Session = Depends(get_db)):
    try:
        types = db.query(JobPost.applicant_type).distinct().filter(JobPost.applicant_type.isnot(None)).all()
        result = [t[0] for t in types if t[0]]
        app_logger.info(f"지원자격 유니크 리스트 조회 완료: {len(result)}건")
        return result
    except Exception as e:
        app_logger.error(f"지원자격 유니크 리스트 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"지원자격 리스트 조회 중 오류가 발생했습니다: {str(e)}")

@router.get(
    "/unique_employment_types",
    response_model=List[str],
    summary="고용형태 유니크 리스트 조회",
    description="등록된 모든 채용공고의 고용형태(중복제거) 리스트를 반환합니다."
)
def get_unique_employment_types(db: Session = Depends(get_db)):
    try:
        types = db.query(JobPost.employment_type).distinct().filter(JobPost.employment_type.isnot(None)).all()
        result = [t[0] for t in types if t[0]]
        app_logger.info(f"고용형태 유니크 리스트 조회 완료: {len(result)}건")
        return result
    except Exception as e:
        app_logger.error(f"고용형태 유니크 리스트 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"고용형태 리스트 조회 중 오류가 발생했습니다: {str(e)}")

@router.get(
    "/unique_tech_stacks",
    response_model=List[str],
    summary="기술스택 유니크 리스트 조회",
    description="등록된 모든 채용공고의 기술스택(중복제거) 리스트를 반환합니다. 여러 기술이 콤마로 구분되어 있을 경우 모두 분리하여 유니크하게 반환합니다."
)
def get_unique_tech_stacks(db: Session = Depends(get_db)):
    try:
        stacks = db.query(JobPost.tech_stack).distinct().filter(JobPost.tech_stack.isnot(None)).all()
        tech_set = set()
        for s in stacks:
            if s[0]:
                for tech in s[0].split(","):
                    tech = tech.strip()
                    if tech:
                        tech_set.add(tech)
        result = sorted(list(tech_set))
        app_logger.info(f"기술스택 유니크 리스트 조회 완료: {len(result)}건")
        return result
    except Exception as e:
        app_logger.error(f"기술스택 유니크 리스트 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"기술스택 리스트 조회 중 오류가 발생했습니다: {str(e)}")