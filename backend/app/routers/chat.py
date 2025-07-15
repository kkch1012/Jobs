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

# intent 목록만 단순 리스트로 유지
INTENT_LIST = [
    "job_posts", "certificates", "skills", "roadmaps", "visualization",
    "get_my_resume", "update_resume", "page_move", "general"
]

def extract_parameters_from_message(message: str, api_type: str) -> Dict[str, Any]:
    """사용자 메시지에서 API 파라미터를 추출합니다."""
    message_lower = message.lower()
    parameters = API_INTENT_PARAMETERS[api_type]["parameters"].copy()
    # (기존 파라미터 추출 로직은 필요시 유지)
    if api_type == "job_posts":
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
        job_patterns = [
            r"([가-힣a-zA-Z]+(?:개발자|엔지니어|디자이너|마케터|기획자))",
            r"([가-힣a-zA-Z]+(?:developer|engineer|designer|marketer))"
        ]
        for pattern in job_patterns:
            match = re.search(pattern, message)
            if match:
                parameters["job_name"] = match.group(1)
                break
        tech_keywords = ["Python", "Java", "JavaScript", "React", "Vue", "Node.js", "Django", "Spring"]
        for tech in tech_keywords:
            if tech.lower() in message_lower:
                parameters["tech_stack"] = tech
                break
        if any(word in message_lower for word in ["신입", "신규", "주니어"]):
            parameters["applicant_type"] = "신입"
        elif any(word in message_lower for word in ["경력", "시니어", "전문가"]):
            parameters["applicant_type"] = "경력"
        if any(word in message_lower for word in ["정규직", "정규"]):
            parameters["employment_type"] = "정규직"
        elif any(word in message_lower for word in ["계약직", "계약"]):
            parameters["employment_type"] = "계약직"
        elif any(word in message_lower for word in ["인턴", "인턴십"]):
            parameters["employment_type"] = "인턴"
    elif api_type == "visualization":
        job_patterns = [
            r"([가-힣a-zA-Z]+(?:개발자|엔지니어|디자이너|마케터|기획자))",
            r"([가-힣a-zA-Z]+(?:developer|engineer|designer|marketer))"
        ]
        for pattern in job_patterns:
            match = re.search(pattern, message)
            if match:
                parameters["job_name"] = match.group(1)
                break
        if any(word in message_lower for word in ["기술", "스택", "tech"]):
            parameters["field"] = "tech_stack"
        elif any(word in message_lower for word in ["자격", "qualification"]):
            parameters["field"] = "qualifications"
    return parameters

# 이하 LLM 기반 의도 분석/응답 생성 코드만 유지 (기존 키워드 기반 함수/변수/주석/legacy 코드 완전 삭제)

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
    # 0. Save user message to MongoDB
    user_msg = MCPMessage(
        session_id=data.session_id,
        role="user",
        content=data.message,
        created_at=datetime.utcnow()
    )
    await user_msg.insert()

    # 1. LLM으로 intent 분석
    available_intents = INTENT_LIST
    intent_json = await llm_client.analyze_intent(data.message, available_intents)
    intent = intent_json.get("intent", "general")
    parameters = intent_json.get("parameters", {})

    # 2. 도구 호출이 필요한 intent면 MCP 서버 도구 호출
    mcp_result = None
    if intent in ["job_posts", "certificates", "skills", "roadmaps", "visualization"]:
        # 파라미터 보완: 메시지에서 추가 추출
        extracted = extract_parameters_from_message(data.message, intent)
        parameters = {**extracted, **parameters}
        try:
            mcp_result = await mcp_client.call_tool(intent, parameters)
        except Exception as e:
            # Save error response as assistant message
            error_content = f"MCP 도구 호출 실패: {str(e)}"
            assistant_msg = MCPMessage(
                session_id=data.session_id,
                role="assistant",
                content=error_content,
                created_at=datetime.utcnow()
            )
            await assistant_msg.insert()
            return JSONResponse(status_code=500, content={"error": error_content})

    # 3. LLM에 MCP 결과를 프롬프트로 넣어 자연어 응답 생성
    if mcp_result is not None:
        summary_prompt = f"""
아래는 사용자의 요청 intent와 MCP 서버에서 받아온 원본 데이터입니다.
- intent: {intent}
- 원본 데이터: {json.dumps(mcp_result, ensure_ascii=False)}

사용자에게 친절하고 명확하게 요약/설명/추천을 자연어로 생성하세요.
"""
        summary_messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "당신은 취업/직무 관련 정보를 요약/설명/추천하는 AI 어시스턴트입니다. 한국어로 자연스럽게 답변하세요."},
            {"role": "user", "content": summary_prompt}
        ]
        llm_summary = await llm_client.chat_completion(summary_messages, model=model)
        answer = (llm_summary or "요약 생성 실패").strip()
        # Save assistant message
        assistant_msg = MCPMessage(
            session_id=data.session_id,
            role="assistant",
            content=answer,
            created_at=datetime.utcnow()
        )
        await assistant_msg.insert()
        return {"answer": answer, "mcp_result": mcp_result, "intent": intent, "parameters": parameters}

    # 4. 이력서 관련 intent 처리
    if intent in ["get_my_resume", "update_resume"]:
        if not current_user:
            error_content = "로그인이 필요합니다."
            assistant_msg = MCPMessage(
                session_id=data.session_id,
                role="assistant",
                content=error_content,
                created_at=datetime.utcnow()
            )
            await assistant_msg.insert()
            return JSONResponse(status_code=401, content={"error": error_content, "action": "login"})
        
        # MCP 서버 호출 시 인증 토큰 전달
        try:
            # Request에서 Authorization 헤더 추출
            auth_header = request.headers.get("authorization")
            if not auth_header:
                error_content = "인증 토큰이 필요합니다."
                assistant_msg = MCPMessage(
                    session_id=data.session_id,
                    role="assistant",
                    content=error_content,
                    created_at=datetime.utcnow()
                )
                await assistant_msg.insert()
                return JSONResponse(status_code=401, content={"error": error_content})
            
            mcp_result = await mcp_client.call_tool_with_auth(intent, parameters, auth_header)
        except Exception as e:
            error_content = f"이력서 도구 호출 실패: {str(e)}"
            assistant_msg = MCPMessage(
                session_id=data.session_id,
                role="assistant",
                content=error_content,
                created_at=datetime.utcnow()
            )
            await assistant_msg.insert()
            return JSONResponse(status_code=500, content={"error": error_content})

        # LLM 요약/설명
        summary_prompt = f"""
아래는 사용자의 요청 intent와 MCP 서버에서 받아온 원본 데이터입니다.
- intent: {intent}
- 원본 데이터: {json.dumps(mcp_result, ensure_ascii=False)}

사용자에게 친절하고 명확하게 요약/설명/추천을 자연어로 생성하세요.
"""
        resume_messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "당신은 취업/직무 관련 정보를 요약/설명/추천하는 AI 어시스턴트입니다. 한국어로 자연스럽게 답변하세요."},
            {"role": "user", "content": summary_prompt}
        ]
        llm_summary = await llm_client.chat_completion(resume_messages, model=model)
        answer = (llm_summary or "요약 생성 실패").strip()
        assistant_msg = MCPMessage(
            session_id=data.session_id,
            role="assistant",
            content=answer,
            created_at=datetime.utcnow()
        )
        await assistant_msg.insert()
        return {"answer": answer, "mcp_result": mcp_result, "intent": intent, "parameters": parameters}

    # 5. 일반 대화
    general_answer = await llm_client.generate_response(data.message)
    answer = (general_answer or "응답 생성 실패").strip()
    assistant_msg = MCPMessage(
        session_id=data.session_id,
        role="assistant",
        content=answer,
        created_at=datetime.utcnow()
    )
    await assistant_msg.insert()
    return {"answer": answer, "intent": intent, "parameters": parameters}

@router.get("/history", summary="세션별 채팅 이력 조회", description="특정 세션 ID의 모든 채팅 메시지(유저/AI)를 시간순으로 반환합니다.")
async def get_chat_history(session_id: int):
    messages = await MCPMessage.find({"session_id": session_id}).sort("created_at").to_list()
    return [
        {
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at
        }
        for msg in messages
    ]
