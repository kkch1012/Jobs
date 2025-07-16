import json
from fastapi import APIRouter, HTTPException, Depends, Body, Request
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.mongo import MCPMessage
from app.schemas.mcp import MessageIn
from app.services.mcp_client import mcp_client
from app.services.llm_client import llm_client
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.chat_session import ChatSession
from typing import Optional, Dict, Any, List
import re
from app.models.job_post import JobPost
from fastapi.responses import JSONResponse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

router = APIRouter(prefix="/mcp_chat", tags=["mcp_chat"])

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
    }
}

# intent 목록
INTENT_LIST = [
    "job_posts", "certificates", "skills", "roadmaps", "visualization",
    "get_my_resume", "update_resume", "page_move", "job_recommendation", "general"
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

async def save_message_to_mongo(session_id: int, role: str, content: str):
    """MongoDB에 메시지를 저장합니다."""
    msg = MCPMessage(
        session_id=session_id,
        role=role,
        content=content,
        created_at=datetime.utcnow()
    )
    await msg.insert()

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

def create_error_response(session_id: int, error_content: str, status_code: int = 500, action: Optional[str] = None) -> JSONResponse:
    """에러 응답을 생성합니다."""
    response_content = {"error": error_content}
    if action:
        response_content["action"] = action
    return JSONResponse(status_code=status_code, content=response_content)

@router.post("/llm/chat/", summary="LLM+MCP 기반 AI 챗봇 대화 (의도 분석+도구 호출+자연어 요약)",
             description="""
OpenRouter API를 사용해 LLM으로 intent를 분석하고,
MCP 서버의 도구를 호출한 결과를 LLM이 자연어로 요약/설명/추천합니다.
- intent에 따라 실제 DB/API 결과를 LLM 프롬프트에 포함하거나, 이력서 수정/추가/삭제/조회, 페이지 이동 등도 처리합니다.
- 프론트엔드에 action, page, updated_resume 등 필요한 정보를 명확히 반환합니다.
""")
async def chat_with_llm(
    data: MessageIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    model: str = Body("qwen/qwen-vl-max", example="qwen/qwen-vl-max")
):
    try:
        # 0. 사용자 메시지 저장
        await save_message_to_mongo(data.session_id, "user", data.message)

        # 1. LLM으로 intent 분석
        intent_json = await llm_client.analyze_intent(data.message, INTENT_LIST)
        intent = intent_json.get("intent", "general")
        parameters = intent_json.get("parameters", {})

        # 2. 도구 호출이 필요한 intent 처리
        mcp_result = None
        if intent in ["job_posts", "certificates", "skills", "roadmaps", "visualization", "job_recommendation"]:
            # LLM이 추출한 파라미터를 기본값과 병합
            parameters = merge_parameters_with_defaults(parameters, intent)
            
            try:
                mcp_result = await mcp_client.call_tool(intent, parameters)
            except Exception as e:
                error_content = f"MCP 도구 호출 실패: {str(e)}"
                await save_message_to_mongo(data.session_id, "assistant", error_content)
                return create_error_response(data.session_id, error_content)

        # 3. 이력서 관련 intent 처리
        elif intent in ["get_my_resume", "update_resume"]:
            if not current_user:
                error_content = "로그인이 필요합니다."
                await save_message_to_mongo(data.session_id, "assistant", error_content)
                return create_error_response(data.session_id, error_content, 401, "login")
            
            # 인증 토큰 추출
            auth_header = request.headers.get("authorization")
            if not auth_header:
                error_content = "인증 토큰이 필요합니다."
                await save_message_to_mongo(data.session_id, "assistant", error_content)
                return create_error_response(data.session_id, error_content, 401)
            
            try:
                # auth_header는 위에서 None 체크를 했으므로 str 타입임이 보장됨
                mcp_result = await mcp_client.call_tool_with_auth(intent, parameters, auth_header)
            except Exception as e:
                error_content = f"이력서 도구 호출 실패: {str(e)}"
                await save_message_to_mongo(data.session_id, "assistant", error_content)
                return create_error_response(data.session_id, error_content)

        # 4. 응답 생성
        if mcp_result is not None:
            # MCP 결과가 있는 경우 LLM 요약
            answer = await generate_llm_summary(intent, mcp_result, model)
        else:
            # 일반 대화
            answer = await llm_client.generate_response(data.message)
            answer = (answer or "응답 생성 실패").strip()

        # 5. 어시스턴트 메시지 저장
        await save_message_to_mongo(data.session_id, "assistant", answer)

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
        error_content = f"채팅 처리 중 오류가 발생했습니다: {str(e)}"
        await save_message_to_mongo(data.session_id, "assistant", error_content)
        return create_error_response(data.session_id, error_content)

@router.get("/history", summary="세션별 채팅 이력 조회", description="특정 세션 ID의 모든 채팅 메시지(유저/AI)를 시간순으로 반환합니다.")
async def get_chat_history(session_id: int):
    try:
        messages = await MCPMessage.find({"session_id": session_id}).sort("created_at").to_list()
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 이력 조회 실패: {str(e)}")
