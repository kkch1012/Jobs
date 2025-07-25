from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, null
from typing import List, Optional
from app.database import get_db
from app.models.job_post import JobPost
from app.models.job_role import JobRole
from app.models.user import User
from app.models.user_similarity import UserSimilarity
from app.schemas.job_post import JobPostResponse, JobPostSearchResponse
from app.utils.dependencies import get_optional_current_user
from app.utils.logger import app_logger

router = APIRouter(prefix="/job_posts", tags=["job_posts"])

@router.get(
    "/",
    response_model=List[JobPostSearchResponse],
    operation_id="read_job_posts",
    summary="전체 채용공고 조회 (필터/페이징 지원)",
    description="""
    회사명, 직무명, 지원자격, 고용형태, 기술스택 등 다양한 조건으로 채용공고를 필터링하여 조회합니다.\n
    - 기본적으로 50건씩 페이징하여 반환합니다.\n
    - `company_name`, `job_name`, `applicant_type`, `employment_type`, `tech_stack` 쿼리 파라미터로 필터링이 가능합니다.\n
    - `limit`(최대 반환 개수, 기본 50, 최대 100), `offset`(시작 위치) 쿼리 파라미터로 페이지네이션이 가능합니다.\n
    - **로그인 시, 해당 유저와 공고의 유사도(적합도)를 함께 반환합니다.**
    - 마감일(deadline)이 null인 경우 "상시채용"으로 반환합니다.
    - **응답**: 검색용 간소화된 정보 (main_tasks, qualifications, preferences 제외)
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
            joinedload(JobPost.job_role)
        )

        # 동적 필터링
        filters = []
        
        # 기본 필터: 만료되지 않은 공고만 조회
        filters.append(or_(JobPost.is_expired.is_(None), JobPost.is_expired.is_(False)))
        
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
        # 직무명 필터링
        if job_name:
            # 직무명으로 조인 후 필터
            query = query.join(JobPost.job_role)
            filters.append(JobRole.job_name.ilike(f"%{job_name}%"))
        
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
            # JobPostSearchResponse 객체 생성 (검색용 간소화된 응답)
            response_item = JobPostSearchResponse.model_validate(job)
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
        names = db.query(JobPost.company_name).distinct().filter(
            and_(
                JobPost.company_name.isnot(None),
                or_(JobPost.is_expired.is_(None), JobPost.is_expired.is_(False))
            )
        ).all()
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
    description="등록된 모든 채용공고의 지원자격을 카테고리별로 정리하여 반환합니다."
)
def get_unique_applicant_types(db: Session = Depends(get_db)):
    try:
        types = db.query(JobPost.applicant_type).distinct().filter(
            and_(
                JobPost.applicant_type.isnot(None),
                or_(JobPost.is_expired.is_(None), JobPost.is_expired.is_(False))
            )
        ).all()
        
        raw_types = [t[0] for t in types if t[0]]
        
        # 지원자격 카테고리 정리
        categorized_types = set()
        
        for applicant_type in raw_types:
            if not applicant_type:
                continue
                
            # 신입 관련
            if "신입" in applicant_type:
                if "경력" in applicant_type:
                    categorized_types.add("신입/경력")
                else:
                    categorized_types.add("신입")
            # 경력 관련
            elif "경력" in applicant_type:
                # 경력 연차 범위 추출 (예: "경력(3~5년)" -> 3, 5)
                import re
                year_matches = re.findall(r'(\d+)', applicant_type)
                if year_matches:
                    # 첫 번째 숫자를 기준으로 분류
                    min_years = int(year_matches[0])
                    if min_years == 0:
                        categorized_types.add("신입/경력")
                    elif min_years <= 3:
                        categorized_types.add("경력(1-3년)")
                    elif min_years <= 5:
                        categorized_types.add("경력(3-5년)")
                    elif min_years <= 7:
                        categorized_types.add("경력(5-7년)")
                    elif min_years <= 10:
                        categorized_types.add("경력(7-10년)")
                    else:
                        categorized_types.add("경력(10년+)")
                else:
                    categorized_types.add("경력")
            # 기타
            else:
                categorized_types.add(applicant_type)
        
        # 정렬된 결과 반환
        result = sorted(list(categorized_types))
        
        app_logger.info(f"지원자격 유니크 리스트 조회 완료: {len(result)}건 (카테고리별 정리)")
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
        types = db.query(JobPost.employment_type).distinct().filter(
            and_(
                JobPost.employment_type.isnot(None),
                or_(JobPost.is_expired.is_(None), JobPost.is_expired.is_(False))
            )
        ).all()
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
    description="주간 스킬 통계에서 추출된 상위 기술스택들의 유니크 리스트를 반환합니다. 실제 채용공고에서 빈도순으로 정렬된 기술 스택을 제공합니다."
)
def get_unique_tech_stacks(
    db: Session = Depends(get_db),
    job_name: Optional[str] = Query(None, description="특정 직무의 기술스택만 조회 (선택사항)")
):
    try:
        from app.models.weekly_skill_stat import WeeklySkillStat
        
        # 특정 직무가 지정된 경우 해당 직무의 기술 스택만 조회
        if job_name:
            from app.models.job_role import JobRole
              
            job_role = db.query(JobRole).filter(
                JobRole.job_name == job_name
            ).first()
            
            if job_role:
                # 직무별 필터링을 위한 쿼리 구성
                query = db.query(WeeklySkillStat.skill).filter(
                    and_(
                        WeeklySkillStat.field_type == "tech_stack",
                        WeeklySkillStat.job_role_id == job_role.id
                    )
                )
                app_logger.info(f"직무별 기술스택 조회: {job_name}")
            else:
                app_logger.warning(f"지정된 직무를 찾을 수 없음: {job_name}")
                return []
        else:
            # 전체 직무의 기술 스택 조회
            query = db.query(WeeklySkillStat.skill).filter(
                WeeklySkillStat.field_type == "tech_stack"
            )
        
        # 전체 직무를 합쳐서 각 기술 스택의 총 카운트를 구함
        from sqlalchemy import func
        
        # 1. 각 스킬의 총 카운트를 구하고 10개 이상인 것만 필터링
        skill_counts = db.query(
            WeeklySkillStat.skill,
            func.sum(WeeklySkillStat.count).label('total_count')
        ).filter(
            WeeklySkillStat.field_type == "tech_stack"
        ).group_by(
            WeeklySkillStat.skill
        ).having(
            func.sum(WeeklySkillStat.count) >= 10  # 10개 이상인 것만
        ).order_by(
            func.sum(WeeklySkillStat.count).desc(),
            WeeklySkillStat.skill.asc()
        ).all()
        
        # 2. 스킬명만 추출
        unique_skills = [(skill, count) for skill, count in skill_counts]
        
        result = [skill for skill, count in unique_skills if skill]
        
        # 로그 메시지 개선
        if job_name:
            app_logger.info(f"기술스택 유니크 리스트 조회 완료: {len(result)}건 (직무: {job_name}, 주간 통계 기반)")
        else:
            app_logger.info(f"기술스택 유니크 리스트 조회 완료: {len(result)}건 (전체 직무, 주간 통계 기반)")
        
        return result
    except Exception as e:
        app_logger.error(f"기술스택 유니크 리스트 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"기술스택 리스트 조회 중 오류가 발생했습니다: {str(e)}")

@router.get(
    "/{job_id}",
    response_model=JobPostResponse,
    summary="채용공고 상세 조회",
    description="""
특정 채용공고의 상세 정보를 조회합니다.

- `job_id`에 해당하는 채용공고가 존재하지 않으면 404 오류를 반환합니다.
- 로그인한 사용자의 경우 해당 공고와의 유사도 점수도 함께 반환합니다.
"""
)
def get_job_post_detail(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    try:
        # 기본 쿼리 구성
        if current_user:
            # 로그인한 사용자의 경우 유사도 점수와 함께 조회
            query = db.query(JobPost, UserSimilarity.similarity).outerjoin(
                UserSimilarity,
                and_(
                    JobPost.id == UserSimilarity.job_post_id,
                    UserSimilarity.user_id == current_user.id
                )
            ).filter(
                and_(
                    JobPost.id == job_id,
                    or_(JobPost.is_expired.is_(None), JobPost.is_expired.is_(False))
                )
            )
        else:
            # 비로그인 사용자의 경우 유사도 없이 조회
            query = db.query(JobPost, null().label('similarity')).filter(
                and_(
                    JobPost.id == job_id,
                    or_(JobPost.is_expired.is_(None), JobPost.is_expired.is_(False))
                )
            )

        # 관계 데이터 미리 로드
        query = query.options(
            joinedload(JobPost.job_role)
        )

        result = query.first()
        
        if not result:
            app_logger.warning(f"채용공고를 찾을 수 없음: job_id={job_id}")
            raise HTTPException(status_code=404, detail=f"ID {job_id}의 채용공고를 찾을 수 없습니다.")

        job, similarity = result
        
        # JobPostResponse 객체 생성
        response_item = JobPostResponse.model_validate(job)
        # 유사도 점수 설정
        response_item.similarity = similarity
        
        app_logger.info(f"채용공고 상세 조회 완료: job_id={job_id}, 사용자: {current_user.id if current_user else '비로그인'}")
        return response_item
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"채용공고 상세 조회 실패: job_id={job_id}, 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"채용공고 상세 조회 중 오류가 발생했습니다: {str(e)}")