# app/routers/mcp.py

from fastapi import APIRouter, Depends
from app.core.security import get_current_user  # JWT 인증 사용할 경우
from app.mcp_client import parse_mcp
from app.models.user import User

router = APIRouter(prefix="/mcp", tags=["MCP"])

# JWT 인증 기반 예시
@router.get("/", summary="mcp 엔드포인트", description="프론트엔드에서 전달된 자연어 명령을 처리하는 MCP 엔드포인트")
async def mcp_endpoint(
    message: str,
    current_user: User = Depends(get_current_user)
):
    """
    Frontend에서 전달된 자연어 명령을 처리하는 MCP 엔드포인트.
    예: /mcp?message=파이썬+로드맵+추천해줘
    """
    try:
        user_id = current_user.id
        response_data = await parse_mcp(message, user_id)
        return response_data
    except Exception as e:
        return {
            "status": "error",
            "message": "MCP 요청 처리 실패",
            "detail": str(e)
        }

# 만약 인증 없이 익명도 허용할 거면 user_id 파라미터로 받을 수도 있음
# @router.get("/")
# async def mcp_endpoint(message: str, user_id: int = None):
#     ...
