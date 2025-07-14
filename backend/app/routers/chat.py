import json
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.mongo import MCPMessage
from app.schemas.mcp import MessageIn, MCPContext
from app.services.mcp_client import mcp_client
from app.services.llm_client import llm_client
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.chat_session import ChatSession
from typing import Optional, Dict, List, Any
import uuid
import re
from app.models.job_post import JobPost

router = APIRouter(prefix="/mcp_chat", tags=["mcp_chat"])

# intent별 파라미터 추출 정보만 남김
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
    }
}

# 일반 대화 키워드 (API 호출 없이 처리)
GENERAL_KEYWORDS = [
    "안녕", "하세요", "반갑", "고마워", "감사", "hello", "hi", "thanks", "thank",
    "도움", "help", "뭐", "무엇", "어떻게", "what", "how", "when", "where",
    "소개", "설명", "알려", "가르쳐", "도와", "assist", "explain", "introduce"
]

# intent 확장: job_posts, resume_update, resume_add, resume_delete, page_move, general 등
EXTENDED_INTENT_MAPPING = {
    "job_posts": "채용공고 조회",
    "resume_update": "이력서 정보 수정",
    "resume_add": "이력서 정보 추가",
    "resume_delete": "이력서 정보 삭제",
    "page_move": "페이지 이동",
    "general": "일반 대화"
}

def extract_parameters_from_message(message: str, api_type: str) -> Dict[str, Any]:
    """사용자 메시지에서 API 파라미터를 추출합니다."""
    message_lower = message.lower()
    parameters = API_INTENT_PARAMETERS[api_type]["parameters"].copy()
    
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
        
        # 직무명 추출
        job_patterns = [
            r"([가-힣a-zA-Z]+(?:개발자|엔지니어|디자이너|마케터|기획자))",
            r"([가-힣a-zA-Z]+(?:developer|engineer|designer|marketer))"
        ]
        for pattern in job_patterns:
            match = re.search(pattern, message)
            if match:
                parameters["job_name"] = match.group(1)
                break
        
        # 기술스택 추출
        tech_keywords = ["Python", "Java", "JavaScript", "React", "Vue", "Node.js", "Django", "Spring"]
        for tech in tech_keywords:
            if tech.lower() in message_lower:
                parameters["tech_stack"] = tech
                break
        
        # 지원자격 추출
        if any(word in message_lower for word in ["신입", "신규", "주니어"]):
            parameters["applicant_type"] = "신입"
        elif any(word in message_lower for word in ["경력", "시니어", "전문가"]):
            parameters["applicant_type"] = "경력"
        
        # 고용형태 추출
        if any(word in message_lower for word in ["정규직", "정규"]):
            parameters["employment_type"] = "정규직"
        elif any(word in message_lower for word in ["계약직", "계약"]):
            parameters["employment_type"] = "계약직"
        elif any(word in message_lower for word in ["인턴", "인턴십"]):
            parameters["employment_type"] = "인턴"
    
    elif api_type == "visualization":
        # 직무명 추출
        job_patterns = [
            r"([가-힣a-zA-Z]+(?:개발자|엔지니어|디자이너|마케터|기획자))",
            r"([가-힣a-zA-Z]+(?:developer|engineer|designer|marketer))"
        ]
        for pattern in job_patterns:
            match = re.search(pattern, message)
            if match:
                parameters["job_name"] = match.group(1)
                break
        
        # 분석 필드 추출
        if any(word in message_lower for word in ["기술", "스택", "tech"]):
            parameters["field"] = "tech_stack"
        elif any(word in message_lower for word in ["자격", "qualification"]):
            parameters["field"] = "qualifications"
    
    return parameters

def calculate_intent_score(message: str, api_type: str) -> float:
    """메시지와 API 타입 간의 의도 매칭 점수를 계산합니다."""
    message_lower = message.lower()
    score = 0.0
    
    # 기본 키워드 매칭
    keywords = API_INTENT_PARAMETERS[api_type]["parameters"]["keywords"]
    for keyword in keywords:
        if keyword.lower() in message_lower:
            score += 1.0
    
    # 동의어 매칭 (가중치 높음)
    synonyms = API_INTENT_PARAMETERS[api_type]["parameters"]["synonyms"]
    for main_word, synonym_list in synonyms.items():
        if main_word.lower() in message_lower:
            score += 2.0
        for synonym in synonym_list:
            if synonym.lower() in message_lower:
                score += 1.5
    
    # 구체적인 질문 키워드 (가중치 높음)
    question_keywords = ["어떤", "무엇", "뭐", "보여", "알려", "찾아", "조회", "검색"]
    for q_keyword in question_keywords:
        if q_keyword in message_lower:
            score += 0.5
    
    return score

async def analyze_intent_with_llm(user_message: str, context: Optional[MCPContext] = None) -> Optional[dict]:
    """LLM을 사용하여 사용자 메시지의 의도를 분석합니다."""
    try:
        # 사용 가능한 API 목록
        available_apis = list(API_INTENT_PARAMETERS.keys()) + [k for k in EXTENDED_INTENT_MAPPING.keys() if k not in API_INTENT_PARAMETERS]
        
        # LLM을 사용한 의도 분석
        intent_result = await llm_client.analyze_intent(user_message, available_apis)
        
        if intent_result and intent_result.get("intent") != "general":
            # API 호출이 필요한 경우
            api_type = intent_result["intent"]
            parameters = extract_parameters_from_message(user_message, api_type)
            
            return {
                "intent": api_type,
                "confidence": intent_result.get("confidence", 0.0),
                "parameters": parameters,
                "reasoning": intent_result.get("reasoning", ""),
                "use_llm": True
            }
        else:
            # 일반 대화인 경우
            return {
                "intent": "general",
                "confidence": intent_result.get("confidence", 0.0) if intent_result else 0.0,
                "parameters": {},
                "reasoning": intent_result.get("reasoning", "") if intent_result else "LLM 분석 실패",
                "use_llm": True
            }
            
    except Exception as e:
        print(f"LLM 의도 분석 중 오류: {str(e)}")
        return None

async def analyze_intent_with_mcp(user_message: str, context: Optional[MCPContext] = None) -> Optional[dict]:
    """외부 MCP 서버를 사용하여 사용자 메시지의 의도를 분석합니다."""
    try:
        # MCP 서버에 도구 목록 요청
        tools_response = await mcp_client.chat_with_mcp(
            method="tools/list",
            params={},
            request_id=str(uuid.uuid4())
        )
        
        if tools_response.get("error"):
            print(f"MCP 도구 목록 조회 실패: {tools_response['error']}")
            return None
        
        available_tools = tools_response.get("result", {}).get("tools", [])
        
        print(f"DEBUG: 분석 중인 메시지: {user_message}")
        
        # 1. 일반 대화인지 확인
        if any(keyword in user_message.lower() for keyword in GENERAL_KEYWORDS):
            print(f"DEBUG: 일반 대화로 인식됨")
            return {
                "router": "general",
                "parameters": {"message": user_message}
            }
        
        # 2. 각 API 타입별 점수 계산
        intent_scores = {}
        for api_type in API_INTENT_PARAMETERS.keys():
            score = calculate_intent_score(user_message, api_type)
            intent_scores[api_type] = score
            print(f"DEBUG: {api_type} 점수: {score}")
        
        # 3. 가장 높은 점수의 API 선택 (임계값 이상)
        max_score = max(intent_scores.values())
        if max_score >= 1.0:  # 최소 1점 이상이어야 의도로 인식
            best_api = max(intent_scores.items(), key=lambda x: x[1])[0]
            print(f"DEBUG: {best_api} 분야로 인식됨 (점수: {max_score})")
            
            # 파라미터 추출
            parameters = extract_parameters_from_message(user_message, best_api)
            print(f"DEBUG: 추출된 파라미터: {parameters}")
            
            return {
                "router": best_api,
                "parameters": parameters
            }
        else:
            print(f"DEBUG: 매칭되는 의도 없음 - 일반 대화로 분류")
            return {
                "router": "general",
                "parameters": {"message": user_message}
            }
            
    except Exception as e:
        print(f"MCP 의도 분석 실패: {e}")
        return None

async def call_api_via_mcp(intent: dict) -> Optional[dict]:
    """외부 MCP 서버를 통해 API를 호출합니다."""
    try:
        tool_name = intent.get("router", "").replace("/", "")
        parameters = intent.get("parameters", {})
        
        # MCP 서버를 통해 도구 호출
        result = await mcp_client.call_tool(tool_name, parameters)
        return result
        
    except Exception as e:
        print(f"MCP API 호출 실패: {e}")
        return None

def convert_datetime(obj):
    if isinstance(obj, dict):
        return {k: convert_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime(i) for i in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

@router.post("/llm/chat/",
             summary="LLM+MCP 기반 AI 챗봇 대화 (의도 분석+도구 호출+자연어 요약)",
             description="""
OpenRouter API를 사용해 LLM으로 intent를 분석하고,
MCP 서버의 도구를 호출한 결과를 LLM이 자연어로 요약/설명/추천합니다.
- intent에 따라 실제 DB/API 결과를 LLM 프롬프트에 포함하거나, 이력서 수정/추가/삭제/조회, 페이지 이동 등도 처리합니다.
- 프론트엔드에 action, page, updated_resume 등 필요한 정보를 명확히 반환합니다.
""")
async def chat_with_llm(
    data: MessageIn,
    model: str = Body("openai/gpt-4-1106-preview"),
    current_user: Optional[User] = Depends(lambda: None),
    db: Session = Depends(get_db)
):
    # 1. LLM으로 intent 분석
    available_apis = list(API_INTENT_PARAMETERS.keys()) + [k for k in EXTENDED_INTENT_MAPPING.keys() if k not in API_INTENT_PARAMETERS]
    intent = await llm_client.analyze_intent(data.message, available_apis)
    intent_name = intent.get("intent")
    params = intent.get("parameters", {})

    # 2. 도구 호출이 필요한 intent면 MCP 서버 도구 호출 → 결과를 LLM에 요약 요청
    mcp_tools = ["job_posts", "certificates", "skills", "roadmaps", "visualization"]
    if intent_name in mcp_tools:
        # MCP 서버 도구 호출
        mcp_result = await mcp_client.call_tool(intent_name, params)
        # LLM에게 요약 프롬프트 전달
        summary_prompt = (
            f"아래는 실제 {intent_name} 데이터입니다. 사용자의 질문: '{data.message}'\n"
            f"{intent_name} 데이터: {json.dumps(mcp_result, ensure_ascii=False)}\n"
            "이 데이터를 바탕으로 사용자에게 친절하게 요약/설명/추천해줘."
        )
        answer = await llm_client.generate_response(summary_prompt)
        return {"message": answer, "intent": intent, "llm_model": model, "mcp_result": mcp_result}

    # 3. 이력서 등 기타 intent는 기존대로 처리
    elif intent_name == "resume_update":
        if not current_user:
            return {"message": "이력서 관련 기능을 이용하려면 로그인이 필요합니다. 먼저 로그인해 주세요.", "intent": intent, "llm_model": model}
        resume = db.query(User).filter(User.id == current_user.id).first()
        update_prompt = (
            f"아래는 사용자의 기존 이력서 정보입니다.\n{resume}\n"
            f"사용자 요청: '{data.message}'\n"
            "이 요청에 따라 이력서 정보를 수정한 결과만 JSON으로 반환해줘."
        )
        updated_resume = await llm_client.generate_response(update_prompt)
        return {"message": "이력서가 성공적으로 수정되었습니다.", "updated_resume": updated_resume, "intent": intent, "llm_model": model}

    elif intent_name == "resume_add":
        if not current_user:
            return {"message": "이력서 관련 기능을 이용하려면 로그인이 필요합니다. 먼저 로그인해 주세요.", "intent": intent, "llm_model": model}
        resume = db.query(User).filter(User.id == current_user.id).first()
        add_prompt = (
            f"아래는 사용자의 기존 이력서 정보입니다.\n{resume}\n"
            f"사용자 요청: '{data.message}'\n"
            "이 요청에 따라 이력서에 추가할 정보를 JSON으로 반환해줘."
        )
        added_resume = await llm_client.generate_response(add_prompt)
        return {"message": "이력서 정보가 성공적으로 추가되었습니다.", "added_resume": added_resume, "intent": intent, "llm_model": model}

    elif intent_name == "resume_delete":
        if not current_user:
            return {"message": "이력서 관련 기능을 이용하려면 로그인이 필요합니다. 먼저 로그인해 주세요.", "intent": intent, "llm_model": model}
        resume = db.query(User).filter(User.id == current_user.id).first()
        delete_prompt = (
            f"아래는 사용자의 기존 이력서 정보입니다.\n{resume}\n"
            f"사용자 요청: '{data.message}'\n"
            "이 요청에 따라 이력서에서 삭제할 정보를 JSON으로 반환해줘."
        )
        deleted_resume = await llm_client.generate_response(delete_prompt)
        return {"message": "이력서 정보가 성공적으로 삭제되었습니다.", "deleted_resume": deleted_resume, "intent": intent, "llm_model": model}

    elif intent_name == "page_move":
        page = params.get("page", "/")
        return {"action": "navigate", "page": page, "intent": intent, "llm_model": model}

    else:
        # 일반 대화
        answer = await llm_client.generate_response(data.message)
        return {"message": answer, "intent": intent, "llm_model": model}

# 프론트엔드에 안내할 사항 정리
FRONTEND_GUIDE = """
1. message: LLM이 생성한 자연어 답변(요약/설명/추천 등)
2. intent: LLM이 분석한 의도 및 파라미터 정보
3. llm_model: 사용된 LLM 모델명
4. action: "navigate"가 오면 page 필드에 명시된 경로로 이동
5. updated_resume, added_resume, deleted_resume: 이력서 정보가 수정/추가/삭제된 경우, 해당 JSON 결과를 활용해 이력서 화면을 갱신
6. 기타 intent에 따라 필요한 추가 정보가 포함될 수 있음
"""

@router.post("/llm/chat/test",
             summary="테스트용 LLM 채팅 (인증 불필요)",
             description="인증이 필요 없는 테스트용 LLM 채팅 엔드포인트입니다.")
async def test_llm_chat(data: MessageIn):
    """테스트용 LLM 채팅 (인증 불필요)"""
    # LLM을 사용한 의도 분석 (우선순위)
    intent = await analyze_intent_with_llm(data.message)
    
    # LLM 분석이 실패한 경우 키워드 기반 분석으로 폴백
    if not intent or intent.get("confidence", 0.0) < 0.3:
        intent = await analyze_intent_with_mcp(data.message)
    
    if not intent:
        answer = "죄송합니다. 요청을 이해하지 못했습니다. 다른 방식으로 질문해 주세요."
    else:
        # LLM 기반 일반 대화 처리
        if intent.get("intent") == "general" or intent.get("use_llm"):
            # LLM을 사용하여 자연스러운 응답 생성
            answer = await llm_client.generate_response(data.message)
        else:
            # API 호출이 필요한 경우
            api_type = intent.get("intent")
            api_result = await call_api_via_mcp(intent)
            
            if api_result:
                # API 결과를 자연스러운 응답으로 변환
                try:
                    if api_type == "job_posts":
                        # API 결과가 리스트인지 딕셔너리인지 확인
                        if isinstance(api_result, list):
                            jobs = api_result
                        else:
                            jobs = api_result.get("jobs", [])
                        
                        if jobs:
                            answer = f"채용공고를 {len(jobs)}개 찾았습니다! "
                            first_job = jobs[0]
                            company = first_job.get('company_name', '알 수 없음')
                            title = first_job.get('title', '알 수 없음')
                            answer += f"예를 들어, {company}에서 {title} 포지션을 모집하고 있습니다. "
                            answer += "더 자세한 정보가 필요하시면 특정 회사나 직무를 말씀해 주세요."
                        else:
                            answer = "현재 등록된 채용공고가 없습니다. 나중에 다시 확인해 주세요."
                    elif api_type == "certificates":
                        certificates = api_result.get("certificates", [])
                        if certificates:
                            answer = f"총 {len(certificates)}개의 자격증 정보를 찾았습니다! "
                            first_cert = certificates[0]
                            cert_name = first_cert.get('name', '알 수 없음')
                            issuer = first_cert.get('issuer', '알 수 없음')
                            answer += f"예를 들어, {cert_name} 자격증은 {issuer}에서 발급합니다. "
                            answer += "특정 분야의 자격증을 찾고 계시면 말씀해 주세요."
                        else:
                            answer = "현재 등록된 자격증 정보가 없습니다."
                    elif api_type == "skills":
                        skills = api_result.get("skills", [])
                        if skills:
                            answer = f"총 {len(skills)}개의 기술 스택 정보를 찾았습니다! "
                            first_skill = skills[0]
                            skill_name = first_skill.get('name', '알 수 없음')
                            category = first_skill.get('category', '알 수 없음')
                            answer += f"예를 들어, {skill_name}은 {category} 분야의 기술입니다. "
                            answer += "특정 기술이나 분야에 대해 더 알고 싶으시면 말씀해 주세요."
                        else:
                            answer = "현재 등록된 기술 스택 정보가 없습니다."
                    elif api_type == "roadmaps":
                        roadmaps = api_result.get("roadmaps", [])
                        if roadmaps:
                            answer = f"총 {len(roadmaps)}개의 취업 로드맵을 찾았습니다! "
                            first_roadmap = roadmaps[0]
                            roadmap_name = first_roadmap.get('name', '알 수 없음')
                            field = first_roadmap.get('field', '알 수 없음')
                            answer += f"예를 들어, {roadmap_name}은 {field} 분야의 로드맵입니다. "
                            answer += "특정 분야나 직무에 대한 로드맵이 필요하시면 말씀해 주세요."
                        else:
                            answer = "현재 등록된 로드맵 정보가 없습니다."
                    elif api_type == "visualization":
                        # 시각화 데이터 처리
                        if isinstance(api_result, list) and api_result:
                            answer = f"총 {len(api_result)}개의 시각화 데이터를 찾았습니다! "
                            first_data = api_result[0]
                            skill = first_data.get('skill', '알 수 없음')
                            count = first_data.get('count', 0)
                            answer += f"예를 들어, '{skill}' 기술이 {count}번 등장했습니다. "
                            answer += "더 자세한 분석이 필요하시면 특정 기술이나 기간을 말씀해 주세요."
                        else:
                            answer = "현재 시각화 데이터가 없습니다."
                    else:
                        answer = "요청하신 정보를 찾았습니다. 더 구체적인 질문을 해주시면 더 자세한 답변을 드릴 수 있습니다."
                except Exception as e:
                    answer = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
            else:
                answer = "죄송합니다. 요청하신 정보를 찾을 수 없습니다. 다른 키워드로 검색해 보시거나, 더 구체적으로 말씀해 주세요."

    return {
        "message": answer,
        "intent": intent,
        "llm_model": "openai/gpt-4-1106-preview", # 테스트용 모델명
        "timestamp": datetime.utcnow()
    }

@router.get("/llm/history/",
            summary="대화 히스토리 조회",
            description="""
특정 세션의 대화 히스토리를 조회합니다.

- MongoDB에 저장된 대화 메시지를 시간순으로 반환합니다.
- 최대 50개 메시지까지 조회 가능합니다.
- 사용자와 AI의 모든 대화 내용을 포함합니다.

**파라미터:**
- `session_id`: 조회할 세션 ID (필수)
- `limit`: 조회할 메시지 개수 (기본값: 50, 최대: 50)
""")
async def get_llm_history(session_id: int, limit: int = 50):
    """대화 히스토리를 반환합니다."""
    if limit > 50:
        limit = 50
    
    messages = await MCPMessage.find(
        MCPMessage.session_id == session_id
    ).sort("+created_at").limit(limit).to_list()
    
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at,
                "intent": msg.intent
            }
            for msg in messages
        ],
        "total_count": len(messages)
    }

@router.get("/llm/tools",
            summary="LLM 기반 AI 챗봇의 도구 목록 조회",
            description="LLM 기반 AI 챗봇에서 사용 가능한 도구 목록을 조회합니다.")
async def get_llm_tools():
    """LLM 기반 AI 챗봇의 도구 목록을 반환합니다."""
    return {
        "tools": [
            "job_posts",
            "resume_update",
            "resume_add",
            "resume_delete",
            "page_move"
        ],
        "llm_model": "openai/gpt-4-1106-preview"
    }

@router.post("/llm/tools/{tool_name}/call",
             summary="LLM 기반 AI 챗봇을 통한 도구 호출",
             description="LLM 기반 AI 챗봇을 통해 특정 도구를 호출합니다.")
async def call_llm_tool(tool_name: str, arguments: dict):
    """LLM 기반 AI 챗봇을 통해 특정 도구를 호출합니다."""
    try:
        # LLM 기반 AI 챗봇은 실제 도구 호출을 직접 처리하지 않고, 프롬프트에 포함시키거나 파싱하여 처리
        # 여기서는 단순히 도구 호출 요청을 받아 프롬프트에 포함시키는 역할만 수행
        # 실제 도구 호출은 LLM 프롬프트에서 처리하도록 가정
        if tool_name == "job_posts":
            return {"message": f"LLM 기반 AI 챗봇에서 채용공고 조회 도구를 호출했습니다. 파라미터: {json.dumps(arguments, ensure_ascii=False)}"}
        elif tool_name == "resume_update":
            return {"message": f"LLM 기반 AI 챗봇에서 이력서 수정 도구를 호출했습니다. 파라미터: {json.dumps(arguments, ensure_ascii=False)}"}
        elif tool_name == "resume_add":
            return {"message": f"LLM 기반 AI 챗봇에서 이력서 추가 도구를 호출했습니다. 파라미터: {json.dumps(arguments, ensure_ascii=False)}"}
        elif tool_name == "resume_delete":
            return {"message": f"LLM 기반 AI 챗봇에서 이력서 삭제 도구를 호출했습니다. 파라미터: {json.dumps(arguments, ensure_ascii=False)}"}
        elif tool_name == "page_move":
            return {"message": f"LLM 기반 AI 챗봇에서 페이지 이동 도구를 호출했습니다. 파라미터: {json.dumps(arguments, ensure_ascii=False)}"}
        else:
            return {"message": f"알 수 없는 도구 이름: {tool_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"도구 호출 실패: {str(e)}")
