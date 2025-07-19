from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.user_similarity import UserSimilarity
from app.models.job_post import JobPost
from app.services.similarity_scores import (
    compute_similarity_scores,
    save_similarity_scores,
    auto_compute_user_similarity,
    auto_compute_all_users_similarity
)
from app.utils.dependencies import get_current_user
from typing import List, Dict, Any
import numpy as np

router = APIRouter(prefix="/similarity", tags=["Similarity"])

@router.post(
    "/compute",
    summary="사용자 유사도 점수 계산 및 저장",
    description="""
현재 로그인된 사용자와 모든 채용공고 간의 유사도 점수를 계산하고 데이터베이스에 저장합니다.

- **계산 과정**: 사용자 프로필을 임베딩으로 변환하여 각 채용공고와의 코사인 유사도를 계산
- **저장**: 기존 유사도 점수를 삭제하고 새로 계산된 점수를 저장
- **권한**: 로그인된 사용자만 실행 가능
"""
)
def compute_and_save_similarity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # current_user가 이미 로그인된 사용자 정보를 담고 있음
    user = current_user
    
    try:
        # 유효한 임베딩을 가진 채용공고 조회
        job_posts = db.query(JobPost).filter(JobPost.full_embedding.isnot(None)).all()
        
        if not job_posts:
            return {"message": "계산할 채용공고가 없습니다.", "scores_count": 0}
        
        # 유사도 점수 계산
        scores = compute_similarity_scores(user, job_posts)
        
        if not scores:
            return {"message": "유사도 계산 결과가 없습니다.", "scores_count": 0}
        
        # 데이터베이스에 저장
        save_similarity_scores(user, scores, db)
        
        return {
            "message": "유사도 점수 계산 및 저장이 완료되었습니다.",
            "user_id": user.id,
            "scores_count": len(scores),
            "top_scores": sorted(scores, key=lambda x: x[1], reverse=True)[:5]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"유사도 계산 중 오류가 발생했습니다: {str(e)}")


@router.post(
    "/compute-all",
    summary="모든 사용자 유사도 점수 계산 (개발/테스트용)",
    description="""
모든 사용자에 대해 유사도 점수를 계산하고 저장합니다.

- **주의**: 시간이 오래 걸릴 수 있습니다
- **용도**: 개발/테스트용 (FastAPI docs에서만 사용)
"""
)
def compute_all_users_similarity(
    db: Session = Depends(get_db)
):
    # 권한 체크 제거 - 개발/테스트용으로만 사용
    
    try:
        # auto_compute_all_users_similarity 함수 사용
        result = auto_compute_all_users_similarity(db)
        
        return {
            "message": "전체 사용자 유사도 점수 계산이 완료되었습니다.",
            "total_users": result["total_users"],
            "success_count": result["success_count"],
            "error_count": result["error_count"],
            "skipped_count": result["skipped_count"],
            "results": result["details"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"전체 유사도 계산 중 오류가 발생했습니다: {str(e)}")

@router.get(
    "/scores/{user_id}",
    summary="사용자 유사도 점수 조회",
    description="""
특정 사용자의 저장된 유사도 점수를 조회합니다.

- **응답**: 유사도 점수가 높은 순으로 정렬된 채용공고 목록
- **권한**: 로그인된 사용자만 조회 가능
"""
)
def get_user_similarity_scores(
    user_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from app.services.similarity_scores import get_user_similarity_scores
        
        similarities = get_user_similarity_scores(user_id, db, limit)
        
        return {
            "user_id": user_id,
            "scores_count": len(similarities),
            "similarities": [
                {
                    "job_post_id": sim.job_post_id,
                    "similarity": sim.similarity,
                    "created_at": sim.created_at
                }
                for sim in similarities
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"유사도 점수 조회 중 오류가 발생했습니다: {str(e)}")

@router.get(
    "/top-jobs/{user_id}",
    summary="사용자 상위 추천 공고 ID 조회",
    description="""
특정 사용자에 대한 상위 추천 공고 ID 목록을 반환합니다.

- **응답**: 유사도 기준 상위 30개 공고 ID
- **용도**: 추천 시스템 연동용
- **권한**: 로그인된 사용자만 조회 가능
"""
)
def get_top_job_ids(
    user_id: int,
    top_k: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from app.services.similarity_scores import get_top_job_ids
        
        # 사용자 조회
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # 유효한 임베딩을 가진 채용공고 조회
        job_posts = db.query(JobPost).filter(JobPost.full_embedding.isnot(None)).all()
        
        if not job_posts:
            return {"user_id": user_id, "top_job_ids": [], "message": "계산할 채용공고가 없습니다."}
        
        # 상위 공고 ID 조회
        top_job_ids = get_top_job_ids(user, job_posts, top_k)
        
        return {
            "user_id": user_id,
            "top_k": top_k,
            "top_job_ids": top_job_ids,
            "count": len(top_job_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상위 공고 ID 조회 중 오류가 발생했습니다: {str(e)}")

 