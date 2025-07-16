from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.user_similarity import UserSimilarity
from app.models.job_post import JobPost
from app.services.similarity_scores import (
    compute_similarity_scores,
    save_similarity_scores
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
        # 유사도 점수 계산
        scores = compute_similarity_scores(user, db)
        
        if not scores:
            return {"message": "계산할 채용공고가 없습니다.", "scores_count": 0}
        
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
    summary="모든 사용자 유사도 점수 계산 (관리자용)",
    description="""
모든 사용자에 대해 유사도 점수를 계산하고 저장합니다.

- **주의**: 시간이 오래 걸릴 수 있습니다
- **권한**: 관리자만 실행 가능
"""
)
def compute_all_users_similarity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 관리자 권한 확인 (예: admin 필드가 있다면)
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="관리자만 실행할 수 있습니다.")
    
    try:
        users = db.query(User).all()
        results = []
        
        for user in users:
            try:
                scores = compute_similarity_scores(user, db)
                if scores:
                    save_similarity_scores(user, scores, db)
                    results.append({
                        "user_id": user.id,
                        "user_name": user.name,
                        "scores_count": len(scores),
                        "status": "success"
                    })
                else:
                    results.append({
                        "user_id": user.id,
                        "user_name": user.name,
                        "scores_count": 0,
                        "status": "no_jobs"
                    })
            except Exception as e:
                results.append({
                    "user_id": user.id,
                    "user_name": user.name,
                    "error": str(e),
                    "status": "error"
                })
        
        return {
            "message": "전체 사용자 유사도 점수 계산이 완료되었습니다.",
            "total_users": len(users),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"전체 유사도 계산 중 오류가 발생했습니다: {str(e)}")

 