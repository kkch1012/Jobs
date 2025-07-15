import httpx
import json
from typing import Dict, Any, Optional, List
from fastapi import HTTPException
from app.config import settings

class MCPClient:
    """외부 MCP 서버와 통신하는 클라이언트"""
    
    def __init__(self, mcp_server_url: str = "http://localhost:8001"):
        self.mcp_server_url = mcp_server_url
        self.client = httpx.AsyncClient()
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """사용 가능한 도구 목록을 조회합니다."""
        try:
            response = await self.client.get(f"{self.mcp_server_url}/tools")
            if response.status_code == 200:
                data = response.json()
                return data.get("tools", [])
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MCP 서버 연결 실패: {str(e)}")
    
    async def call_tool_with_auth(self, tool_name: str, arguments: Dict[str, Any], auth_token: str) -> Dict[str, Any]:
        """인증 토큰과 함께 특정 도구를 호출합니다."""
        try:
            payload = {
                "name": tool_name,
                "arguments": arguments,
                "authorization": auth_token
            }
            response = await self.client.post(
                f"{self.mcp_server_url}/tools/{tool_name}/call",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                # content에서 text 추출
                content = data.get("content", [])
                if content and len(content) > 0:
                    text_content = content[0].get("text", "{}")
                    return json.loads(text_content)
                return {}
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"도구 호출 실패: {str(e)}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """특정 도구를 호출합니다."""
        try:
            payload = {
                "name": tool_name,
                "arguments": arguments
            }
            response = await self.client.post(
                f"{self.mcp_server_url}/tools/{tool_name}/call",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                # content에서 text 추출
                content = data.get("content", [])
                if content and len(content) > 0:
                    text_content = content[0].get("text", "{}")
                    return json.loads(text_content)
                return {}
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"도구 호출 실패: {str(e)}")
    
    async def chat_with_mcp(self, method: str, params: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
        """MCP 프로토콜을 통한 채팅"""
        try:
            payload = {
                "method": method,
                "params": params,
                "id": request_id
            }
            response = await self.client.post(f"{self.mcp_server_url}/chat", json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MCP 채팅 실패: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """MCP 서버 상태를 확인합니다."""
        try:
            response = await self.client.get(f"{self.mcp_server_url}/health")
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MCP 서버 상태 확인 실패: {str(e)}")

# 전역 MCP 클라이언트 인스턴스
mcp_client = MCPClient() 