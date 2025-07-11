from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings
from app.models.mongo import MCPMessage
from datetime import datetime
from openai import OpenAI
from fastapi.concurrency import run_in_threadpool

router = APIRouter()

client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url=settings.OPENROUTER_BASE_URL,
)

class MessageIn(BaseModel):
    session_id: str
    message: str

@router.post("/chat/")
async def chat_with_llm(data: MessageIn):
    # 1. 사용자 질문 DB 저장
    user_msg = MCPMessage(
        session_id=data.session_id,
        role="user",
        content=data.message,
        created_at=datetime.utcnow()
    )
    await user_msg.insert()

    # 2. 동기 LLM 호출을 비동기로 감싸기
    response = await run_in_threadpool(
        client.chat.completions.create,
        model="deepseek/deepseek-chat-v3-0324",  # OpenRouter 지원 모델명
        messages=[{"role": "user", "content": data.message}],
        extra_headers={
            "HTTP-Referer": "https://yourdomain.com",  # 필요시 설정
            "X-Title": "YourSiteName",                 # 필요시 설정
        }
    )
    answer = response.choices[0].message.content

    # 3. LLM 답변 DB 저장
    ai_msg = MCPMessage(
        session_id=data.session_id,
        role="assistant",
        content=answer,
        created_at=datetime.utcnow()
    )
    await ai_msg.insert()

    # 4. 응답 반환
    return {"message": answer}

@router.get("/chat/history/")
async def get_history(session_id: str, limit: int = 50):
    messages = await MCPMessage.find(
        MCPMessage.session_id == session_id
    ).sort("+created_at").limit(limit).to_list()
    return messages
