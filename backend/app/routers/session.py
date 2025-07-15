from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.chat_session import ChatSession
from app.schemas.chat_session import ChatSessionCreate, ChatSessionResponse
from typing import List
from app.utils.dependencies import get_current_user
from app.models.user import User

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

@router.get("/my", response_model=List[int], summary="내 채팅 세션 ID 조회")
def get_my_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).all()
    session_ids = [s.id for s in sessions]
    return session_ids 