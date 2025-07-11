import json
from fastapi import APIRouter, HTTPException
from datetime import datetime
from fastapi.concurrency import run_in_threadpool
from openai import OpenAI
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models.mongo import MCPMessage
from app.schemas.mcp import MessageIn, MCPIntent, MCPResponse, MCPMessageOut, MCPContext
from app.schemas.job_post import JobPostResponse
from app.schemas.certificate import CertificateResponse
from app.schemas.roadmap import RoadmapResponse
from app.schemas.skill import SkillResponse
from app.schemas.user import UserResponse
from app.services.mcp_service import mcp_service
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.user_skill import UserSkill
from app.models.skill import Skill
from app.models.user_certificate import UserCertificate
from app.models.certificate import Certificate
from fastapi import Depends
from typing import Optional

from app.routers import (
    auth,
    certificate,
    job_post,
    job_required_skill,
    roadmap,
    skill as skill_router,
    user_certificate,
    user_preference,
    user_roadmap,
    user_skill,
    user,
    visualization,
)

router = APIRouter()

client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url=settings.OPENROUTER_BASE_URL,
)

async def summarize_response_with_llm(original_message: str, api_result: dict | list | None) -> str:
    if api_result is None:
        response = await run_in_threadpool(
            client.chat.completions.create,
            model="deepseek/deepseek-chat-v3-0324",
            messages=[
                {"role": "user", "content": original_message}
            ]
        )
        return response.choices[0].message.content.strip()

    response = await run_in_threadpool(
        client.chat.completions.create,
        model="deepseek/deepseek-chat-v3-0324",
        messages=[
            {"role": "system", "content": "다음 데이터를 사용자에게 자연스럽게 설명해 주세요."},
            {"role": "user", "content": json.dumps(api_result, ensure_ascii=False)}
        ]
    )
    return response.choices[0].message.content.strip()

async def analyze_and_route(user_message: str, session_id: str | None = None, current_user: Optional[User] = None) -> dict | list | None:
    """사용자 메시지를 분석하고 적절한 API를 호출합니다."""
    
    # MCP 컨텍스트 구성
    context = None
    if session_id:
        conversation_history = await mcp_service.get_conversation_history(session_id, limit=5)
        context = MCPContext(
            session_id=session_id,
            conversation_history=conversation_history,
            available_tools=mcp_service.available_tools
        )
    
    # 의도 분석
    intent = await mcp_service.analyze_intent(user_message, context)
    if not intent:
        return None

    # 라우터별 API 호출
    db: Session = next(get_db())
    try:
        if intent.router == "/job_posts":
            job_posts = job_post.read_job_posts(db=db)
            # SQLAlchemy 객체를 Pydantic 모델로 변환
            return [JobPostResponse.model_validate(post) for post in job_posts]
        elif intent.router == "/certificates":
            certificates = certificate.list_all_certificates(db=db)
            return [CertificateResponse.model_validate(cert) for cert in certificates]
        elif intent.router == "/roadmaps":
            roadmaps = roadmap.get_all_roadmaps(db=db)
            return [RoadmapResponse.model_validate(roadmap) for roadmap in roadmaps]
        elif intent.router == "/skills":
            skill_list = skill_router.list_skills(db=db)
            return [SkillResponse.model_validate(skill_obj) for skill_obj in skill_list]
        elif intent.router == "/user_skills":
            if current_user:
                try:
                    # 실제 사용자 기술 정보 조회
                    user_skills = db.query(UserSkill).filter(UserSkill.user_id == current_user.id).all()
                    skill_details = []
                    for user_skill in user_skills:
                        skill = db.query(Skill).filter(Skill.id == user_skill.skill_id).first()
                        if skill:
                            skill_details.append({
                                "skill_name": skill.name,
                                "proficiency": user_skill.proficiency
                            })
                    return {
                        "user_id": current_user.id,
                        "user_skills": skill_details,
                        "total_skills": len(skill_details)
                    }
                except Exception as e:
                    return {"message": f"사용자 기술 정보 조회 실패: {str(e)}"}
            else:
                return {"message": "사용자 인증이 필요한 기능입니다. 유효한 토큰을 포함해주세요."}
        elif intent.router == "/user_certificates":
            if current_user:
                try:
                    # 실제 사용자 자격증 정보 조회
                    user_certs = db.query(UserCertificate).filter(UserCertificate.user_id == current_user.id).all()
                    cert_details = []
                    for user_cert in user_certs:
                        cert = db.query(Certificate).filter(Certificate.id == user_cert.certificate_id).first()
                        if cert:
                            cert_details.append({
                                "certificate_name": cert.name,
                                "issuer": cert.issuer,
                                "acquired_date": user_cert.acquired_date.isoformat() if user_cert.acquired_date else None
                            })
                    return {
                        "user_id": current_user.id,
                        "user_certificates": cert_details,
                        "total_certificates": len(cert_details)
                    }
                except Exception as e:
                    return {"message": f"사용자 자격증 정보 조회 실패: {str(e)}"}
            else:
                return {"message": "사용자 인증이 필요한 기능입니다. 유효한 토큰을 포함해주세요."}
        elif intent.router == "/user_profile":
            if current_user:
                try:
                    # 실제 사용자 프로필 정보 조회
                    return {
                        "user_id": current_user.id,
                        "email": current_user.email,
                        "nickname": current_user.nickname,
                        "name": current_user.name,
                        "phone_number": current_user.phone_number,
                        "birth_date": current_user.birth_date.isoformat() if current_user.birth_date else None,
                        "gender": current_user.gender,
                        "university": current_user.university,
                        "major": current_user.major,
                        "gpa": current_user.gpa,
                        "education_status": current_user.education_status,
                        "degree": current_user.degree,
                        "desired_job": current_user.desired_job
                    }
                except Exception as e:
                    return {"message": f"사용자 프로필 조회 실패: {str(e)}"}
            else:
                return {"message": "사용자 인증이 필요한 기능입니다. 유효한 토큰을 포함해주세요."}
        elif intent.router == "/update_user_profile":
            if current_user:
                try:
                    # 사용자 프로필 수정
                    update_data = intent.parameters
                    updated_fields = []
                    
                    # 수정 가능한 필드들
                    allowed_fields = [
                        "nickname", "name", "phone_number", "university", 
                        "major", "gpa", "education_status", "degree", "desired_job"
                    ]
                    
                    for field, value in update_data.items():
                        if field in allowed_fields and hasattr(current_user, field):
                            setattr(current_user, field, value)
                            updated_fields.append(field)
                    
                    if updated_fields:
                        db.commit()
                        return {
                            "message": f"프로필이 성공적으로 업데이트되었습니다.",
                            "updated_fields": updated_fields,
                            "user_id": current_user.id
                        }
                    else:
                        return {"message": "업데이트할 수 있는 필드가 없습니다."}
                except Exception as e:
                    return {"message": f"프로필 업데이트 실패: {str(e)}"}
            else:
                return {"message": "사용자 인증이 필요한 기능입니다. 유효한 토큰을 포함해주세요."}
        else:
            return {"message": f"지원하지 않는 요청입니다: {intent.router}"}
    finally:
        db.close()

@router.post("/chat/",
             summary="AI 챗봇과 대화",
             description="""
MCP(Model Context Protocol)를 사용하여 AI 챗봇과 대화합니다.

- 사용자의 자연어 메시지를 분석하여 적절한 API를 호출합니다.
- 대화 히스토리를 MongoDB에 저장합니다.
- API 결과를 자연스러운 응답으로 변환합니다.
- 로그인된 사용자의 경우 개인 정보도 조회/수정 가능합니다.

**지원하는 요청 예시:**
- "채용공고 목록을 보여주세요"
- "IT 관련 자격증이 뭐가 있나요?"
- "내 기술 스택을 보여주세요" (로그인 필요)
- "내 프로필을 수정해주세요" (로그인 필요)
""")
async def chat_with_llm(
    data: MessageIn,
    current_user: Optional[User] = Depends(get_current_user)
):
    # 사용자 메시지 저장
    await mcp_service.save_message(
        session_id=data.session_id,
        role="user",
        content=data.message
    )

    # API 호출 및 응답 생성
    api_result = await analyze_and_route(data.message, data.session_id, current_user)
    answer = await mcp_service.summarize_response(data.message, api_result)

    # AI 응답 저장
    await mcp_service.save_message(
        session_id=data.session_id,
        role="assistant",
        content=answer,
        intent=api_result
    )

    return {"message": answer}

@router.get("/chat/history/",
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
async def get_history(session_id: str, limit: int = 50):
    messages = await MCPMessage.find(
        MCPMessage.session_id == session_id
    ).sort("+created_at").limit(limit).to_list()
    return messages

@router.get("/chat/context/{session_id}",
            summary="MCP 컨텍스트 정보 조회",
            description="""
MCP(Model Context Protocol) 컨텍스트 정보를 조회합니다.

- 세션별 대화 상태와 사용 가능한 도구 목록을 반환합니다.
- 최근 10개 메시지의 요약 정보를 제공합니다.
- MCP 시스템의 현재 상태를 파악할 수 있습니다.

**반환 정보:**
- `session_id`: 세션 ID
- `message_count`: 총 메시지 개수
- `last_message`: 마지막 메시지 정보
- `available_tools`: 사용 가능한 API 도구 목록

**사용 가능한 도구:**
- `/job_posts`: 채용공고 조회
- `/certificates`: 자격증 조회
- `/roadmaps`: 로드맵 조회
- `/skills`: 기술 스택 조회
- `/visualizations`: 데이터 시각화
""")
async def get_mcp_context(session_id: str):
    """MCP 컨텍스트 정보를 반환합니다."""
    messages = await MCPMessage.find(
        MCPMessage.session_id == session_id
    ).sort("+created_at").limit(10).to_list()
    
    return {
        "session_id": session_id,
        "message_count": len(messages),
        "last_message": messages[-1] if messages else None,
        "available_tools": [
            "/job_posts",
            "/certificates", 
            "/roadmaps",
            "/skills",
            "/visualizations"
        ]
    }

@router.post("/chat/stream/",
             summary="스트리밍 채팅 응답",
             description="""
스트리밍 방식으로 AI 챗봇과 대화합니다.

- 일반 채팅과 동일한 기능을 제공하지만 추가 정보를 포함합니다.
- 의도 분석 결과를 함께 반환합니다.
- 로그인된 사용자의 경우 개인 정보도 조회/수정 가능합니다.

**반환 정보:**
- `message`: AI 응답 메시지
- `session_id`: 세션 ID
- `intent`: 의도 분석 결과 (호출된 API 정보)

**사용 시나리오:**
- 실시간 채팅 인터페이스
- 의도 분석 결과가 필요한 경우
- 디버깅 및 모니터링 목적
""")
async def chat_stream(
    data: MessageIn,
    current_user: Optional[User] = Depends(get_current_user)
):
    """스트리밍 채팅 응답을 위한 엔드포인트"""
    user_msg = MCPMessage(
        session_id=data.session_id,
        role="user",
        content=data.message,
        created_at=datetime.utcnow()
    )
    await user_msg.insert()

    # 의도 분석
    intent_result = await analyze_and_route(data.message, data.session_id, current_user)
    
    # 응답 생성
    answer = await summarize_response_with_llm(data.message, intent_result)

    ai_msg = MCPMessage(
        session_id=data.session_id,
        role="assistant",
        content=answer,
        created_at=datetime.utcnow(),
        intent=intent_result
    )
    await ai_msg.insert()

    return {
        "message": answer,
        "session_id": data.session_id,
        "intent": intent_result
    }
