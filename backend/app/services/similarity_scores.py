'''
추천 로직의 유사도 계산 모듈입니다.
- 전체 공고에 대한 유사도 리스트 반환 (프론트용)
- 상위 30개 공고 ID만 추출 (recommender 연동용)
'''
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.job_post import JobPost
from app.models.user_similarity import UserSimilarity
from app.utils.logger import similarity_logger
from datetime import datetime, timedelta
import asyncio
from typing import List, Optional

# === [1] 임베딩 모델 싱글턴 (1회만 로딩) ===
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("intfloat/multilingual-e5-large")
    return _embedder

# === [2] 사용자 정보를 문자열로 요약 ===
# 유저 ORM 객체(User)를 받아 주요 필드 값을 문자열로 변환함
# 유사도 계산을 위한 임베딩 입력 텍스트 생성용
'''
이때, user_id 는 프론트에서 전달받은 유저 id 입니다.
'''
def summarize_user_for_embedding(user: User) -> str:
    used_cols = [
        "name", "gender", "university", "major", "gpa",
        "education_status", "degree", "language_score",
        "desired_job", "working_year",
        "skills_with_proficiency", "certificates",
        "experiences_text"
    ]

    empty_values = {"", "None", "[]", "{}", "nan", "없음", "없어요", "없다", "null", "NULL"}

    def extract_user_fields(user: User) -> dict:
        # 경험 전체를 텍스트로 병합
        experiences_text = " | ".join([
            f"{exp.name}, {exp.period}, {exp.description}"
            for exp in user.experiences
        ]) if user.experiences else None

        return {
            "name": user.name,
            "gender": user.gender,
            "university": user.university,
            "major": user.major,
            "gpa": getattr(user, "gpa", None),
            "education_status": user.education_status,
            "degree": user.degree,
            "language_score": user.language_score.get("OPIC") if isinstance(user.language_score, dict) else None,
            "desired_job": ', '.join(user.desired_job) if isinstance(user.desired_job, list) else user.desired_job,
            "working_year": user.working_year,
            "skills_with_proficiency": ', '.join([f"{s.skill.name}({s.proficiency})" for s in user.user_skills]),
            "certificates": ', '.join([c.certificate.name for c in user.user_certificates]),
            "experiences_text": experiences_text
        }

    def summarize_user_fields(fields: dict) -> str:
        texts = []
        for col in used_cols:
            val = fields.get(col)
            if val is None or str(val).strip().lower() in empty_values:
                continue
            texts.append(str(val).strip())
        return " | ".join(texts)

    fields = extract_user_fields(user)
    return summarize_user_fields(fields)

# === [3] 유저 임베딩 생성 ===
def get_user_embedding(user: User) -> np.ndarray:
    user_text = summarize_user_for_embedding(user)
    embedder = get_embedder()
    embedding = embedder.encode(user_text, normalize_embeddings=True)
    return np.array(embedding)

# === [4] 유사도 보정 함수 (신입 여부 + 필드 누락) ===
def adjust_score_for_fresher(score, applicant_type, is_fresher, bonus=0.0, penalty=0.4):
    if not isinstance(applicant_type, str):
        return score
    if is_fresher:
        if "신입" in applicant_type:
            return score + bonus
        else:
            return score * penalty
    return score

def adjust_score_for_sparse_features(score, actual_count, expected_count):
    fill_ratio = actual_count / expected_count
    if fill_ratio >= 1.0:
        return score
    elif fill_ratio >= 0.8:
        return score * 0.9
    elif fill_ratio >= 0.6:
        return score * 0.7
    elif fill_ratio >= 0.4:
        return score * 0.5
    elif fill_ratio >= 0.2:
        return score * 0.2
    else:
        return score * 0.1

def adjust_similarity_score(similarity, applicant_type, user_row, used_cols, empty_values):
    is_fresher = "신입" in str(user_row.get("working_year"))
    actual_count = sum(1 for col in used_cols if str(user_row.get(col)).strip().lower() not in empty_values)
    expected_count = len(used_cols)

    score = adjust_score_for_fresher(similarity, applicant_type, is_fresher)
    score = adjust_score_for_sparse_features(score, actual_count, expected_count)
    return score

# === [5] 유사도 결과 DB 저장 및 조회 ===
def save_similarity_scores(user: User, scores: list, db: Session):
    # 이전 결과 삭제
    db.query(UserSimilarity).filter(UserSimilarity.user_id == user.id).delete()
    # 새로운 결과 저장 (numpy 타입을 Python float로 변환)
    for job_id, sim in scores:
        # numpy 타입을 Python float로 변환
        similarity_float = float(sim) if hasattr(sim, 'item') else sim
        db.add(UserSimilarity(user_id=user.id, job_post_id=job_id, similarity=similarity_float))
    db.commit()

def get_user_similarity_scores(user_id: int, db: Session, limit: int = 20) -> list:
    return (
        db.query(UserSimilarity)
        .filter(UserSimilarity.user_id == user_id)
        .order_by(UserSimilarity.similarity.desc())
        .limit(limit)
        .all()
    )

# === [6] 유사도 자동 갱신 여부 판단 ===
def should_recompute_similarity(user: User, db: Session, max_age_hours: int = 24) -> bool:
    try:
        latest_similarity = (
            db.query(UserSimilarity)
            .filter(UserSimilarity.user_id == user.id)
            .order_by(UserSimilarity.created_at.desc())
            .first()
        )
        if not latest_similarity:
            similarity_logger.info(f"사용자 {user.id}의 유사도 점수가 없습니다. 재계산이 필요합니다.")
            return True
        
        # 마지막 계산 시간 확인 (timezone-aware datetime 사용)
        from datetime import timezone
        current_time = datetime.now(timezone.utc)
        time_diff = current_time - latest_similarity.created_at
        hours_diff = time_diff.total_seconds() / 3600
        
        if hours_diff > max_age_hours:
            similarity_logger.info(f"사용자 {user.id}의 유사도 점수가 {hours_diff:.1f}시간 전에 계산되었습니다. 재계산이 필요합니다.")
            return True
        
        similarity_logger.info(f"사용자 {user.id}의 유사도 점수가 최신입니다. 재계산이 필요하지 않습니다.")
        return False
    except Exception as e:
        # created_at 필드가 아직 없는 경우 등 에러 발생 시 항상 재계산
        similarity_logger.warning(f"유사도 재계산 여부 확인 중 오류 발생, 강제 재계산: {str(e)}")
        return True

# === [7] 유사도 전체 자동 계산 함수 ===
def auto_compute_user_similarity(user: User, db: Session, job_posts: list) -> bool:
    try:
        user_vec = get_user_embedding(user)
        used_cols = [
            "name", "gender", "university", "major", "gpa",
            "education_status", "degree", "language_score",
            "desired_job", "working_year",
            "skills_with_proficiency", "certificates",
            "experiences_text"
        ]
        empty_values = {"", "None", "[]", "{}", "nan", "없음", "없어요", "없다", "null", "NULL"}

        # 사용자 정보를 딕셔너리로 변환 (SQLAlchemy 객체의 __dict__ 대신)
        user_dict = {
            "name": user.name,
            "gender": user.gender,
            "university": user.university,
            "major": user.major,
            "gpa": getattr(user, "gpa", None),
            "education_status": user.education_status,
            "degree": user.degree,
            "language_score": user.language_score,
            "desired_job": user.desired_job,
            "working_year": user.working_year,
            "skills_with_proficiency": ', '.join([f"{s.skill.name}({s.proficiency})" for s in user.user_skills]),
            "certificates": ', '.join([c.certificate.name for c in user.user_certificates]),
            "experiences_text": " | ".join([
                f"{exp.name}, {exp.period}, {exp.description}"
                for exp in user.experiences
            ]) if user.experiences else None
        }

        scores = []
        for job in job_posts:
            job_vec = np.array(job.full_embedding)
            job_vec = job_vec / np.linalg.norm(job_vec) if np.linalg.norm(job_vec) > 0 else job_vec
            sim = cosine_similarity([user_vec], [job_vec])[0][0]
            adjusted = adjust_similarity_score(sim, job.applicant_type, user_dict, used_cols, empty_values)
            # numpy 타입을 Python float로 변환
            adjusted_float = float(adjusted) if hasattr(adjusted, 'item') else adjusted
            scores.append((job.id, adjusted_float))

        save_similarity_scores(user, scores, db)
        return True
    except Exception as e:
        similarity_logger.error(f"[ERROR] 유저 {user.id} 유사도 계산 실패: {str(e)}")
        return False

# === [8] 비동기 자동화 ===
async def async_auto_compute_user_similarity(user: User, db: Session, job_posts: list) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, auto_compute_user_similarity, user, db, job_posts)

# === [9] 전체 공고 점수 반환 함수 : 프론트용 ===
def compute_similarity_scores(user: User, job_posts: list) -> list:
    user_vec = get_user_embedding(user)
    used_cols = [
        "name", "gender", "university", "major", "gpa",
        "education_status", "degree", "language_score",
        "desired_job", "working_year",
        "skills_with_proficiency", "certificates",
        "experiences_text"
    ]
    empty_values = {"", "None", "[]", "{}", "nan", "없음", "없어요", "없다", "null", "NULL"}

    # 사용자 정보를 딕셔너리로 변환 (SQLAlchemy 객체의 __dict__ 대신)
    user_dict = {
        "name": user.name,
        "gender": user.gender,
        "university": user.university,
        "major": user.major,
        "gpa": getattr(user, "gpa", None),
        "education_status": user.education_status,
        "degree": user.degree,
        "language_score": user.language_score,
        "desired_job": user.desired_job,
        "working_year": user.working_year,
        "skills_with_proficiency": ', '.join([f"{s.skill.name}({s.proficiency})" for s in user.user_skills]),
        "certificates": ', '.join([c.certificate.name for c in user.user_certificates]),
        "experiences_text": " | ".join([
            f"{exp.name}, {exp.period}, {exp.description}"
            for exp in user.experiences
        ]) if user.experiences else None
    }

    results = []
    for job in job_posts:
        job_vec = np.array(job.full_embedding)
        job_vec = job_vec / np.linalg.norm(job_vec) if np.linalg.norm(job_vec) > 0 else job_vec
        sim = cosine_similarity([user_vec], [job_vec])[0][0]
        adjusted = adjust_similarity_score(sim, job.applicant_type, user_dict, used_cols, empty_values)
        # numpy 타입을 Python float로 변환
        adjusted_float = float(adjusted) if hasattr(adjusted, 'item') else adjusted
        results.append((job.id, adjusted_float))
    return results

# === [10] 상위 30개 공고 ID만 반환 : recommender 연동용 ===
def get_top_job_ids(user: User, job_posts: list, top_k: int = 30) -> List[int]:
    scored = compute_similarity_scores(user, job_posts)
    top_jobs = sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]
    return [job_id for job_id, _ in top_jobs]

# === [11] 기존 호환성을 위한 함수들 ===
def auto_compute_all_users_similarity(db: Session) -> dict:
    """모든 사용자의 유사도 점수 자동 계산 (기존 호환성)"""
    try:
        similarity_logger.info("전체 사용자 유사도 자동 계산 시작")
        users = db.query(User).all()
        job_posts = db.query(JobPost).filter(JobPost.full_embedding.isnot(None)).all()
        
        results = {
            "total_users": len(users),
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "details": []
        }
        
        for user in users:
            try:
                if should_recompute_similarity(user, db):
                    success = auto_compute_user_similarity(user, db, job_posts)
                    if success:
                        results["success_count"] += 1
                        results["details"].append({
                            "user_id": user.id,
                            "user_name": user.name,
                            "status": "success"
                        })
                    else:
                        results["error_count"] += 1
                        results["details"].append({
                            "user_id": user.id,
                            "user_name": user.name,
                            "status": "failed"
                        })
                else:
                    results["skipped_count"] += 1
                    results["details"].append({
                        "user_id": user.id,
                        "user_name": user.name,
                        "status": "skipped"
                    })
            except Exception as e:
                results["error_count"] += 1
                results["details"].append({
                    "user_id": user.id,
                    "user_name": getattr(user, 'name', 'Unknown'),
                    "status": "error",
                    "error": str(e)
                })
        
        similarity_logger.info(f"전체 사용자 유사도 자동 계산 완료: 성공 {results['success_count']}, 실패 {results['error_count']}, 건너뜀 {results['skipped_count']}")
        return results
    except Exception as e:
        similarity_logger.error(f"전체 사용자 유사도 자동 계산 실패: {str(e)}")
        return {
            "total_users": 0,
            "success_count": 0,
            "error_count": 1,
            "skipped_count": 0,
            "details": [{"error": str(e)}]
        }

def auto_compute_similarity_for_new_job(job_id: int, db: Session) -> bool:
    """새로운 채용공고에 대한 모든 사용자의 유사도 점수 재계산 (기존 호환성)"""
    try:
        similarity_logger.info(f"새 채용공고 {job_id}에 대한 전체 사용자 유사도 재계산 시작")
        users = db.query(User).all()
        job_posts = db.query(JobPost).filter(JobPost.full_embedding.isnot(None)).all()
        
        success_count = 0
        error_count = 0
        
        for user in users:
            try:
                success = auto_compute_user_similarity(user, db, job_posts)
                if success:
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                similarity_logger.error(f"사용자 {user.id} 유사도 재계산 실패: {str(e)}")
        
        similarity_logger.info(f"새 채용공고 {job_id}에 대한 유사도 재계산 완료: 성공 {success_count}, 실패 {error_count}")
        return success_count > 0
    except Exception as e:
        similarity_logger.error(f"새 채용공고 {job_id}에 대한 유사도 재계산 실패: {str(e)}")
        return False

async def async_auto_compute_all_users_similarity(db: Session) -> dict:
    """비동기 전체 사용자 유사도 자동 계산 (기존 호환성)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, auto_compute_all_users_similarity, db)

async def async_auto_compute_similarity_for_new_job(job_id: int, db: Session) -> bool:
    """비동기 새 채용공고에 대한 유사도 재계산 (기존 호환성)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, auto_compute_similarity_for_new_job, job_id, db) 