from typing import List, Dict, Any
from datetime import datetime
from app.models.job_postings import JobPosting

async def get_all_job_postings() -> List[JobPosting]:
    """MongoDB에서 모든 채용공고 조회"""
    jobs = await JobPosting.find_all().to_list()
    return jobs

def parse_date(date_str: str) -> datetime.date:
    """문자열을 date 타입으로 변환 (예: '2025-03-26' -> date)"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None

async def preprocess_job_postings() -> List[Dict[str, Any]]:
    """
    MongoDB 채용공고를 PostgreSQL ORM 모델에 맞게 변환해 리스트로 반환
    """
    jobs = await get_all_job_postings()
    processed = []
    for job in jobs:
        data = job.job_data or {}

        # PostgreSQL 모델 필드명에 맞게 변환
        item = {
            "id": int(job.job_id) if job.job_id and job.job_id.isdigit() else None,
            "company_id": int(data.get("company_id")) if data.get("company_id") else None,
            "job_position": data.get("job_position") or data.get("title") or "",
            "employment_type": data.get("employment_type") or "",
            "applicant_type": data.get("applicant_type") or "",
            "posting_date": parse_date(data.get("posting_date")) if data.get("posting_date") else None,
            "main_tasks": data.get("main_tasks") or "",
            "qualifications": data.get("qualifications") or "",
            "preferences": data.get("preferences") or "",
            "tech_stack": data.get("tech_stack") or "",
        }

        processed.append(item)

    return processed
