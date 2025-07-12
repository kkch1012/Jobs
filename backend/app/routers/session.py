from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.chat_session import ChatSession
from app.schemas.chat_session import ChatSessionCreate, ChatSessionResponse
from typing import List

router = APIRouter(prefix="/chat_sessions", tags=["chat_sessions"])

@router.post("/", response_model=ChatSessionResponse, summary="새 채팅 세션 생성")
def create_chat_session(session: ChatSessionCreate, db: Session = Depends(get_db)):
    db_session = ChatSession(**session.dict())
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

@router.delete("/{session_id}", summary="채팅 세션 삭제")
def delete_chat_session(session_id: int, db: Session = Depends(get_db)):
    db_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(db_session)
    db.commit()
    return {"ok": True} 