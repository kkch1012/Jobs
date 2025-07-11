from typing import Dict, Any, Optional
from beanie import Document, Indexed

class JobPosting(Document):
    job_id: str = Indexed(unique=True)  # 타입 힌트 + Indexed 설정 분리됨

    job_data: Optional[Dict[str, Any]] = None  # 나머지 모든 공고 정보 JSON 형태로 저장

    class Settings:
        name = "job_postings"
