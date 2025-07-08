from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.services.mongo_service import preprocess_job_postings

router = APIRouter(prefix="/preprocess", tags=["Preprocess"])

@router.get(
    "/job_postings",
    response_model=List[Dict[str, Any]],
    summary="전처리된 채용공고 목록 조회",
    description="""
MongoDB에서 채용공고 데이터를 조회하여 PostgreSQL 구조에 맞게 변환한 후,  
전처리된 채용공고 리스트를 반환하는 API입니다.

- MongoDB에 저장된 원본 공고 데이터를 기반으로 합니다.
- 반환되는 데이터는 PostgreSQL 스키마에 맞춘 형태입니다.
- 비동기 방식으로 처리됩니다.
"""
)
async def get_processed_job_postings():
    """
    MongoDB에서 불러와 PostgreSQL 구조로 변환한 채용공고 리스트 반환 API
    """
    try:
        processed_data = await preprocess_job_postings()
        return processed_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
