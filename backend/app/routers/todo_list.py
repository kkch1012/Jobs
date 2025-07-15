from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.services.llm_client import llm_client
from app.services.mcp_client import mcp_client

router = APIRouter(prefix="/todo", tags=["todo"])

@router.post("/generate", summary="맞춤형 todo-list 생성")
async def generate_todo_list(user_id: int, course: str, days: int, db: Session = Depends(get_db)):
    # ... (생성 로직, 위 답변 참고)
    pass

@router.get("/user/{user_id}", summary="유저의 todo-list 조회")
def get_user_todo_list(user_id: int, db: Session = Depends(get_db)):
    # ... (조회 로직, 위 답변 참고)
    pass