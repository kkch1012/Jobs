from fastapi import APIRouter, HTTPException
from app.services.mcp_client import mcp_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP"])

@router.get("/tools", summary="MCP 도구 목록 조회", description="MCP 서버에서 사용 가능한 모든 도구 목록을 조회합니다.")
async def list_mcp_tools():
    """MCP 서버의 사용 가능한 도구 목록을 반환합니다."""
    try:
        tools = await mcp_client.list_tools()
        return {"tools": tools}
    except Exception as e:
        logger.error(f"MCP 도구 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MCP 서버 연결 실패: {str(e)}")

@router.get("/health", summary="MCP 서버 상태 확인", description="MCP 서버의 상태를 확인합니다.")
async def check_mcp_health():
    """MCP 서버의 상태를 확인합니다."""
    try:
        health = await mcp_client.health_check()
        return health
    except Exception as e:
        logger.error(f"MCP 서버 상태 확인 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MCP 서버 상태 확인 실패: {str(e)}") 