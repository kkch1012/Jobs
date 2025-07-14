from typing import List, Dict, Any, Optional
from datetime import datetime, date
from app.models.job_postings import JobPosting

async def get_all_job_postings() -> List[JobPosting]:
    """MongoDB에서 모든 채용공고 조회"""
    jobs = await JobPosting.find_all().to_list()
    return jobs

def parse_date(date_str: Optional[str]) -> Optional[date]:
    """문자열을 date 타입으로 변환 (예: '2025-03-26' -> date)"""
    if not date_str or not isinstance(date_str, str):
        return None
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
        job_id_val = job.job_id if job.job_id and str(job.job_id).isdigit() else None
        company_id_val = data.get("company_id")
        company_id_val = int(company_id_val) if company_id_val is not None and str(company_id_val).isdigit() else None
        posting_date_val = data.get("posting_date")
        posting_date_val = parse_date(posting_date_val) if isinstance(posting_date_val, str) else None

        item = {
            "id": int(job_id_val) if job_id_val is not None else None,
            "company_id": company_id_val,
            "job_position": data.get("job_position") or data.get("title") or "",
            "employment_type": data.get("employment_type") or "",
            "applicant_type": data.get("applicant_type") or "",
            "posting_date": posting_date_val,
            "main_tasks": data.get("main_tasks") or "",
            "qualifications": data.get("qualifications") or "",
            "preferences": data.get("preferences") or "",
            "tech_stack": data.get("tech_stack") or "",
        }

        processed.append(item)

    return processed
