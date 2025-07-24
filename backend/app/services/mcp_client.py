import httpx
import json
from typing import Dict, Any, Optional, List
from fastapi import HTTPException
from app.config import settings

class MCPClient:
    """외부 MCP 서버와 통신하는 클라이언트"""
    
    def __init__(self, mcp_server_url: str = None):
        from app.config import settings
        self.mcp_server_url = mcp_server_url or settings.MCP_SERVER_URL
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
    
    # 새로운 기능들을 위한 편의 메서드들
    async def perform_gap_analysis(self, category: str, auth_token: str) -> Dict[str, Any]:
        """사용자의 갭 분석을 수행합니다."""
        return await self.call_tool_with_auth("gap_analysis", {"category": category}, auth_token)
    
    async def search_skills(self, skill_name: str) -> Dict[str, Any]:
        """스킬명으로 검색합니다."""
        return await self.call_tool("skill_search", {"skill_name": skill_name})
    
    async def get_roadmap_recommendations(self, category: str, limit: int = 10, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """갭 분석 기반 로드맵 추천을 받습니다."""
        arguments = {"category": category, "limit": limit}
        if auth_token:
            return await self.call_tool_with_auth("roadmap_recommendations", arguments, auth_token)
        else:
            return await self.call_tool("roadmap_recommendations", arguments)
    
    async def get_roadmap_recommendations_direct(self, category: str, gap_result_text: str, limit: int = 10, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """직접 갭 분석 결과로 로드맵 추천을 받습니다."""
        arguments = {
            "category": category, 
            "gap_result_text": gap_result_text, 
            "limit": limit
        }
        if auth_token:
            return await self.call_tool_with_auth("roadmap_recommendations_direct", arguments, auth_token)
        else:
            return await self.call_tool("roadmap_recommendations_direct", arguments)
    
    async def compare_resume_vs_job_skills(self, job_name: str, field: str = "tech_stack", auth_token: Optional[str] = None) -> Dict[str, Any]:
        """이력서 스킬과 직무 스킬을 비교합니다."""
        arguments = {"job_name": job_name, "field": field}
        if auth_token:
            return await self.call_tool_with_auth("resume_vs_job_skill_trend", arguments, auth_token)
        else:
            return await self.call_tool("resume_vs_job_skill_trend", arguments)
    
    async def get_weekly_skill_frequency(self, job_name: str, field: str = "tech_stack") -> Dict[str, Any]:
        """주간 스킬 빈도를 조회합니다."""
        return await self.call_tool("visualization", {"job_name": job_name, "field": field})
    
    async def get_job_recommendations(self, top_n: int = 20, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """맞춤형 채용공고 추천을 받습니다."""
        arguments = {"top_n": top_n}
        if auth_token:
            return await self.call_tool_with_auth("job_recommendation", arguments, auth_token)
        else:
            return await self.call_tool("job_recommendation", arguments)
    
    async def get_my_resume(self, auth_token: str, requested_field: Optional[str] = None) -> Dict[str, Any]:
        """내 이력서 정보를 조회합니다."""
        arguments = {}
        if requested_field:
            arguments["requested_field"] = requested_field
        return await self.call_tool_with_auth("get_my_resume", arguments, auth_token)
    
    async def update_resume(self, resume_data: Dict[str, Any], auth_token: str) -> Dict[str, Any]:
        """이력서 정보를 업데이트합니다."""
        return await self.call_tool_with_auth("update_resume", resume_data, auth_token)

# 전역 MCP 클라이언트 인스턴스
mcp_client = MCPClient() 