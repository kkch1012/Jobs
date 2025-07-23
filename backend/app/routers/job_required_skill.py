from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from datetime import timedelta

from app.database import get_db
from app.models.job_required_skill import JobRequiredSkill
from app.models.job_post import JobPost
from app.schemas.job_required_skill import JobNameResponse
from app.utils.redis_cache import redis_cache_manager

router = APIRouter(prefix="/job-skills", tags=["Job Required Skills"])

@router.get(
    "/job-names",
    operation_id="get_job_names",
    response_model=List[JobNameResponse],
    summary="직무명(이름만) 리스트 조회"
)
async def get_job_names(
    force_refresh: bool = Query(False, description="캐시를 무시하고 새로 조회"),
    db: Session = Depends(get_db)
):
    """
    등록된 모든 직무명(name) 리스트를 반환합니다.
    (중복 불가능, unique constraint로 보장)
    캐싱: 30분 동안 중복 조회를 방지합니다.
    """
    # 캐시 키 생성
    cache_key = "job_names:all"
    
    # 캐시 확인 (force_refresh가 False인 경우만)
    if not force_refresh:
        cached_data = await redis_cache_manager.get_cached_data("job_names", cache_key, timedelta(minutes=30))
        if cached_data is not None:
            return cached_data
    
    # DB에서 조회
    job_names = db.query(JobRequiredSkill.job_name).all()
    result = [{"name": name[0]} for name in job_names]
    
    # Redis 캐시에 저장
    await redis_cache_manager.set_cached_data("job_names", cache_key, result, timedelta(minutes=30))
    
    return result

@router.get(
    "/job-names/no-posts",
    operation_id="get_job_names_without_posts",
    response_model=List[JobNameResponse],
    summary="채용공고가 없는 직무명 리스트 조회"
)
async def get_job_names_without_posts(
    force_refresh: bool = Query(False, description="캐시를 무시하고 새로 조회"),
    db: Session = Depends(get_db)
):
    """
    채용공고가 없는 직무명(name) 리스트를 반환합니다.
    (JobRequiredSkill에는 있지만 JobPost에 연결된 데이터가 없는 직무들)
    캐싱: 30분 동안 중복 조회를 방지합니다.
    """
    # 캐시 키 생성
    cache_key = "job_names:no_posts"
    
    # 캐시 확인 (force_refresh가 False인 경우만)
    if not force_refresh:
        cached_data = await redis_cache_manager.get_cached_data("job_names", cache_key, timedelta(minutes=30))
        if cached_data is not None:
            return cached_data
    
    # LEFT JOIN을 사용해서 JobPost가 없는 JobRequiredSkill 조회
    jobs_without_posts = db.query(JobRequiredSkill.job_name).outerjoin(
        JobPost, JobRequiredSkill.id == JobPost.job_required_skill_id
    ).filter(
        JobPost.id.is_(None)  # JobPost가 없는 경우
    ).all()
    
    result = [{"name": name[0]} for name in jobs_without_posts]
    
    # Redis 캐시에 저장
    await redis_cache_manager.set_cached_data("job_names", cache_key, result, timedelta(minutes=30))
    
    return result

@router.get(
    "/job-names/with-posts",
    operation_id="get_job_names_with_posts",
    response_model=List[JobNameResponse],
    summary="채용공고가 있는 직무명 리스트 조회"
)
async def get_job_names_with_posts(
    force_refresh: bool = Query(False, description="캐시를 무시하고 새로 조회"),
    db: Session = Depends(get_db)
):
    """
    채용공고가 있는 직무명(name) 리스트를 반환합니다.
    (JobPost에 연결된 데이터가 있는 직무들)
    캐싱: 30분 동안 중복 조회를 방지합니다.
    """
    # 캐시 키 생성
    cache_key = "job_names:with_posts"
    
    # 캐시 확인 (force_refresh가 False인 경우만)
    if not force_refresh:
        cached_data = await redis_cache_manager.get_cached_data("job_names", cache_key, timedelta(minutes=30))
        if cached_data is not None:
            return cached_data
    
    # INNER JOIN을 사용해서 JobPost가 있는 JobRequiredSkill 조회
    jobs_with_posts = db.query(JobRequiredSkill.job_name).join(
        JobPost, JobRequiredSkill.id == JobPost.job_required_skill_id
    ).distinct().all()
    
    result = [{"name": name[0]} for name in jobs_with_posts]
    
    # Redis 캐시에 저장
    await redis_cache_manager.set_cached_data("job_names", cache_key, result, timedelta(minutes=30))
    
    return result

@router.delete("/cache/clear", summary="직무명 캐시 초기화", description="직무명 관련 캐시를 모두 초기화합니다.")
async def clear_job_names_cache():
    """직무명 캐시를 초기화합니다."""
    try:
        # 모든 직무명 관련 캐시 삭제
        deleted_count = await redis_cache_manager.clear_user_cache(None, ["job_names"])
        
        return {
            "message": "직무명 Redis 캐시가 초기화되었습니다.",
            "deleted_cache_count": deleted_count
        }
        
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"캐시 초기화 실패: {str(e)}")

@router.get("/cache/status", summary="직무명 캐시 상태 조회", description="현재 직무명 캐시 상태를 조회합니다.")
async def get_job_names_cache_status():
    """직무명 캐시 상태를 조회합니다."""
    try:
        return await redis_cache_manager.get_cache_status(None)
        
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"캐시 상태 조회 실패: {str(e)}")
