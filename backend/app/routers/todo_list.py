from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.certificate import Certificate
from app.models.user_certificate import UserCertificate
from app.services.llm_client import llm_client
from app.services.mcp_client import mcp_client
from app.utils.dependencies import get_current_user
from app.utils.exceptions import NotFoundException, BadRequestException, InternalServerException
from app.utils.logger import app_logger
from typing import List, Dict, Any, Optional
from openai.types.chat import ChatCompletionMessageParam
import json

router = APIRouter(prefix="/todo", tags=["todo"])

async def analyze_user_resume(user: User, db: Session) -> Optional[Dict[str, Any]]:
    """사용자 이력서 분석"""
    try:
        # MCP를 통해 사용자 이력서 정보 가져오기
        resume_data = await mcp_client.call_tool("get_my_resume", {})
        
        # 사용자 정보 요약
        user_summary = f"""
        사용자: {user.name}
        희망 직무: {user.desired_job}
        기술 스택: {[f"{s.skill.name}({s.proficiency})" for s in user.user_skills]}
        자격증: {[c.certificate.name for c in user.user_certificates]}
        경험: {[f"{exp.name} - {exp.period}" for exp in user.experiences]}
        학력: {user.university} {user.major} {user.degree}
        어학 점수: {user.language_score}
        """
        
        return {
            "resume_data": resume_data,
            "user_summary": user_summary,
            "skills": [{"name": s.skill.name, "proficiency": s.proficiency} for s in user.user_skills],
            "certificates": [c.certificate.name for c in user.user_certificates],
            "experiences": [{"name": exp.name, "period": exp.period, "description": exp.description} for exp in user.experiences]
        }
    except Exception as e:
        app_logger.error(f"이력서 분석 실패: {str(e)}")
        return None

async def analyze_job_market_gaps(user: User, desired_job: str) -> Optional[Dict[str, Any]]:
    """직무 시장과 사용자 간의 갭 분석"""
    try:
        # MCP를 통해 해당 직무의 채용공고 분석
        job_posts = await mcp_client.call_tool("job_posts", {
            "job_name": desired_job,
            "limit": 20
        })
        
        # 기술 스택 분석을 위한 시각화 데이터 가져오기
        tech_analysis = await mcp_client.call_tool("visualization", {
            "job_name": desired_job,
            "field": "tech_stack"
        })
        
        return {
            "job_posts": job_posts,
            "tech_analysis": tech_analysis,
            "desired_job": desired_job
        }
    except Exception as e:
        app_logger.error(f"직무 갭 분석 실패: {str(e)}")
        return None

async def analyze_certificate_gaps(user: User, db: Session, desired_job: str) -> Dict[str, Any]:
    """자격증 갭 분석 및 추천 자격증 조회"""
    try:
        # 사용자가 보유한 자격증 목록
        user_certificates = db.query(UserCertificate).filter(UserCertificate.user_id == user.id).all()
        user_cert_names = [uc.certificate.name for uc in user_certificates]
        
        # 전체 자격증 목록 조회
        all_certificates = db.query(Certificate).all()
        
        # 직무별 관련 자격증 필터링 (LLM이 판단)
        relevant_certs = []
        for cert in all_certificates:
            if cert.name not in user_cert_names:
                relevant_certs.append({
                    "name": cert.name,
                    "issuer": cert.issuer
                })
        
        # MCP를 통해 자격증 정보 가져오기
        certificate_data = await mcp_client.call_tool("certificates", {
            "limit": 50
        })
        
        return {
            "user_certificates": user_cert_names,
            "relevant_certificates": relevant_certs[:10],  # 상위 10개만
            "certificate_market_data": certificate_data,
            "desired_job": desired_job
        }
    except Exception as e:
        app_logger.error(f"자격증 갭 분석 실패: {str(e)}")
        return {
            "user_certificates": [],
            "relevant_certificates": [],
            "certificate_market_data": {},
            "desired_job": desired_job
        }

async def search_recommended_courses(gap_analysis: Dict[str, Any], certificate_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """갭 분석을 바탕으로 추천 강의 검색"""
    try:
        # LLM을 통해 갭 분석 결과를 바탕으로 추천 강의 검색
        missing_skills = gap_analysis.get("tech_analysis", {}).get("top_skills", [])
        relevant_certs = certificate_analysis.get("relevant_certificates", [])
        
        # LLM 프롬프트 구성
        prompt = f"""
        다음 정보를 바탕으로 추천 강의를 검색해주세요:
        
        [부족한 기술 스택]
        {', '.join(missing_skills[:5])}
        
        [추천 자격증]
        {', '.join([cert['name'] for cert in relevant_certs[:5]])}
        
        [요구사항]
        1. 부족한 기술 스택을 보완할 수 있는 강의 검색
        2. 추천 자격증 준비를 위한 강의 검색
        3. 각 강의별 난이도, 예상 소요시간, 학습 목표 제시
        4. 실무 중심의 실습 강의 우선 추천
        
        [출력 형식]
        다음 JSON 형태로 응답해주세요:
        {{
            "recommended_courses": [
                {{
                    "title": "강의 제목",
                    "platform": "강의 플랫폼",
                    "skill_focus": "주요 학습 기술",
                    "difficulty": "beginner|intermediate|advanced",
                    "duration": "예상 소요시간",
                    "description": "강의 설명",
                    "learning_objectives": ["목표1", "목표2"],
                    "certificate_related": "관련 자격증명 또는 null"
                }}
            ]
        }}
        """
        
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system", 
                "content": """당신은 IT 강의 추천 전문가입니다. 
                사용자의 기술 갭과 자격증 목표를 분석하여 
                실용적이고 효과적인 강의를 추천해주세요."""
            },
            {"role": "user", "content": prompt}
        ]
        
        response = await llm_client.chat_completion(messages)
        
        if not response:
            return []
        
        # JSON 파싱
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                course_data = json.loads(json_str)
                return course_data.get("recommended_courses", [])
            else:
                return []
        except json.JSONDecodeError:
            app_logger.warning(f"강의 검색 결과 JSON 파싱 실패: {response}")
            return []
            
    except Exception as e:
        app_logger.error(f"강의 검색 실패: {str(e)}")
        return []

async def analyze_language_requirements(user: User, gap_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """언어 요구사항 분석 및 부족 시 일정 조정 계획"""
    try:
        user_language_score = getattr(user, 'language_score', None)
        
        # LLM을 통해 언어 요구사항 분석
        prompt = f"""
        다음 정보를 바탕으로 언어 학습 필요성을 분석해주세요:
        
        [사용자 현재 어학 점수]
        {user_language_score or "정보 없음"}
        
        [목표 직무]
        {gap_analysis.get('desired_job', '개발자')}
        
        [시장 분석 결과]
        {gap_analysis.get('tech_analysis', {})}
        
        [분석 요구사항]
        1. 현재 어학 점수가 목표 직무에 충분한지 판단
        2. 부족한 경우 어떤 언어 시험을 준비해야 하는지 제안
        3. 목표 점수와 현재 점수의 갭 분석
        4. 언어 학습을 위한 일정 조정 필요성 판단
        
        [출력 형식]
        다음 JSON 형태로 응답해주세요:
        {{
            "language_analysis": {{
                "current_score": "현재 점수",
                "target_score": "목표 점수",
                "score_gap": "점수 갭",
                "recommended_test": "추천 시험",
                "needs_improvement": true/false,
                "study_weeks_needed": 0,
                "priority": "high|medium|low"
            }}
        }}
        """
        
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system", 
                "content": """당신은 어학 학습 전문가입니다. 
                사용자의 현재 어학 점수와 목표 직무를 분석하여 
                언어 학습 필요성과 일정을 제안해주세요."""
            },
            {"role": "user", "content": prompt}
        ]
        
        response = await llm_client.chat_completion(messages)
        
        if not response:
            return {"language_analysis": {"needs_improvement": False}}
        
        # JSON 파싱
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                language_data = json.loads(json_str)
                return language_data
            else:
                return {"language_analysis": {"needs_improvement": False}}
        except json.JSONDecodeError:
            app_logger.warning(f"언어 분석 결과 JSON 파싱 실패: {response}")
            return {"language_analysis": {"needs_improvement": False}}
            
    except Exception as e:
        app_logger.error(f"언어 요구사항 분석 실패: {str(e)}")
        return {"language_analysis": {"needs_improvement": False}}

async def generate_comprehensive_todo_list(
    user: User, 
    course: str, 
    days: int, 
    user_prompt: str,
    resume_analysis: Dict[str, Any],
    gap_analysis: Dict[str, Any],
    certificate_analysis: Dict[str, Any],
    recommended_courses: List[Dict[str, Any]],
    language_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """종합적인 분석을 바탕으로 todo-list 생성"""
    
    # 분석 결과 요약
    gap_summary = ""
    if gap_analysis and gap_analysis.get("tech_analysis"):
        tech_data = gap_analysis["tech_analysis"]
        gap_summary = f"""
        [시장 분석 결과]
        - 요구 기술: {', '.join(tech_data.get('top_skills', []))}
        - 평균 연봉: {tech_data.get('avg_salary', '정보 없음')}
        - 채용 공고 수: {len(gap_analysis.get('job_posts', {}).get('jobs', []))}
        """
    
    certificate_summary = ""
    if certificate_analysis.get("relevant_certificates"):
        certs = certificate_analysis["relevant_certificates"][:5]
        certificate_summary = f"""
        [추천 자격증]
        {', '.join([cert['name'] for cert in certs])}
        """
    
    course_summary = ""
    if recommended_courses:
        course_summary = "\n[추천 강의]\n"
        for i, course_info in enumerate(recommended_courses[:3], 1):
            course_summary += f"""
            {i}. {course_info.get('title', 'N/A')}
               - 플랫폼: {course_info.get('platform', 'N/A')}
               - 난이도: {course_info.get('difficulty', 'N/A')}
               - 소요시간: {course_info.get('duration', 'N/A')}
            """
    
    language_summary = ""
    if language_analysis.get("language_analysis", {}).get("needs_improvement"):
        lang_data = language_analysis["language_analysis"]
        language_summary = f"""
        [언어 학습 필요]
        - 현재 점수: {lang_data.get('current_score', 'N/A')}
        - 목표 점수: {lang_data.get('target_score', 'N/A')}
        - 추천 시험: {lang_data.get('recommended_test', 'N/A')}
        - 필요 학습 주: {lang_data.get('study_weeks_needed', 0)}주
        """
    
    # LLM 프롬프트 구성
    prompt = f"""
    다음은 사용자의 종합적인 분석 결과와 요청사항입니다.
    
    [사용자 정보]
    {resume_analysis['user_summary']}
    
    [사용자 요청]
    코스: {course}
    학습 기간: {days}일
    추가 요청: {user_prompt}
    
    {gap_summary}
    
    {certificate_summary}
    
    {course_summary}
    
    {language_summary}
    
    [요구사항]
    1. 사용자의 현재 기술 수준과 목표 직무 간의 갭을 고려한 학습 계획 수립
    2. 추천 강의를 활용한 실용적인 학습 경로 제시
    3. 자격증 준비를 위한 학습 일정 포함
    4. 언어 학습이 필요한 경우 일정에 반영
    5. 일별로 구체적인 학습 목표, 태스크, 예상 소요시간 설정
    6. 주말에는 복습과 실습 프로젝트 포함
    7. 사용자의 추가 요청사항 반영
    
    [출력 형식]
    다음 JSON 형태로 응답해주세요:
    {{
        "course": "{course}",
        "duration_days": {days},
        "gap_analysis": {{
            "missing_skills": ["기술1", "기술2"],
            "priority_skills": ["우선기술1", "우선기술2"]
        }},
        "certificate_plan": {{
            "target_certificates": ["자격증1", "자격증2"],
            "study_weeks": 0
        }},
        "language_plan": {{
            "needs_study": true/false,
            "target_test": "시험명",
            "study_weeks": 0
        }},
        "recommended_courses": ["강의1", "강의2"],
        "todos": [
            {{
                "day": 1,
                "date": "2025-01-01",
                "goals": ["목표1", "목표2"],
                "tasks": [
                    {{
                        "title": "태스크 제목",
                        "description": "상세 설명",
                        "duration": "2시간",
                        "type": "theory|practice|project|review|certificate|language"
                    }}
                ],
                "notes": "특별한 주의사항이나 팁"
            }}
        ]
    }}
    """
    
    messages: List[ChatCompletionMessageParam] = [
        {
            "role": "system", 
            "content": """당신은 취업 준비생을 위한 학습 계획 수립 전문가입니다. 
            사용자의 현재 상황, 목표 직무, 시장 분석 결과, 추천 강의, 자격증 목표, 언어 요구사항을 종합적으로 고려하여 
            실현 가능하고 효과적인 학습 계획을 수립해주세요. 
            각 태스크는 구체적이고 측정 가능해야 하며, 
            사용자의 수준에 맞는 난이도로 설정해주세요."""
        },
        {"role": "user", "content": prompt}
    ]
    
    response = await llm_client.chat_completion(messages)
    
    if not response:
        raise BadRequestException("LLM 응답을 받지 못했습니다.")
    
    # JSON 파싱
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_str = response[json_start:json_end]
            todo_data = json.loads(json_str)
        else:
            # 기본 구조 생성
            todo_data = create_fallback_todo_list(course, days, gap_analysis, certificate_analysis, language_analysis)
    except json.JSONDecodeError:
        app_logger.warning(f"LLM 응답 JSON 파싱 실패: {response}")
        todo_data = create_fallback_todo_list(course, days, gap_analysis, certificate_analysis, language_analysis)
    
    return todo_data

def create_fallback_todo_list(
    course: str, 
    days: int, 
    gap_analysis: Dict[str, Any], 
    certificate_analysis: Dict[str, Any],
    language_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """LLM 응답 실패 시 기본 todo-list 생성"""
    
    missing_skills = []
    if gap_analysis and gap_analysis.get("tech_analysis"):
        missing_skills = gap_analysis["tech_analysis"].get("top_skills", [])[:5]
    
    target_certificates = []
    if certificate_analysis.get("relevant_certificates"):
        target_certificates = [cert["name"] for cert in certificate_analysis["relevant_certificates"][:3]]
    
    needs_language_study = language_analysis.get("language_analysis", {}).get("needs_improvement", False)
    
    todos = []
    for i in range(days):
        day_tasks = []
        
        # 기술 학습 태스크
        if i < len(missing_skills):
            skill = missing_skills[i]
            day_tasks.append({
                "title": f"{skill} 학습",
                "description": f"{skill}에 대한 기본 개념과 실습",
                "duration": "3시간",
                "type": "theory"
            })
        
        # 메인 코스 학습
        day_tasks.append({
            "title": f"{course} Day {i + 1} 학습",
            "description": f"{course} 커리큘럼 Day {i + 1} 진행",
            "duration": "2시간",
            "type": "practice"
        })
        
        # 자격증 학습 (주 2회)
        if i % 3 == 0 and target_certificates:
            cert = target_certificates[i % len(target_certificates)]
            day_tasks.append({
                "title": f"{cert} 자격증 준비",
                "description": f"{cert} 자격증 관련 학습 및 문제 풀이",
                "duration": "1.5시간",
                "type": "certificate"
            })
        
        # 언어 학습 (필요한 경우)
        if needs_language_study and i % 2 == 0:
            day_tasks.append({
                "title": "어학 학습",
                "description": "목표 시험 준비를 위한 어학 학습",
                "duration": "1시간",
                "type": "language"
            })
        
        # 주말 복습 및 프로젝트
        if i % 7 == 6:
            day_tasks.append({
                "title": "주간 복습 및 프로젝트",
                "description": "이번 주 학습 내용 복습 및 실습 프로젝트",
                "duration": "4시간",
                "type": "review"
            })
        
        todos.append({
            "day": i + 1,
            "date": f"2025-01-{i+1:02d}",
            "goals": [f"Day {i + 1} 학습 목표 달성"],
            "tasks": day_tasks,
            "notes": "꾸준한 학습과 실습이 중요합니다."
        })
    
    return {
        "course": course,
        "duration_days": days,
        "gap_analysis": {
            "missing_skills": missing_skills,
            "priority_skills": missing_skills[:3]
        },
        "certificate_plan": {
            "target_certificates": target_certificates,
            "study_weeks": len(target_certificates) * 2
        },
        "language_plan": {
            "needs_study": needs_language_study,
            "target_test": "TOEIC" if needs_language_study else None,
            "study_weeks": 8 if needs_language_study else 0
        },
        "recommended_courses": [],
        "todos": todos
    }

@router.post("/generate", summary="맞춤형 todo-list 생성 (종합 분석)")
async def generate_todo_list(
    course: str,
    days: int,
    user_prompt: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 이력서 분석, 직무 갭 분석, 자격증 분석, 강의 추천, 언어 요구사항 분석을 통합하여 맞춤형 todo-list를 생성합니다.
    
    Args:
        course: 학습할 코스명
        days: 학습 기간 (일)
        user_prompt: 사용자의 추가 요청사항
        current_user: 현재 로그인한 사용자
        db: 데이터베이스 세션
    
    Returns:
        생성된 todo-list
    """
    try:
        app_logger.info(f"사용자 {current_user.id}의 종합 todo-list 생성 시작: {course}")
        
        # 1. 사용자 이력서 분석
        resume_analysis = await analyze_user_resume(current_user, db)
        if not resume_analysis:
            raise BadRequestException("사용자 이력서 분석에 실패했습니다.")
        
        # 2. 직무 시장 갭 분석
        desired_job = getattr(current_user, 'desired_job', None)
        if desired_job is None:
            desired_job = "개발자"
        else:
            desired_job = str(desired_job)
            
        gap_analysis = await analyze_job_market_gaps(current_user, desired_job)
        if not gap_analysis:
            app_logger.warning("직무 갭 분석에 실패했습니다. 기본 분석으로 진행합니다.")
        
        # 3. 자격증 갭 분석
        certificate_analysis = await analyze_certificate_gaps(current_user, db, desired_job)
        
        # 4. 추천 강의 검색
        recommended_courses = await search_recommended_courses(gap_analysis or {}, certificate_analysis)
        
        # 5. 언어 요구사항 분석
        language_analysis = await analyze_language_requirements(current_user, gap_analysis or {})
        
        # 6. 종합적인 todo-list 생성
        todo_data = await generate_comprehensive_todo_list(
            current_user, 
            course, 
            days, 
            user_prompt,
            resume_analysis,
            gap_analysis or {},
            certificate_analysis,
            recommended_courses,
            language_analysis
        )
        
        # 7. 사용자 모델에 todo_list 저장
        setattr(current_user, 'todo_list', todo_data)
        db.commit()
        
        app_logger.info(f"사용자 {current_user.id}의 종합 todo-list 생성 완료: {course}")
        
        return {
            "success": True,
            "message": f"{course} 코스의 {days}일 종합 학습 계획이 생성되었습니다.",
            "data": todo_data,
            "analysis_summary": {
                "resume_analyzed": True,
                "gap_analyzed": gap_analysis is not None,
                "certificates_analyzed": len(certificate_analysis.get("relevant_certificates", [])),
                "courses_recommended": len(recommended_courses),
                "language_needs_improvement": language_analysis.get("language_analysis", {}).get("needs_improvement", False),
                "missing_skills": todo_data.get("gap_analysis", {}).get("missing_skills", [])
            }
        }
        
    except Exception as e:
        app_logger.error(f"종합 todo-list 생성 실패: {str(e)}")
        raise InternalServerException(f"todo-list 생성 중 오류가 발생했습니다: {str(e)}")

@router.get("/user", summary="유저의 todo-list 조회")
def get_user_todo_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    현재 로그인한 사용자의 todo-list를 조회합니다.
    
    Args:
        current_user: 현재 로그인한 사용자
        db: 데이터베이스 세션
    
    Returns:
        사용자의 todo-list
    """
    try:
        todo_list = getattr(current_user, 'todo_list', None)
        if not todo_list or todo_list == []:
            return {
                "success": True,
                "message": "등록된 todo-list가 없습니다.",
                "data": None
            }
        
        app_logger.info(f"사용자 {current_user.id}의 todo-list 조회")
        
        return {
            "success": True,
            "message": "todo-list 조회 성공",
            "data": todo_list
        }
        
    except Exception as e:
        app_logger.error(f"todo-list 조회 실패: {str(e)}")
        raise InternalServerException(f"todo-list 조회 중 오류가 발생했습니다: {str(e)}")

@router.put("/update", summary="todo-list 업데이트")
def update_user_todo_list(
    todo_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 todo-list를 업데이트합니다.
    
    Args:
        todo_data: 업데이트할 todo-list 데이터
        current_user: 현재 로그인한 사용자
        db: 데이터베이스 세션
    
    Returns:
        업데이트 결과
    """
    try:
        setattr(current_user, 'todo_list', todo_data)
        db.commit()
        
        app_logger.info(f"사용자 {current_user.id}의 todo-list 업데이트 완료")
        
        return {
            "success": True,
            "message": "todo-list가 성공적으로 업데이트되었습니다.",
            "data": todo_data
        }
        
    except Exception as e:
        app_logger.error(f"todo-list 업데이트 실패: {str(e)}")
        raise InternalServerException(f"todo-list 업데이트 중 오류가 발생했습니다: {str(e)}")

@router.delete("/clear", summary="todo-list 삭제")
def clear_user_todo_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 todo-list를 삭제합니다.
    
    Args:
        current_user: 현재 로그인한 사용자
        db: 데이터베이스 세션
    
    Returns:
        삭제 결과
    """
    try:
        setattr(current_user, 'todo_list', [])
        db.commit()
        
        app_logger.info(f"사용자 {current_user.id}의 todo-list 삭제 완료")
        
        return {
            "success": True,
            "message": "todo-list가 성공적으로 삭제되었습니다."
        }
        
    except Exception as e:
        app_logger.error(f"todo-list 삭제 실패: {str(e)}")
        raise InternalServerException(f"todo-list 삭제 중 오류가 발생했습니다: {str(e)}")