import os
import re
import logging
from openai import OpenAI
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Dict, Any, Optional

# 로거 설정
logger = logging.getLogger(__name__)

# 환경 변수 확인 및 로깅
api_key = os.getenv("OPENROUTER_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL")

logger.info(f"OPENROUTER_API_KEY 설정 여부: {'설정됨' if api_key else '설정되지 않음'}")
logger.info(f"OPENROUTER_BASE_URL 설정 여부: {'설정됨' if base_url else '설정되지 않음'}")

if not api_key:
    logger.error("OPENROUTER_API_KEY가 설정되지 않았습니다!")
if not base_url:
    logger.error("OPENROUTER_BASE_URL가 설정되지 않았습니다!")

# OpenAI 클라이언트 초기화 (OpenRouter API 키 및 BASE_URL 사용)
client = OpenAI(
    api_key=api_key,
    base_url=base_url
)


# 트렌드 스킬 리스트 조회 함수
def get_trend_skills_by_category(category: str, db: Session) -> List[str]:
    """주간 스킬 통계에서 해당 직무의 트렌드 스킬 리스트를 조회합니다."""
    from app.models.weekly_skill_stat import WeeklySkillStat
    from app.models.job_required_skill import JobRequiredSkill
    
    # 직무 ID 조회
    job_role = db.query(JobRequiredSkill).filter(
        JobRequiredSkill.job_name == category
    ).first()
    
    if not job_role:
        return []
    
    # 해당 직무의 주간 스킬 통계 조회 (최근 데이터 기준)
    stats = db.query(
        WeeklySkillStat.skill,
        func.sum(WeeklySkillStat.count).label('total_count')
    ).filter(
        WeeklySkillStat.job_role_id == job_role.id
    ).group_by(
        WeeklySkillStat.skill
    ).order_by(
        func.sum(WeeklySkillStat.count).desc()
    ).all()
    
    return [stat.skill for stat in stats]


# 유저 정보 조회 함수
def get_user_summary(user_id: int, db: Session) -> Optional[Dict[str, Any]]:
    """사용자의 이력서 정보를 종합적으로 조회합니다."""
    from app.models.user import User
    from app.models.user_skill import UserSkill
    from app.models.skill import Skill
    from app.models.user_certificate import UserCertificate
    from app.models.certificate import Certificate
    from app.models.user_experience import UserExperience
    
    # 사용자 기본 정보 조회
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    # 사용자 스킬 정보 조회 (정규화된 스킬명 사용)
    user_skills = db.query(
        Skill.name,
        UserSkill.proficiency
    ).join(
        UserSkill, Skill.id == UserSkill.skill_id
    ).filter(
        UserSkill.user_id == user_id
    ).all()
    
    logger.info(f"사용자 스킬 조회 결과: {user_skills}")
    
    # 스킬명 정규화 및 매칭 개선
    normalized_skills = []
    for skill_name, proficiency in user_skills:
        # 스킬명 정규화 (대소문자, 공백, 특수문자 처리)
        normalized = skill_name.strip().lower()
        # 원본 스킬명과 숙련도를 함께 저장
        normalized_skills.append(f"{skill_name}({proficiency})")
    
    skills_with_proficiency = ', '.join(normalized_skills)
    
    # 스킬 매칭을 위한 추가 정보도 저장
    skill_mapping = {}
    for skill_name, proficiency in user_skills:
        # 다양한 형태로 매칭 가능하도록 저장
        normalized = skill_name.strip().lower()
        skill_mapping[normalized] = {
            'original': skill_name,
            'proficiency': proficiency
        }
        # 유사 스킬명도 추가
        if 'javascript' in normalized:
            skill_mapping['js'] = {'original': skill_name, 'proficiency': proficiency}
        elif 'react' in normalized:
            skill_mapping['react.js'] = {'original': skill_name, 'proficiency': proficiency}
        elif 'python' in normalized:
            skill_mapping['python3'] = {'original': skill_name, 'proficiency': proficiency}
    
    logger.info(f"스킬 매핑 정보: {skill_mapping}")
    
    # 사용자 자격증 정보 조회
    user_certificates = db.query(
        Certificate.name
    ).join(
        UserCertificate, Certificate.id == UserCertificate.certificate_id
    ).filter(
        UserCertificate.user_id == user_id
    ).all()
    
    certificates = ', '.join([cert[0] for cert in user_certificates])
    
    # 최근 경험 정보 조회
    latest_experience = db.query(UserExperience).filter(
        UserExperience.user_id == user_id
    ).order_by(
        UserExperience.period.desc()
    ).first()
    
    # 언어 점수 (OPIC) 추출
    opic_score = "없음"
    try:
        language_score = getattr(user, 'language_score', None)
        if language_score and isinstance(language_score, dict):
            opic_score = language_score.get('OPIC', '없음')
    except:
        opic_score = "없음"
    
    return {
        'name': user.name,
        'gender': user.gender,
        'university': user.university,
        'major': user.major,
        'degree': user.degree,
        'education_status': user.education_status,
        'desired_job': user.desired_job,
        'opic_score': opic_score,
        'skills_with_proficiency': skills_with_proficiency,
        'certificates': certificates,
        'latest_exp_name': latest_experience.name if latest_experience else '없음',
        'latest_exp_period': latest_experience.period if latest_experience else '없음',
        'latest_exp_description': latest_experience.description if latest_experience else '없음'
    }


# 갭 분석 프롬프트 생성 함수 (시각화용 - 5개)
def make_gap_analysis_prompt_visualization(user_data: Dict[str, Any], skill_trend: List[str], job_category: str) -> str:
    name = user_data['name']
    major = user_data['major']
    university = user_data['university']
    degree = user_data['degree']
    education_status = user_data['education_status']
    desired_jobs = ', '.join(user_data['desired_job']) if isinstance(user_data['desired_job'], list) else user_data['desired_job']
    opic_score = user_data.get('opic_score') or "없음"
    skills = user_data['skills_with_proficiency']
    certs = user_data['certificates']
    exp_name = user_data['latest_exp_name']
    exp_period = user_data['latest_exp_period']
    exp_desc = user_data['latest_exp_description']

    return f"""
당신은 채용 담당자를 위한 커리어 갭 분석 전문가입니다.
모든 분석 결과는 반드시 한국어로 작성해주세요.

[지원자 정보]
이름: {name}
학교: {university}, 전공: {major}
학위: {degree}, 학력 상태: {education_status}
어학 점수 (OPIC): {opic_score}
기술 스택 (숙련도 포함): {skills}
자격증: {certs}
경험: {exp_name} / 기간: {exp_period}
경험 설명: {exp_desc}

[기준 역량 리스트 - {job_category}]
다음은 최근 **{job_category}** 직무에서 실제 채용공고를 분석한 주요 역량 리스트입니다.
이 리스트는 실제 채용공고에서 추출된 기술 스택과 요구사항을 빈도순으로 정렬한 것입니다:
{', '.join(skill_trend)}

[분석 요청사항]
위 기준 역량 리스트를 상단부터 순서대로 확인하며, 지원자와의 격차를 분석해 주세요.

**중요한 분석 기준:**
1. **기술 스택 매칭**: 지원자의 기술 스택과 채용공고 요구사항을 정확히 매칭해주세요.
   - 예: "Python(중)" → "Python" 요구사항과 매칭
   - 예: "Java(하)" → "Java" 요구사항과 매칭 (하지만 숙련도 부족)
   - 예: "React" → "React.js", "React Native" 등 유사 기술과 매칭 고려

2. **우선순위**: 리스트 상단에 있을수록 **우선순위가 높습니다**.
   - 상위 10개는 필수 기술로 간주
   - 하위 기술은 선택 기술로 간주

3. **숙련도 평가**: 
   - **없음**: 해당 기술을 전혀 보유하지 않음
   - **하**: 기초 수준 (학습 중이거나 간단한 프로젝트 경험)
   - **중**: 실무 가능 수준 (실제 프로젝트에서 사용 경험)
   - **상**: 전문가 수준 (복잡한 프로젝트에서 주도적 사용)

아래 형식에 따라 상위 5개의 격차 항목만 출력해 주세요:

보유여부, 숙련도는 이력서 기반 판단해주세요.

**1. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: 
  - 지원자가 보유했다면 **경험 기반 숙련도**를 참고해 부족한 이유를 설명해 주세요.
  - 보유하지 않았다면, 해당 역량이 왜 중요한지 간결하고 명확하게 (2~3줄 이내로) 설명해 주세요.

**2. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**3. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**4. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**5. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**기술 스택 매칭 시 주의사항:**
- "JavaScript"와 "JS"는 같은 기술로 간주
- "React"와 "React.js"는 같은 기술로 간주
- "Python"과 "Python3"는 같은 기술로 간주
- "AWS"와 "Amazon Web Services"는 같은 기술로 간주

협업 경험 / 프로젝트 경험 / 운영 경험 등은 **경험 설명에 해당 키워드가 있거나 팀 기반 활동이면 있음으로 간주**해 주세요.  
예를 들어 "사내 API 개발 및 유지보수"는 협업이 포함된 활동입니다.

**기술 스택이 가장 중요한 분석 요소**이므로, 지원자의 기술 스택과 채용공고 요구사항을 정확히 매칭하여 분석해 주세요.
"""

# 갭 분석 프롬프트 생성 함수 (todo_list용 - 10개)
def make_gap_analysis_prompt_todo(user_data: Dict[str, Any], skill_trend: List[str], job_category: str) -> str:
    name = user_data['name']
    major = user_data['major']
    university = user_data['university']
    degree = user_data['degree']
    education_status = user_data['education_status']
    desired_jobs = ', '.join(user_data['desired_job']) if isinstance(user_data['desired_job'], list) else user_data['desired_job']
    opic_score = user_data.get('opic_score') or "없음"
    skills = user_data['skills_with_proficiency']
    certs = user_data['certificates']
    exp_name = user_data['latest_exp_name']
    exp_period = user_data['latest_exp_period']
    exp_desc = user_data['latest_exp_description']

    return f"""
당신은 채용 담당자를 위한 커리어 갭 분석 전문가입니다.
모든 분석 결과는 반드시 한국어로 작성해주세요.

[지원자 정보]
이름: {name}
학교: {university}, 전공: {major}
학위: {degree}, 학력 상태: {education_status}
어학 점수 (OPIC): {opic_score}
기술 스택 (숙련도 포함): {skills}
자격증: {certs}
경험: {exp_name} / 기간: {exp_period}
경험 설명: {exp_desc}

[기준 역량 리스트]
다음은 최근 **{job_category}** 직무에서 요구되는 주요 역량 리스트입니다.
이 리스트에는 기술 스택 뿐만 아니라, 협업 경험, 프로젝트 운영, 문서화 능력, 서비스 개선 등
**비기술적/경험 기반 역량**도 포함되어 있습니다:
{', '.join(skill_trend)}

[요청사항]
위 기준 역량 리스트를 상단부터 순서대로 확인하며, 지원자와의 격차를 분석해 주세요.

분석 순서는 다음과 같습니다:
1. 기준 역량 리스트 상단에 있을수록 **우선순위가 높습니다**.  
       반드시 리스트 순서를 기준으로 분석해주세요.
2. 각 항목마다 **지원자 보유 여부 및 숙련도(하/중/상)**를 참고해 격차를 판단해 주세요.
        단, **리스트 순서를 벗어난 재정렬은 하지 마세요**.
3. 보유 여부/숙련도에 따른 격차 판단 기준은 다음과 같습니다:
   - **보유하지 않은 경우** → 격차가 가장 큽니다.
   - **보유했지만 숙련도 '하'** → 그 다음 격차입니다.
   - **숙련도 '중'** → 상대적으로 덜한 격차입니다.
   - **숙련도 '상'**은 격차로 판단하지 않습니다.

아래 형식에 따라 상위 10개의 격차 항목만 출력해 주세요:

보유여부, 숙련도는 이력서 기반 판단해주세요.

**1. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: 
  - 지원자가 보유했다면 **경험 기반 숙련도**를 참고해 부족한 이유를 설명해 주세요.
  - 보유하지 않았다면, 해당 역량이 왜 중요한지 간결하고 명확하게 (2~3줄 이내로) 설명해 주세요.

**2. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**3. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**4. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**5. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**6. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**7. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**8. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**9. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

**10. [역량 이름]**
- 현재 보유 여부: 있음 / 없음
- 숙련도: 없음 / 하 / 중 / 상
- 필수 여부: 필수 / 선택
- 사유: (설명)

협업 경험 / 프로젝트 경험 / 운영 경험 등은 **경험 설명에 해당 키워드가 있거나 팀 기반 활동이면 있음으로 간주**해 주세요.  
예를 들어 "사내 API 개발 및 유지보수"는 협업이 포함된 활동입니다.

**비기술 역량도 중요**하니 기술 스택 외 항목도 반드시 포함하여 평가해 주세요.
"""


# LLM 호출 함수
def call_llm_for_gap_analysis(prompt: str) -> str:
    try:
        logger.info("LLM API 호출 시작")
        logger.info(f"API 키 확인: {api_key[:10] if api_key else 'None'}...")
        logger.info(f"Base URL: {base_url}")
        
        if not api_key:
            logger.error("API 키가 설정되지 않아 LLM 호출을 건너뜁니다.")
            return "API 키가 설정되지 않아 분석을 수행할 수 없습니다."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 채용 담당자를 위한 커리어 갭 분석 전문가입니다. 모든 분석 결과는 반드시 한국어로 작성해주세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        logger.info("LLM API 호출 성공")
        content = response.choices[0].message.content
        return content if content else "분석 결과를 생성할 수 없습니다."
        
    except Exception as e:
        logger.error(f"LLM API 호출 중 오류 발생: {str(e)}")
        return f"API 호출 중 오류가 발생했습니다: {str(e)}"


# 역량 이름 리스트 추출 함수
def extract_top_gap_items(response_text: str) -> List[str]:
    logger.info(f"응답 텍스트에서 스킬 추출 시작: {response_text[:200]}...")
    
    # 여러 패턴으로 시도
    patterns = [
        r'\d+\.\s\*\*(.+?)\*\*',  # 1. **스킬명**
        r'\d+\.\s(.+?)(?:\n|$)',  # 1. 스킬명
        r'\d+\.\s(.+?)(?:\s-|$)',  # 1. 스킬명 -
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, response_text)
        if matches:
            # 스킬명 정리: [ ], * 문자 제거
            cleaned_matches = []
            for match in matches:
                cleaned = match.strip()
                # [ ] 제거
                if cleaned.startswith('[') and cleaned.endswith(']'):
                    cleaned = cleaned[1:-1]
                # ** 제거
                cleaned = cleaned.replace('*', '').strip()
                if cleaned:
                    cleaned_matches.append(cleaned)
            
            logger.info(f"패턴 '{pattern}'으로 추출된 스킬: {matches}")
            logger.info(f"정리된 스킬: {cleaned_matches}")
            return cleaned_matches
    
    logger.warning("어떤 패턴으로도 스킬을 추출하지 못했습니다.")
    return []


# 갭 분석 함수 (시각화용 - 5개)
def perform_gap_analysis_visualization(user_id: int, category: str, db: Session) -> Dict[str, Any]:
    """사용자의 갭 분석을 수행합니다. (시각화용 - 상위 5개)"""
    try:
        logger.info(f"시각화용 갭 분석 시작 - 사용자 ID: {user_id}, 카테고리: {category}")
        
        skill_order = get_trend_skills_by_category(category, db)
        logger.info(f"트렌드 스킬 조회 결과: {len(skill_order)}개 스킬")
        skill_trend = skill_order[:20]  # 상위 20개만 사용

        user_data = get_user_summary(user_id, db)
        if not user_data:
            logger.error(f"사용자 {user_id}를 찾을 수 없습니다.")
            raise ValueError(f"User {user_id} not found")
        
        logger.info(f"사용자 데이터 조회 성공: {user_data.get('name', 'Unknown')}")

        prompt = make_gap_analysis_prompt_visualization(user_data, skill_trend, category)
        logger.info("시각화용 프롬프트 생성 완료")
        
        gap_result_text = call_llm_for_gap_analysis(prompt)
        logger.info("LLM 분석 완료")
        
        top_skills = extract_top_gap_items(gap_result_text)
        logger.info(f"추출된 Top 스킬 (시각화용): {len(top_skills)}개")

        return {
            "user_id": user_id,
            "category": category,
            "gap_result": gap_result_text,
            "top_skills": top_skills[:5]  # 상위 5개만 반환
        }
        
    except Exception as e:
        logger.error(f"시각화용 갭 분석 중 오류 발생: {str(e)}")
        raise

# 갭 분석 함수 (todo_list용 - 10개)
def perform_gap_analysis_todo(user_id: int, category: str, db: Session) -> Dict[str, Any]:
    """사용자의 갭 분석을 수행합니다. (todo_list용 - 상위 10개)"""
    try:
        logger.info(f"todo_list용 갭 분석 시작 - 사용자 ID: {user_id}, 카테고리: {category}")
        
        skill_order = get_trend_skills_by_category(category, db)
        logger.info(f"트렌드 스킬 조회 결과: {len(skill_order)}개 스킬")
        skill_trend = skill_order[:20]  # 상위 20개만 사용

        user_data = get_user_summary(user_id, db)
        if not user_data:
            logger.error(f"사용자 {user_id}를 찾을 수 없습니다.")
            raise ValueError(f"User {user_id} not found")
        
        logger.info(f"사용자 데이터 조회 성공: {user_data.get('name', 'Unknown')}")

        prompt = make_gap_analysis_prompt_todo(user_data, skill_trend, category)
        logger.info("todo_list용 프롬프트 생성 완료")
        
        gap_result_text = call_llm_for_gap_analysis(prompt)
        logger.info("LLM 분석 완료")
        
        top_skills = extract_top_gap_items(gap_result_text)
        logger.info(f"추출된 Top 스킬 (todo_list용): {len(top_skills)}개")

        return {
            "user_id": user_id,
            "category": category,
            "gap_result": gap_result_text,
            "top_skills": top_skills[:10]  # 상위 10개만 반환
        }
        
    except Exception as e:
        logger.error(f"todo_list용 갭 분석 중 오류 발생: {str(e)}")
        raise

# 기존 함수 (하위 호환성 유지)
def perform_gap_analysis(user_id: int, category: str, db: Session) -> Dict[str, Any]:
    """사용자의 갭 분석을 수행합니다. (기본 - 10개)"""
    return perform_gap_analysis_todo(user_id, category, db)

