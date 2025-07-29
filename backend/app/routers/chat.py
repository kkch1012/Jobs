import json
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime
from sqlalchemy.orm import Session
from app.utils.logger import app_logger
from app.database import get_db
from app.models.mongo import MCPMessage
from app.schemas.mcp import MessageIn
from app.services.mcp_client import mcp_client
from app.services.llm_client import llm_client
from app.utils.dependencies import get_current_user, get_optional_current_user
from app.models.user import User
from app.models.chat_session import ChatSession
from typing import Optional, Dict, Any, List
import re
from fastapi.responses import JSONResponse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["chat"])

# intent별 파라미터 추출 정보 (기본값만 정의)
API_INTENT_PARAMETERS = {
    "job_posts": {
        "parameters": {
            "limit": 10,
            "company_name": None,
            "job_name": None,
            "applicant_type": None,
            "employment_type": None,
            "tech_stack": None
        }
    },
    "certificates": {
        "parameters": {
            "limit": 10
        }
    },
    "skills": {
        "parameters": {
            "limit": 10
        }
    },
    "roadmaps": {
        "parameters": {
            "limit": 10
        }
    },
    "visualization": {
        "parameters": {
            "job_name": None,
            "field": "tech_stack"
        }
    },
    "job_recommendation": {
        "parameters": {
            "top_n": 20
        }
    },
    "get_my_skills": {
        "parameters": {}
    },
    "add_my_skills": {
        "parameters": {
            "skill_name": None,
            "proficiency": None
        }
    },
    "get_my_certificates": {
        "parameters": {}
    },
    "add_my_certificates": {
        "parameters": {
            "certificate_name": None,
            "acquired_date": None
        }
    },
    "update_my_skill_proficiency": {
        "skill_name": "숙련도를 변경할 스킬명",
        "proficiency": "새로운 숙련도 레벨"
    }
}

# intent 목록
INTENT_LIST = [
    "job_posts", "certificates", "skills", "roadmaps", "visualization",
    "get_my_resume", "update_resume", "page_move", "job_recommendation", 
    "get_my_skills", "add_my_skills", "get_my_certificates", "add_my_certificates", "update_my_skill_proficiency", "general"
]

def merge_parameters_with_defaults(extracted_params: Dict[str, Any], api_type: str) -> Dict[str, Any]:
    """추출된 파라미터와 기본값을 병합합니다."""
    default_params = API_INTENT_PARAMETERS[api_type]["parameters"].copy()
    
    # 추출된 파라미터로 기본값 덮어쓰기
    for key, value in extracted_params.items():
        if value is not None and key in default_params:
            default_params[key] = value
    
    return default_params

def extract_parameters_from_message(message: str, api_type: str) -> Dict[str, Any]:
    """사용자 메시지에서 API 파라미터를 추출합니다. (백업용 - LLM 추출 실패시 사용)"""
    message_lower = message.lower()
    parameters = {}
    
    if api_type == "job_posts":
        # 회사명 추출
        company_patterns = [
            r"([가-힣a-zA-Z]+(?:기업|회사|corporation|company|inc|ltd))",
            r"([가-힣a-zA-Z]+에서)",
            r"([가-힣a-zA-Z]+의)"
        ]
        for pattern in company_patterns:
            match = re.search(pattern, message)
            if match:
                parameters["company_name"] = match.group(1).replace("에서", "").replace("의", "")
                break
        
        # 지원자격 추출
        if any(word in message_lower for word in ["신입", "신규", "주니어", "junior"]):
            parameters["applicant_type"] = "신입"
        elif any(word in message_lower for word in ["경력", "시니어", "전문가", "senior"]):
            parameters["applicant_type"] = "경력"
        
        # 고용형태 추출
        if any(word in message_lower for word in ["정규직", "정규", "permanent"]):
            parameters["employment_type"] = "정규직"
        elif any(word in message_lower for word in ["계약직", "계약", "contract"]):
            parameters["employment_type"] = "계약직"
        elif any(word in message_lower for word in ["인턴", "인턴십", "intern"]):
            parameters["employment_type"] = "인턴"
            
    elif api_type == "job_recommendation":
        # 추천 개수 조정
        if any(word in message_lower for word in ["많이", "더", "더 많은"]):
            parameters["top_n"] = 50
        elif any(word in message_lower for word in ["적게", "몇 개", "3개", "5개"]):
            parameters["top_n"] = 10
            
    elif api_type == "visualization":
        # 분석 필드 추출
        if any(word in message_lower for word in ["기술", "스택", "tech"]):
            parameters["field"] = "tech_stack"
        elif any(word in message_lower for word in ["자격", "qualification"]):
            parameters["field"] = "qualifications"
    
    return parameters

def extract_requested_resume_field(message: str) -> Optional[str]:
    """사용자 메시지에서 요청한 이력서 필드를 추출합니다."""
    message_lower = message.lower()
    
    # 대학교/학교 관련
    if any(word in message_lower for word in ["대학교", "대학", "학교", "university", "college"]):
        return "university"
    
    # 전공 관련
    if any(word in message_lower for word in ["전공", "학과", "major", "학부"]):
        return "major"
    
    # 학점 관련
    if any(word in message_lower for word in ["학점", "gpa", "성적", "평점"]):
        return "gpa"
    
    # 어학점수 관련
    if any(word in message_lower for word in ["어학", "토익", "toeic", "토플", "toefl", "아이엘츠", "ielts"]):
        return "language_score"
    
    # 경력 관련
    if any(word in message_lower for word in ["경력", "연차", "working_year", "경험"]):
        return "working_year"
    
    # 희망직무 관련
    if any(word in message_lower for word in ["희망직무", "직무", "job_name", "원하는 일"]):
        return "job_name"
    
    # 기술스택 관련
    if any(word in message_lower for word in ["기술", "스택", "tech_stack", "스킬"]):
        return "tech_stack"
    
    # 자격증 관련
    if any(word in message_lower for word in ["자격증", "certificate", "증명서"]):
        return "certificates"
    
    # 전체 이력서 요청인 경우
    if any(word in message_lower for word in ["전체", "모든", "이력서", "resume", "전부"]):
        return "all"
    
    return None

async def save_message_to_mongo(session_id: int, role: str, content: str):
    """MongoDB에 메시지를 저장합니다."""
    try:
        msg = MCPMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.utcnow()
        )
        await msg.insert()
        app_logger.debug(f"MongoDB 메시지 저장 성공: session_id={session_id}, role={role}")
    except Exception as e:
        app_logger.error(f"MongoDB 메시지 저장 실패: {str(e)}")
        # MongoDB 저장 실패는 전체 요청을 중단시키지 않음
        raise

async def generate_llm_summary(intent: str, mcp_result: Dict[str, Any], model: str) -> str:
    """LLM을 사용하여 MCP 결과를 자연어로 요약합니다."""
    
    # 중복 체크 결과인 경우 특별 처리
    if intent == "update_resume" and mcp_result.get("status") == "duplicate":
        return mcp_result.get("msg", "이미 등록된 정보입니다.")
    
    summary_prompt = f"""
아래는 사용자의 요청 intent와 MCP 서버에서 받아온 원본 데이터입니다.
- intent: {intent}
- 원본 데이터: {json.dumps(mcp_result, ensure_ascii=False)}

사용자에게 친절하고 명확하게 요약/설명/추천을 자연어로 생성하세요.
"""
    messages: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": "당신은 취업/직무 관련 정보를 요약/설명/추천하는 AI 어시스턴트입니다. 한국어로 자연스럽게 답변하세요."},
        {"role": "user", "content": summary_prompt}
    ]
    llm_summary = await llm_client.chat_completion(messages, model=model)
    return (llm_summary or "요약 생성 실패").strip()

async def execute_single_intent(
    intent: str, 
    parameters: Dict[str, Any], 
    current_user: Optional[User], 
    request: Request,
    db: Session
) -> Dict[str, Any]:
    """단일 intent를 실행하고 결과를 반환합니다."""
    
    # 도구 호출이 필요한 intent 처리
    if intent in ["job_posts", "certificates", "skills", "roadmaps", "visualization"]:
        # LLM이 추출한 파라미터를 기본값과 병합
        parameters = merge_parameters_with_defaults(parameters, intent)
        return await mcp_client.call_tool(intent, parameters)
    
    # 인증이 필요한 intent 처리
    elif intent in ["get_my_resume", "update_resume", "job_recommendation", "get_my_skills", "add_my_skills", "get_my_certificates", "add_my_certificates", "update_my_skill_proficiency"]:
        if not current_user:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
        
        # 인증 토큰 추출
        auth_header = request.headers.get("authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
        
        # intent별 특수 처리
        if intent == "get_my_resume":
            requested_field = parameters.get("requested_field")
            return await mcp_client.get_my_resume(auth_header, requested_field)
        
        elif intent == "get_my_skills":
            skill_name = parameters.get("skill_name")
            skill_params = {}
            if skill_name:
                skill_params["skill_name"] = skill_name
            return await mcp_client.call_tool_with_auth(intent, skill_params, auth_header)
        
        elif intent == "add_my_skills":
            skill_name = parameters.get("skill_name")
            proficiency = parameters.get("proficiency")
            
            if not skill_name:
                raise ValueError("스킬명이 필요합니다.")
            
            skill_params = {
                "skill_name": skill_name,
                "proficiency": proficiency or ""
            }
            return await mcp_client.call_tool_with_auth(intent, skill_params, auth_header)
        
        elif intent == "get_my_certificates":
            return await mcp_client.call_tool_with_auth(intent, {}, auth_header)
        
        elif intent == "add_my_certificates":
            cert_name = parameters.get("certificate_name")
            acquired_date = parameters.get("acquired_date")
            
            if not cert_name:
                raise ValueError("자격증명이 필요합니다.")
            
            cert_params = {
                "certificate_name": cert_name,
                "acquired_date": acquired_date or ""
            }
            return await mcp_client.call_tool_with_auth(intent, cert_params, auth_header)
        
        elif intent == "update_my_skill_proficiency":
            skill_name = parameters.get("skill_name")
            proficiency = parameters.get("proficiency")
            
            if not skill_name:
                raise ValueError("숙련도를 변경할 스킬명이 필요합니다.")
            
            skill_params = {
                "skill_name": skill_name,
                "proficiency": proficiency or ""
            }
            return await mcp_client.call_tool_with_auth(intent, skill_params, auth_header)
        
        elif intent == "job_recommendation":
            parameters = merge_parameters_with_defaults(parameters, intent)
            return await mcp_client.call_tool_with_auth(intent, parameters, auth_header)
        
        else:
            return await mcp_client.call_tool_with_auth(intent, parameters, auth_header)
    
    else:
        # 일반 대화나 알 수 없는 intent
        raise ValueError(f"지원하지 않는 intent: {intent}")

def create_error_response(session_id: int, error_content: str, status_code: int = 500, action: Optional[str] = None) -> JSONResponse:
    """에러 응답을 생성합니다."""
    response_content = {"error": error_content}
    if action:
        response_content["action"] = action
    return JSONResponse(status_code=status_code, content=response_content)

@router.post("/", summary="LLM+MCP 기반 AI 챗봇 대화 (의도 분석+도구 호출+자연어 요약)",
             description="""
OpenRouter API를 사용해 LLM으로 intent를 분석하고,
MCP 서버의 도구를 호출한 결과를 LLM이 자연어로 요약/설명/추천합니다.
- intent에 따라 실제 DB/API 결과를 LLM 프롬프트에 포함하거나, 이력서 수정/추가/삭제/조회, 페이지 이동 등도 처리합니다.
- 프론트엔드에 action, page, updated_resume 등 필요한 정보를 명확히 반환합니다.
- 인증이 필요한 기능의 경우 자동으로 인증을 요구합니다.
""")
async def chat_with_llm(
    data: MessageIn,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
    model: str = "qwen/qwen-vl-max"
):
    try:
        # 0. 사용자 메시지 저장
        try:
            await save_message_to_mongo(data.session_id, "user", data.message)
        except Exception as e:
            app_logger.error(f"사용자 메시지 MongoDB 저장 실패: {str(e)}")
            # MongoDB 저장 실패해도 계속 진행

        # 1. LLM으로 intent 분석
        try:
            app_logger.debug(f"LLM intent 분석 시작: message='{data.message[:50]}...'")
            
            # 기존 숫자 선택 처리 로직 제거 (자동 순차 실행으로 변경됨)
            
            intent_json = await llm_client.analyze_intent(data.message, INTENT_LIST)
            
            # 다중 intent 처리
            if intent_json.get("multiple_intents"):
                app_logger.debug(f"다중 intent 감지: {len(intent_json.get('intents', []))}개")
                
                # 즉시 모든 인텐트를 순차 실행
                intents_list = intent_json.get("intents", [])
                if len(intents_list) > 1:
                    results = []
                    
                    app_logger.info(f"순차 실행 시작: {len(intents_list)}개 작업")
                    
                    for i, intent_item in enumerate(intents_list):
                        intent = intent_item.get("intent", "unknown")
                        parameters = intent_item.get("parameters", {})
                        description = intent_item.get("description", intent)
                        
                        app_logger.debug(f"실행 중: {i+1}번 - {intent} ({description})")
                        
                        try:
                            # 각 intent별 MCP 호출 로직
                            mcp_result = await execute_single_intent(
                                intent, parameters, current_user, request, db
                            )
                            
                            # LLM 요약 생성
                            summary = await generate_llm_summary(intent, mcp_result, model)
                            
                            results.append({
                                "step": i + 1,
                                "intent": intent,
                                "description": description,
                                "summary": summary,
                                "success": True
                            })
                            
                        except Exception as e:
                            app_logger.error(f"{i+1}번 작업 실행 실패: {str(e)}")
                            results.append({
                                "step": i + 1,
                                "intent": intent,
                                "description": description,
                                "summary": f"작업 실행 중 오류가 발생했습니다: {str(e)}",
                                "success": False
                            })
                    
                    # 전체 결과 종합
                    total_steps = len(results)
                    success_steps = sum(1 for r in results if r["success"])
                    
                    final_answer = f"📋 1번부터 순차적으로 {total_steps}개 작업을 실행했습니다!\n"
                    final_answer += f"✅ 성공: {success_steps}개 / ❌ 실패: {total_steps - success_steps}개\n\n"
                    
                    for result in results:
                        status = "✅" if result["success"] else "❌"
                        final_answer += f"{status} {result['step']}. {result['description']}\n"
                        final_answer += f"   → {result['summary']}\n\n"
                    
                    # 최종 응답 저장
                    try:
                        await save_message_to_mongo(data.session_id, "assistant", final_answer)
                    except Exception as e:
                        app_logger.error(f"순차 실행 결과 저장 실패: {str(e)}")
                    
                    return {
                        "answer": final_answer,
                        "intent": "sequential_execution",
                        "parameters": {},
                        "executed_steps": results,
                        "total_steps": total_steps,
                        "success_steps": success_steps
                    }
            
            # 단일 intent 처리 (기존 로직)
            intent = intent_json.get("intent", "general")
            parameters = intent_json.get("parameters", {})
            
            # 스킬 관련 키워드 강제 override
            if intent == "update_resume" and any(keyword in data.message.lower() for keyword in ["파이썬", "python", "자바스크립트", "javascript", "react", "vue", "java", "c++", "스킬", "기술"]):
                # 스킬명 추출
                skill_keywords = ["파이썬", "python", "자바스크립트", "javascript", "react", "vue", "java", "c++", "c#", "node", "spring", "django", "flask"]
                skill_name = None
                
                for keyword in skill_keywords:
                    if keyword.lower() in data.message.lower():
                        skill_name = keyword
                        break
                
                if skill_name:
                    intent = "add_my_skills"
                    parameters = {"skill_name": skill_name, "proficiency": ""}
                    app_logger.info(f"스킬 키워드 감지로 intent 변경: update_resume → add_my_skills, skill: {skill_name}")
            
            app_logger.debug(f"LLM intent 분석 성공: intent={intent}, parameters={parameters}")
        except Exception as e:
            app_logger.error(f"LLM intent 분석 실패: {str(e)}")
            intent = "general"
            parameters = {}

        # 2. 도구 호출이 필요한 intent 처리
        mcp_result = None
        if intent in ["job_posts", "certificates", "skills", "roadmaps", "visualization"]:
            # LLM이 추출한 파라미터를 기본값과 병합
            parameters = merge_parameters_with_defaults(parameters, intent)
            
            try:
                mcp_result = await mcp_client.call_tool(intent, parameters)
            except Exception as e:
                app_logger.error(f"MCP 도구 호출 실패: {str(e)}")
                error_content = f"MCP 도구 호출 실패: {str(e)}"
                try:
                    await save_message_to_mongo(data.session_id, "assistant", error_content)
                except:
                    pass
                return create_error_response(data.session_id, error_content)

        # 3. 인증이 필요한 intent 처리
        elif intent in ["get_my_resume", "update_resume", "job_recommendation", "get_my_skills", "add_my_skills", "get_my_certificates", "add_my_certificates", "update_my_skill_proficiency"]:
            if not current_user:
                error_content = "로그인이 필요합니다."
                try:
                    await save_message_to_mongo(data.session_id, "assistant", error_content)
                except:
                    pass
                return create_error_response(data.session_id, error_content, 401, "login")
            
            # 인증 토큰 추출
            auth_header = request.headers.get("authorization")
            if not auth_header:
                error_content = "인증 토큰이 필요합니다."
                try:
                    await save_message_to_mongo(data.session_id, "assistant", error_content)
                except:
                    pass
                return create_error_response(data.session_id, error_content, 401)
            
            try:
                # get_my_resume의 경우 특정 필드 요청 처리
                if intent == "get_my_resume":
                    # 사용자 메시지에서 요청한 필드 추출
                    requested_field = extract_requested_resume_field(data.message)
                    if requested_field:
                        parameters["requested_field"] = requested_field
                        app_logger.debug(f"이력서 특정 필드 요청: {requested_field}")
                
                # job_recommendation의 경우 파라미터 병합
                if intent == "job_recommendation":
                    parameters = merge_parameters_with_defaults(parameters, intent)
                
                # auth_header는 위에서 None 체크를 했으므로 str 타입임이 보장됨
                if intent == "get_my_resume":
                    requested_field = parameters.get("requested_field")
                    mcp_result = await mcp_client.get_my_resume(auth_header, requested_field)
                elif intent == "get_my_skills":
                    skill_name = parameters.get("skill_name")
                    skill_params = {}
                    if skill_name:
                        skill_params["skill_name"] = skill_name
                    mcp_result = await mcp_client.call_tool_with_auth(intent, skill_params, auth_header)
                elif intent == "add_my_skills":
                    # 스킬명과 숙련도 파라미터 추출
                    skill_name = parameters.get("skill_name")
                    proficiency = parameters.get("proficiency")
                    
                    if not skill_name:
                        # LLM이 스킬명을 추출하지 못한 경우 메시지에서 다시 추출 시도
                        import re
                        
                        # 개선된 스킬명 추출 패턴
                        skill_patterns = [
                            r'(?:이력서에|에)\s*([가-힣a-zA-Z\+\#\.]+)\s*(?:추가|스킬)',
                            r'([가-힣a-zA-Z\+\#\.]+)\s*(?:스킬|기술)\s*추가',
                            r'([가-힣a-zA-Z\+\#\.]+)\s*추가',
                            r'([가-힣a-zA-Z\+\#\.]+)(?:\s+(?:스킬|기술|을|를))?'
                        ]
                        
                        for pattern in skill_patterns:
                            matches = re.findall(pattern, data.message)
                            if matches:
                                possible_skills = [s.strip() for s in matches if len(s.strip()) > 1 and s.lower() not in ['스킬', '추가', '해줘', '스택', '기술', '이력서', '내', '에']]
                                if possible_skills:
                                    skill_name = possible_skills[0]
                                    app_logger.debug(f"패턴 '{pattern}'으로 스킬명 추출: {skill_name}")
                                    break
                    
                    if not skill_name:
                        app_logger.warning(f"스킬명을 추출할 수 없습니다. 메시지: {data.message}")
                        # 간단한 fallback - 메시지에서 첫번째 단어 추출
                        words = data.message.split()
                        for word in words:
                            if word not in ['내', '이력서에', '추가해줘', '스킬', '기술'] and len(word) > 1:
                                skill_name = word
                                app_logger.debug(f"fallback으로 스킬명 추출: {skill_name}")
                                break
                    
                    # 숙련도가 없으면 메시지에서 추출 시도
                    if not proficiency:
                        proficiency_patterns = [
                            r'(?:숙련도를|레벨을)\s*(초급|중급|고급|상급|하급|입문|전문가)',
                            r'(초급|중급|고급|상급|하급|입문|전문가)(?:으로|로)\s*(?:변경|바꿔)',
                            r'(초급|중급|고급|상급|하급|입문|전문가)'
                        ]
                        for pattern in proficiency_patterns:
                            matches = re.findall(pattern, data.message)
                            if matches:
                                proficiency = matches[0]
                                app_logger.debug(f"패턴 '{pattern}'으로 숙련도 추출: {proficiency}")
                                break
                    
                    app_logger.debug(f"최종 추출된 스킬명: {skill_name}, 숙련도: {proficiency}")
                    
                    skill_params = {
                        "skill_name": skill_name,
                        "proficiency": proficiency or ""
                    }
                    mcp_result = await mcp_client.call_tool_with_auth(intent, skill_params, auth_header)
                elif intent == "get_my_certificates":
                    mcp_result = await mcp_client.call_tool_with_auth(intent, {}, auth_header)
                elif intent == "add_my_certificates":
                    # 자격증명과 취득일 파라미터 추출
                    cert_name = parameters.get("certificate_name")
                    acquired_date = parameters.get("acquired_date")
                    
                    if not cert_name:
                        # LLM이 자격증명을 추출하지 못한 경우 메시지에서 다시 추출 시도
                        import re
                        cert_matches = re.findall(r'([가-힣a-zA-Z\+\#\.]+(?:\s*[가-힣a-zA-Z\+\#\.]*)*)', data.message)
                        possible_certs = [c for c in cert_matches if len(c) > 1 and c.lower() not in ['자격증', '추가', '해줘', '취득', '등록']]
                        if possible_certs:
                            cert_name = possible_certs[0]
                    
                    cert_params = {
                        "certificate_name": cert_name,
                        "acquired_date": acquired_date or ""
                    }
                    mcp_result = await mcp_client.call_tool_with_auth(intent, cert_params, auth_header)
                elif intent == "update_my_skill_proficiency":
                    # 스킬명과 숙련도 파라미터 추출
                    skill_name = parameters.get("skill_name")
                    proficiency = parameters.get("proficiency")
                    
                    if not skill_name:
                        # LLM이 스킬명을 추출하지 못한 경우 메시지에서 다시 추출 시도
                        import re
                        skill_patterns = [
                            r'(?:이력서에|에)\s*([가-힣a-zA-Z\+\#\.]+)\s*(?:숙련도|스킬|기술)\s*변경',
                            r'([가-힣a-zA-Z\+\#\.]+)\s*(?:스킬|기술)\s*숙련도\s*변경',
                            r'([가-힣a-zA-Z\+\#\.]+)\s*(?:숙련도|스킬|기술)\s*변경'
                        ]
                        for pattern in skill_patterns:
                            matches = re.findall(pattern, data.message)
                            if matches:
                                possible_skills = [s.strip() for s in matches if len(s.strip()) > 1 and s.lower() not in ['숙련도', '변경', '해줘', '스킬', '기술', '이력서', '내', '에']]
                                if possible_skills:
                                    skill_name = possible_skills[0]
                                    app_logger.debug(f"패턴 '{pattern}'으로 스킬명 추출: {skill_name}")
                                    break
                    
                    if not skill_name:
                        app_logger.warning(f"스킬명을 추출할 수 없습니다. 메시지: {data.message}")
                        # 간단한 fallback - 메시지에서 첫번째 단어 추출
                        words = data.message.split()
                        for word in words:
                            if word not in ['내', '이력서에', '숙련도', '변경', '스킬', '기술'] and len(word) > 1:
                                skill_name = word
                                app_logger.debug(f"fallback으로 스킬명 추출: {skill_name}")
                                break
                    
                    # 숙련도가 없으면 메시지에서 추출 시도
                    if not proficiency:
                        proficiency_patterns = [
                            r'(?:숙련도를|레벨을)\s*(초급|중급|고급|상급|하급|입문|전문가)',
                            r'(초급|중급|고급|상급|하급|입문|전문가)(?:으로|로)\s*(?:변경|바꿔)',
                            r'(초급|중급|고급|상급|하급|입문|전문가)'
                        ]
                        for pattern in proficiency_patterns:
                            matches = re.findall(pattern, data.message)
                            if matches:
                                proficiency = matches[0]
                                app_logger.debug(f"패턴 '{pattern}'으로 숙련도 추출: {proficiency}")
                                break
                    
                    app_logger.debug(f"최종 추출된 스킬명: {skill_name}, 숙련도: {proficiency}")
                    
                    skill_params = {
                        "skill_name": skill_name,
                        "proficiency": proficiency or ""
                    }
                    mcp_result = await mcp_client.call_tool_with_auth(intent, skill_params, auth_header)
                else:
                    mcp_result = await mcp_client.call_tool_with_auth(intent, parameters, auth_header)
            except Exception as e:
                app_logger.error(f"인증 도구 호출 실패: {str(e)}")
                error_content = f"인증 도구 호출 실패: {str(e)}"
                try:
                    await save_message_to_mongo(data.session_id, "assistant", error_content)
                except:
                    pass
                return create_error_response(data.session_id, error_content)

        # 4. 응답 생성
        try:
            app_logger.debug(f"응답 생성 시작: intent={intent}, has_mcp_result={mcp_result is not None}")
            if mcp_result is not None:
                # MCP 결과가 있는 경우 LLM 요약
                answer = await generate_llm_summary(intent, mcp_result, model)
            else:
                # 일반 대화
                answer = await llm_client.generate_response(data.message)
                answer = (answer or "응답 생성 실패").strip()
            app_logger.debug(f"응답 생성 성공: answer_length={len(answer)}")
        except Exception as e:
            app_logger.error(f"응답 생성 실패: {str(e)}")
            answer = "죄송합니다. 응답을 생성할 수 없습니다."

        # 5. 어시스턴트 메시지 저장
        try:
            await save_message_to_mongo(data.session_id, "assistant", answer)
        except Exception as e:
            app_logger.error(f"어시스턴트 메시지 저장 실패: {str(e)}")

        # 6. 응답 반환
        response = {
            "answer": answer,
            "intent": intent,
            "parameters": parameters
        }
        
        if mcp_result is not None:
            response["mcp_result"] = mcp_result
            
        return response

    except Exception as e:
        app_logger.error(f"채팅 처리 중 예상치 못한 오류: {str(e)}")
        error_content = f"채팅 처리 중 오류가 발생했습니다: {str(e)}"
        try:
            await save_message_to_mongo(data.session_id, "assistant", error_content)
        except:
            pass
        return create_error_response(data.session_id, error_content)

@router.get("/history", summary="세션별 채팅 이력 조회", description="특정 세션 ID의 모든 채팅 메시지(유저/AI)를 시간순으로 반환합니다.")
async def get_chat_history(session_id: str):
    try:
        # session_id를 정수로 변환
        try:
            session_id_int = int(session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="session_id는 정수여야 합니다.")
        
        messages = await MCPMessage.find({"session_id": session_id_int}).sort("created_at").to_list()
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"채팅 이력 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"채팅 이력 조회 실패: {str(e)}")
