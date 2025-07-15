from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.recommender import recommend_jobs_for_user
import os

router = APIRouter(prefix="/recommend", tags=["recommend"])

@router.get(
    "/user/{user_id}",
    summary="사용자 맞춤 채용공고 추천",
    description="""
사용자 ID를 기반으로 개인화된 채용공고를 추천합니다.

- **유사도 계산**: 사용자의 프로필(기술, 경험 등)과 각 채용공고의 임베딩 값을 비교하여 유사도를 계산합니다.
- **LLM 재추천**: 유사도 상위 N개의 공고를 LLM(Qwen)에게 보내, 최종적으로 가장 적합한 5개의 공고와 그 이유를 추천받습니다.
- **API 키 필요**: 이 기능을 사용하려면 서버 환경변수에 `OPENROUTER_API_KEY`가 설정되어 있어야 합니다.
"""
)
def recommend_for_user(user_id: int, db: Session = Depends(get_db)):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 환경변수가 설정되어 있지 않습니다.")
    result = recommend_jobs_for_user(user_id, db, api_key)
    return {"recommendation": result}