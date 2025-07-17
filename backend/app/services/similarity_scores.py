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

# 임베딩 모델 싱글턴
_embedder = None
def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("intfloat/multilingual-e5-large")
    return _embedder

def summarize_user_for_embedding(user: User) -> str:
    """사용자 정보를 임베딩용 텍스트로 요약"""
    # ORM 객체에서 정보 추출
    skills = [f"{s.skill.name}({s.proficiency})" for s in user.user_skills]
    certs = [c.certificate.name for c in user.user_certificates]
    exp = user.experiences[0] if user.experiences else None
    exp_text = f"{exp.name}, {exp.period}, {exp.description}" if exp else "없음"
    
    # language_score 처리
    lang_score = '없음'
    if getattr(user, 'language_score', None) is not None and isinstance(user.language_score, dict):
        lang_score = user.language_score.get('OPIC', '없음')
    
    # desired_job을 JSON 배열로 처리
    desired_jobs = user.desired_job if isinstance(user.desired_job, list) else []
    desired_job_text = ', '.join(desired_jobs) if len(desired_jobs) > 0 else '없음'
    
    return (
        f"이름: {user.name}\n"
        f"성별: {user.gender}, 학교: {user.university}, 학과: {user.major}, "
        f"학위: {user.degree}, 학력 상태: {user.education_status}\n"
        f"희망 직무: {desired_job_text}\n"
        f"어학 점수: {lang_score}\n"
        f"기술 스택: {', '.join(skills) or '없음'}\n"
        f"자격증: {', '.join(certs) or '없음'}\n"
        f"경험: {exp_text}"
    )

def get_user_embedding(user: User) -> np.ndarray:
    """사용자 정보를 임베딩 벡터로 변환"""
    user_text = summarize_user_for_embedding(user)
    embedder = get_embedder()
    embedding = embedder.encode(user_text)
    return np.array(embedding)

def compute_similarity_scores(user: User, db: Session) -> list:
    """사용자와 모든 채용공고 간의 유사도 점수 계산"""
    user_embedding = get_user_embedding(user)
    jobs = db.query(JobPost).all()
    
    if not jobs:
        return []
    
    # 유효한 임베딩을 가진 채용공고만 필터링
    valid_jobs = []
    valid_embeddings = []
    
    for job in jobs:
        if hasattr(job, 'full_embedding') and job.full_embedding is not None:
            try:
                # 임베딩을 numpy 배열로 변환
                job_embedding = np.array(job.full_embedding)
                if job_embedding.size > 0:  # 빈 배열이 아닌지 확인
                    valid_jobs.append(job)
                    valid_embeddings.append(job_embedding)
            except Exception as e:
                similarity_logger.warning(f"Job {job.id} 임베딩 변환 실패: {e}")
                continue
    
    if not valid_jobs:
        similarity_logger.warning("유효한 임베딩을 가진 채용공고가 없습니다.")
        return []
    
    # 디버깅 정보 출력
    similarity_logger.info(f"사용자 임베딩 형태: {user_embedding.shape}")
    similarity_logger.info(f"사용자 임베딩 범위: {user_embedding.min():.4f} ~ {user_embedding.max():.4f}")
    similarity_logger.info(f"유효한 채용공고 수: {len(valid_jobs)}")
    
    # 첫 번째 채용공고 임베딩 정보 출력
    if valid_embeddings:
        first_job_emb = valid_embeddings[0]
        similarity_logger.info(f"첫 번째 채용공고 임베딩 형태: {first_job_emb.shape}")
        similarity_logger.info(f"첫 번째 채용공고 임베딩 범위: {first_job_emb.min():.4f} ~ {first_job_emb.max():.4f}")
    
    # 임베딩 스택 생성
    job_embeddings = np.vstack(valid_embeddings)
    
    # 차원 확인
    if user_embedding.shape[0] != job_embeddings.shape[1]:
        similarity_logger.error(f"차원 불일치: 사용자 {user_embedding.shape[0]} vs 채용공고 {job_embeddings.shape[1]}")
        return []
    
    # 코사인 유사도 계산
    similarity_scores = cosine_similarity([user_embedding], job_embeddings)[0]
    
    # 결과 확인
    similarity_logger.info(f"유사도 점수 범위: {similarity_scores.min():.4f} ~ {similarity_scores.max():.4f}")
    similarity_logger.info(f"유사도 점수 평균: {similarity_scores.mean():.4f}")
    
    return [(valid_jobs[i].id, float(similarity_scores[i])) for i in range(len(valid_jobs))]

def save_similarity_scores(user: User, scores: list, db: Session):
    """계산된 유사도 점수를 데이터베이스에 저장"""
    # 기존 유사도 점수 삭제
    db.query(UserSimilarity).filter(UserSimilarity.user_id == user.id).delete()
    
    # 새로운 유사도 점수 저장
    for job_id, sim in scores:
        db.add(UserSimilarity(user_id=user.id, job_post_id=job_id, similarity=sim))
    
    db.commit()

def get_user_similarity_scores(user_id: int, db: Session, limit: int = 20) -> list:
    """사용자의 유사도 점수를 높은 순으로 조회"""
    similarities = (
        db.query(UserSimilarity)
        .filter(UserSimilarity.user_id == user_id)
        .order_by(UserSimilarity.similarity.desc())
        .limit(limit)
        .all()
    )
    return similarities

# === 자동화 함수들 ===

def should_recompute_similarity(user: User, db: Session, max_age_hours: int = 24) -> bool:
    """사용자의 유사도 점수를 재계산해야 하는지 확인"""
    # 가장 최근 유사도 점수 조회
    latest_similarity = (
        db.query(UserSimilarity)
        .filter(UserSimilarity.user_id == user.id)
        .order_by(UserSimilarity.created_at.desc())
        .first()
    )
    
    if not latest_similarity:
        similarity_logger.info(f"사용자 {user.id}의 유사도 점수가 없습니다. 재계산이 필요합니다.")
        return True
    
    # 마지막 계산 시간 확인
    time_diff = datetime.utcnow() - latest_similarity.created_at
    if time_diff > timedelta(hours=max_age_hours):
        similarity_logger.info(f"사용자 {user.id}의 유사도 점수가 {time_diff.total_seconds() /3600:0.1f}시간 전에 계산되었습니다. 재계산이 필요합니다.")
        return True
    
    similarity_logger.info(f"사용자 {user.id}의 유사도 점수가 최신입니다. 재계산이 필요하지 않습니다.")
    return False

def auto_compute_user_similarity(user: User, db: Session) -> bool:
    """사용자 유사도 자동 계산"""
    try:
        similarity_logger.info(f"사용자 {user.id}의 유사도 자동 계산 시작")
        # 유사도 점수 계산
        scores = compute_similarity_scores(user, db)
        if not scores:
            similarity_logger.warning(f"사용자 {user.id}의 유사도 계산 결과가 없습니다.")
            return False
        # 데이터베이스에 저장
        save_similarity_scores(user, scores, db)
        similarity_logger.info(f"사용자 {user.id}의 유사도 자동 계산 완료: {len(scores)}개 점수 저장")
        return True
    except Exception as e:
        similarity_logger.error(f"사용자 {user.id}의 유사도 자동 계산 실패: {str(e)}")
        return False

def auto_compute_all_users_similarity(db: Session) -> dict:
    """모든 사용자의 유사도 점수 자동 계산"""
    try:
        similarity_logger.info("전체 사용자 유사도 자동 계산 시작")
        users = db.query(User).all()
        results = {
            "total_users": len(users),
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "details": []
        }
        for user in users:
            try:
                # 재계산 필요 여부 확인
                if should_recompute_similarity(user, db):
                    success = auto_compute_user_similarity(user, db)
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
        similarity_logger.info(f"전체 사용자 유사도 자동 계산 완료: 성공 {results['success_count']},실패 {results['error_count']}, 건너뜀 {results['skipped_count']}")
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
    """새로운 채용공고에 대한 모든 사용자의 유사도 점수 재계산"""
    try:
        similarity_logger.info(f"새 채용공고 {job_id}에 대한 전체 사용자 유사도 재계산 시작")
        users = db.query(User).all()
        success_count = 0
        error_count = 0
        for user in users:
            try:
                success = auto_compute_user_similarity(user, db)
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

async def async_auto_compute_user_similarity(user: User, db: Session) -> bool:
    """비동기 사용자 유사도 자동 계산"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, auto_compute_user_similarity, user, db)

async def async_auto_compute_all_users_similarity(db: Session) -> dict:
    """비동기 전체 사용자 유사도 자동 계산"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, auto_compute_all_users_similarity, db)

async def async_auto_compute_similarity_for_new_job(job_id: int, db: Session) -> bool:
    """비동기 새 채용공고에 대한 유사도 재계산"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, auto_compute_similarity_for_new_job, job_id, db) 