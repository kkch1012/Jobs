'''
로드맵 추천 모델링 로직 모듈
갭 분석 결과와 로드맵을 매칭하여 사용자에게 최적의 로드맵을 추천합니다.
'''
import pandas as pd
import ast
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.user_skill import UserSkill
from app.models.skill import Skill
from app.models.roadmap import Roadmap
from app.services.gap_model import extract_top_gap_items, get_trend_skills_by_category
import logging

logger = logging.getLogger(__name__)

# === 유저 스킬 조회 ===
def get_user_skills_with_proficiency(user_id: int, db: Session) -> List[str]:
    """
    사용자의 스킬 목록을 조회합니다.
    
    Args:
        user_id: 사용자 ID
        db: 데이터베이스 세션
    
    Returns:
        사용자 스킬명 리스트
    """
    try:
        user_skills = db.query(
            Skill.name
        ).join(
            UserSkill, Skill.id == UserSkill.skill_id
        ).filter(
            UserSkill.user_id == user_id
        ).all()
        
        return [skill.name for skill in user_skills]
        
    except Exception as e:
        logger.error(f"사용자 스킬 조회 실패: {str(e)}")
        return []

# === 스킬 점수 계산 ===
def score_skills(user_skills: List[str], top_skills: List[str], skill_order: List[str]) -> pd.DataFrame:
    """
    스킬 점수를 계산합니다.
    
    Args:
        user_skills: 사용자 보유 스킬 리스트
        top_skills: 갭 분석에서 추출된 상위 스킬 리스트
        skill_order: 트렌드 스킬 순서 리스트
    
    Returns:
        점수가 계산된 스킬 DataFrame
    """
    # 소문자로 변환하여 비교
    user_skills_set = set(s.lower() for s in user_skills)
    top_skills_set = set(s.lower() for s in top_skills)
    skill_order_lower = [s.lower() for s in skill_order]

    # 1. 유저가 안 가진 추천 스킬 → except_skills
    except_skills = user_skills_set - top_skills_set

    # 2. except_skills 중 skill_order에 포함된 것 → unmatched
    unmatched_skills = [s for s in skill_order_lower if s in except_skills]

    # 3. unmatched 제외한 최종 스킬 리스트
    final_skills = [s for s in skill_order_lower if s not in unmatched_skills]

    # 4. 점수 계산
    base_score = len(final_skills)
    scored_skills = []
    for i, skill in enumerate(final_skills):
        base = base_score - i
        bonus = 5 if skill in top_skills_set else 0
        total_score = base + bonus
        scored_skills.append({
            "skill": skill,
            "base_score": base,
            "bonus": bonus,
            "total_score": total_score
        })

    scored_df = pd.DataFrame(scored_skills).sort_values(by="total_score", ascending=False).reset_index(drop=True)
    return scored_df

# === 로드맵 점수화 적용 함수 ===
def apply_score_to_roadmaps(roadmaps: pd.DataFrame, scored_df: pd.DataFrame) -> pd.DataFrame:
    """
    로드맵에 스킬 점수를 적용합니다.
    
    Args:
        roadmaps: 로드맵 DataFrame
        scored_df: 점수가 계산된 스킬 DataFrame
    
    Returns:
        점수가 적용된 로드맵 DataFrame
    """
    # 스킬-점수 매핑
    skill_score_map = dict(zip(scored_df["skill"], scored_df["total_score"]))

    # 점수 계산 함수
    def calculate_score(skill_list):
        if not skill_list:
            return 0
        
        # 리스트가 아닌 경우 처리
        if isinstance(skill_list, str):
            try:
                skill_list = ast.literal_eval(skill_list)
            except (ValueError, SyntaxError):
                # 파싱 실패 시 문자열을 리스트로 변환
                skill_list = [skill_list]
        
        if not isinstance(skill_list, list):
            return 0
            
        normalized = [s.lower().strip() for s in skill_list if s]
        return sum(skill_score_map.get(skill, 0) for skill in normalized)

    # 점수 계산 및 정렬
    roadmaps["skill_score"] = roadmaps["skill_description"].apply(calculate_score)
    return roadmaps.sort_values(by="skill_score", ascending=False).reset_index(drop=True)

# === 메인 로드맵 추천 함수 ===
def roadmap_recommendation(
    user_id: int, 
    category: str, 
    top_skills: List[str], 
    gap_result_text: str, 
    db: Session
) -> pd.DataFrame:
    """
    사용자에게 맞는 로드맵을 추천합니다.
    
    Args:
        user_id: 사용자 ID
        category: 직무 카테고리
        top_skills: 갭 분석에서 추출된 상위 스킬 리스트
        gap_result_text: 갭 분석 결과 텍스트
        db: 데이터베이스 세션
    
    Returns:
        추천 로드맵 DataFrame
    """
    try:
        logger.info(f"로드맵 추천 시작 - 사용자 ID: {user_id}, 카테고리: {category}")
        
        # 1. 유저 보유 스킬 조회
        user_skills = get_user_skills_with_proficiency(user_id, db)
        logger.info(f"사용자 스킬 조회 완료: {len(user_skills)}개")

        # 2. 상위 직무에 따른 스킬 트렌드 조회
        skill_order = get_trend_skills_by_category(category, db)
        logger.info(f"트렌드 스킬 조회 완료: {len(skill_order)}개")

        # 3. 스킬 점수 계산
        scored_df = score_skills(user_skills, top_skills, skill_order)
        logger.info(f"스킬 점수 계산 완료: {len(scored_df)}개")

        # 4. 로드맵 조회 및 점수 적용
        roadmaps_query = db.query(Roadmap).all()
        roadmaps = pd.DataFrame([
            {
                'id': roadmap.id,
                'name': roadmap.name,
                'type': roadmap.type,
                'skill_description': roadmap.skill_description,
                'start_date': roadmap.start_date,
                'end_date': roadmap.end_date,
                'status': roadmap.status,
                'deadline': roadmap.deadline,
                'location': roadmap.location,
                'onoff': roadmap.onoff,
                'participation_time': roadmap.participation_time,
                'company': roadmap.company,
                'program_course': roadmap.program_course
            }
            for roadmap in roadmaps_query
        ])
        
        if roadmaps.empty:
            logger.warning("로드맵 데이터가 없습니다.")
            return pd.DataFrame()

        # 5. 점수 적용
        scored_roadmaps = apply_score_to_roadmaps(roadmaps, scored_df)
        logger.info(f"로드맵 점수 적용 완료: {len(scored_roadmaps)}개")

        return scored_roadmaps
        
    except Exception as e:
        logger.error(f"로드맵 추천 실패: {str(e)}")
        raise

# === API 엔드포인트용 함수 ===
def get_roadmap_recommendations(
    user_id: int, 
    category: str, 
    gap_result_text: str, 
    db: Session,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    API 엔드포인트에서 사용할 로드맵 추천 함수
    
    Args:
        user_id: 사용자 ID
        category: 직무 카테고리
        gap_result_text: 갭 분석 결과 텍스트
        db: 데이터베이스 세션
        limit: 반환할 로드맵 개수
    
    Returns:
        추천 로드맵 리스트
    """
    try:
        # 갭 분석에서 상위 스킬 추출
        top_skills = extract_top_gap_items(gap_result_text)
        logger.info(f"갭 분석에서 추출된 상위 스킬: {top_skills}")
        
        # 로드맵 추천 수행
        recommended_roadmaps = roadmap_recommendation(
            user_id, category, top_skills, gap_result_text, db
        )
        
        # 상위 N개만 반환
        top_roadmaps = recommended_roadmaps.head(limit)
        
        # 딕셔너리 리스트로 변환
        result = []
        for _, roadmap in top_roadmaps.iterrows():
            roadmap_dict = roadmap.to_dict()
            # datetime 객체를 문자열로 변환
            for key, value in roadmap_dict.items():
                if hasattr(value, 'isoformat'):
                    roadmap_dict[key] = value.isoformat()
            result.append(roadmap_dict)
        
        return result
        
    except Exception as e:
        logger.error(f"로드맵 추천 API 실패: {str(e)}")
        return []