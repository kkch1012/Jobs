"""
직무 추천 로직 모듈
사용자의 기술 스택과 시장 트렌드를 분석하여 최적의 직무를 추천합니다.
"""
import pandas as pd
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.user import User
from app.models.user_skill import UserSkill
from app.models.job_required_skill import JobRequiredSkill
from app.models.weekly_skill_stat import WeeklySkillStat
from app.utils.logger import app_logger


def extract_user_skills_with_proficiency(user: User) -> str:
    """
    사용자 ORM 객체에서 기술 스택과 숙련도를 문자열로 추출
    
    Args:
        user: User 모델 객체
        
    Returns:
        기술 스택 문자열 (예: "django(하), python(중), react(상)")
    """
    if not user.user_skills:
        return ""

    skills_list = []
    for user_skill in user.user_skills:
        if user_skill.skill and user_skill.proficiency:
            skill_name = user_skill.skill.name.strip()
            proficiency = user_skill.proficiency.strip()
            skills_list.append(f"{skill_name}({proficiency})")
    
    return ', '.join(skills_list)


def get_job_categories(db: Session) -> List[str]:
    """
    데이터베이스에서 직무 카테고리 리스트 조회
    
    Args:
        db: 데이터베이스 세션
        
    Returns:
        직무 카테고리 리스트
    """
    try:
        job_names = db.query(JobRequiredSkill.job_name).distinct().all()
        categories = [name[0] for name in job_names if name[0]]
        
        app_logger.info(f"직무 카테고리 {len(categories)}개 조회 완료")
        return categories
        
    except Exception as e:
        app_logger.error(f"직무 카테고리 조회 실패: {str(e)}")
        # 오류 발생 시 기본 리스트 반환
        return [
            "소프트웨어 엔지니어", "서버 개발자", "프론트엔드 개발자", "자바 개발자", "웹 개발자",
            "파이썬 개발자", "머신러닝 엔지니어", "데이터 엔지니어", "DevOps / 시스템 관리자",
            "데이터 사이언티스트", "QA,테스트 엔지니어", "안드로이드 개발자", "iOS 개발자"
        ]


def get_trend_skills_by_category(db: Session, category: str, limit: int = 200) -> List[str]:
    """
    해당 직무 카테고리에 대한 트렌드 스킬 리스트 조회
    
    Args:
        db: 데이터베이스 세션
        category: 직무 카테고리명
        limit: 반환할 스킬 개수 (기본값: 200)
        
    Returns:
        트렌드 스킬 리스트 (인기도 순)
    """
    try:
        query = text("""
            SELECT wss.skill, jrs.job_name, SUM(wss.count) AS total_count
            FROM weekly_skill_stats wss
            JOIN job_required_skills jrs ON wss.job_role_id = jrs.id
            WHERE jrs.job_name = :category
            GROUP BY wss.skill, jrs.job_name
            ORDER BY total_count DESC
            LIMIT :limit
        """)
        
        result = db.execute(query, {"category": category, "limit": limit})
        skills = [row[0] for row in result.fetchall()]
        
        app_logger.info(f"직무 '{category}'의 트렌드 스킬 {len(skills)}개 조회 완료")
        return skills
        
    except Exception as e:
        app_logger.error(f"트렌드 스킬 조회 실패 - 직무: {category}, 오류: {str(e)}")
        return []


def calculate_skill_score(user_skills_str: str, trend_skills: List[str], verbose: bool = False) -> Tuple[float, List[Dict]]:
    """
    사용자 기술 스택과 트렌드 스킬을 비교하여 점수 계산
    
    Args:
        user_skills_str: 사용자 기술 스택 문자열
        trend_skills: 트렌드 스킬 리스트
        verbose: 상세 로그 출력 여부
        
    Returns:
        (총 점수, 스킬별 상세 정보)
    """
    score = 0.0
    proficiency_weights = {"하": 1.0, "중": 1.2, "상": 2.0}
    skill_details = []

    # 사용자 기술 스택 파싱
    user_skill_map = {}
    for skill in user_skills_str.split(","):
        skill = skill.strip()
        if "(" in skill and ")" in skill:
            name, prof = skill.split("(")
            user_skill_map[name.strip().lower()] = prof.strip(")").strip()

    # 트렌드 스킬과 매칭하여 점수 계산
    for idx, trend_skill in enumerate(trend_skills):
        trend_score = len(trend_skills) - idx  # 순위에 따른 점수
        skill_key = trend_skill.strip().lower()

        if skill_key in user_skill_map:
            prof = user_skill_map[skill_key]
            weight = proficiency_weights.get(prof, 1.0)
            contribution = trend_score * weight
            score += contribution
            
            skill_details.append({
                "skill": skill_key,
                "rank": idx + 1,
                "base_score": trend_score,
                "proficiency": prof,
                "weight": weight,
                "contribution": contribution
            })

    if verbose:
        app_logger.info(f"총 점수: {score:.2f}")
        app_logger.info("==== 스킬별 기여도 ====")
        for detail in skill_details:
            app_logger.info(
                f"- {detail['skill']} (순위 {detail['rank']}, 숙련도: {detail['proficiency']}) "
                f"→ {detail['base_score']}점 × {detail['weight']} = {detail['contribution']:.2f}"
            )

    return score, skill_details


def recommend_best_job(user_skills: str, trend_skill_dict: Dict[str, List[str]], db: Session, verbose: bool = False) -> Dict:
    """
    사용자 기술 스택에 가장 적합한 직무 추천
    
    Args:
        user_skills: 사용자 기술 스택 문자열
        trend_skill_dict: 직무별 트렌드 스킬 딕셔너리
        db: 데이터베이스 세션
        verbose: 상세 로그 출력 여부
        
    Returns:
        추천 결과 딕셔너리
    """
    best_job = None
    best_score = -1
    best_details = []
    job_scores = []

    job_categories = get_job_categories(db)
    
    for job in job_categories:
        if verbose:
            app_logger.info(f"[{job}] 분석 중...")
            
        trend_skills = trend_skill_dict.get(job, [])
        score, details = calculate_skill_score(user_skills, trend_skills, verbose=verbose)
        
        job_scores.append({
            "job_name": job,
            "score": score,
            "details": details
        })

        if score > best_score:
            best_score = score
            best_job = job
            best_details = details

    if verbose:
        app_logger.info(f"최종 추천 직무: {best_job} (점수: {best_score:.2f})")

    return {
        "recommended_job": best_job,
        "score": best_score,
        "details": best_details,
        "all_scores": job_scores
    }


def generate_trend_skill_dict(db: Session) -> Dict[str, List[str]]:
    """
    전체 직무의 트렌드 스킬 딕셔너리 생성
    
    Args:
        db: 데이터베이스 세션
        
    Returns:
        직무별 트렌드 스킬 딕셔너리
    """
    trend_dict = {}
    job_categories = get_job_categories(db)
    
    for job in job_categories:
        trend_dict[job] = get_trend_skills_by_category(db, job)
    
    app_logger.info(f"트렌드 스킬 딕셔너리 생성 완료 - {len(trend_dict)}개 직무")
    return trend_dict


def recommend_job_for_user(user: User, db: Session, verbose: bool = False) -> Dict:
    """
    사용자에게 최적의 직무를 추천하는 메인 함수
    
    Args:
        user: User 모델 객체
        db: 데이터베이스 세션
        verbose: 상세 로그 출력 여부
        
    Returns:
        추천 결과 딕셔너리
    """
    try:
        # 사용자 기술 스택 추출
        user_skills = extract_user_skills_with_proficiency(user)
        if not user_skills:
            return {
                "recommended_job": None,
                "score": 0,
                "message": "등록된 기술 스택이 없습니다.",
                "details": []
            }

        # 트렌드 스킬 딕셔너리 생성
        trend_dict = generate_trend_skill_dict(db)
        
        # 직무 추천 실행
        result = recommend_best_job(user_skills, trend_dict, db, verbose=verbose)
        
        app_logger.info(f"직무 추천 완료 - 사용자: {user.id}, 추천 직무: {result['recommended_job']}")
        return result
        
    except Exception as e:
        app_logger.error(f"직무 추천 실패 - 사용자: {user.id}, 오류: {str(e)}")
        return {
            "recommended_job": None,
            "score": 0,
            "message": f"직무 추천 중 오류가 발생했습니다: {str(e)}",
            "details": []
        }


def get_job_recommendation_simple(user: User, db: Session) -> str:
    """
    간단한 직무명만 반환하는 함수 (기존 호환성 유지)
    
    Args:
        user: User 모델 객체
        db: 데이터베이스 세션
        
    Returns:
        추천 직무명 문자열
    """
    result = recommend_job_for_user(user, db)
    return result.get("recommended_job", "직무 추천 불가")