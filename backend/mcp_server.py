from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import httpx
import json
from datetime import datetime
import asyncio

# MCP 서버 설정
MCP_SERVER_HOST = "localhost"
MCP_SERVER_PORT = 8001
FASTAPI_SERVER_URL = "http://localhost:8000"  # 기존 FastAPI 서버 URL

app = FastAPI(
    title="MCP Server",
    description="Model Context Protocol Server for Job Platform",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP 도구 정의
class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]
    outputSchema: Dict[str, Any]

# 사용 가능한 도구들
AVAILABLE_TOOLS = {
    "job_posts": MCPTool(
        name="job_posts",
        description="채용공고 목록을 조회합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "company_name": {"type": "string", "description": "회사명"},
                "job_name": {"type": "string", "description": "직무명"},
                "limit": {"type": "integer", "description": "조회 개수", "default": 10}
            }
        },
        outputSchema={
            "type": "object",
            "properties": {
                "jobs": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "certificates": MCPTool(
        name="certificates",
        description="자격증 목록을 조회합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "자격증 카테고리"},
                "limit": {"type": "integer", "description": "조회 개수", "default": 10}
            }
        },
        outputSchema={
            "type": "object",
            "properties": {
                "certificates": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "skills": MCPTool(
        name="skills",
        description="기술 스택 목록을 조회합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "기술 카테고리"},
                "limit": {"type": "integer", "description": "조회 개수", "default": 10}
            }
        },
        outputSchema={
            "type": "object",
            "properties": {
                "skills": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "roadmaps": MCPTool(
        name="roadmaps",
        description="취업 로드맵을 조회합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "field": {"type": "string", "description": "분야"},
                "limit": {"type": "integer", "description": "조회 개수", "default": 10}
            }
        },
        outputSchema={
            "type": "object",
            "properties": {
                "roadmaps": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "visualization": MCPTool(
        name="visualization",
        description="직무별 스킬 빈도 시각화 데이터를 조회합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "job_name": {"type": "string", "description": "직무명"},
                "field": {"type": "string", "description": "분석 필드", "default": "tech_stack"}
            }
        },
        outputSchema={
            "type": "object",
            "properties": {
                "weekly_skill_frequency": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "get_my_resume": MCPTool(
        name="get_my_resume",
        description="내 이력서 정보를 조회합니다",
        inputSchema={
            "type": "object",
            "properties": {}
        },
        outputSchema={
            "type": "object",
            "properties": {
                "resume": {"type": "object", "description": "이력서 정보"}
            }
        }
    ),
    "update_resume": MCPTool(
        name="update_resume",
        description="이력서 정보를 수정/입력합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "resume_data": {"type": "object", "description": "수정할 이력서 데이터"}
            }
        },
        outputSchema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "수정 결과 메시지"}
            }
        }
    ),
    "job_recommendation": MCPTool(
        name="job_recommendation",
        description="사용자에게 맞춤형 채용공고를 추천합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "top_n": {"type": "integer", "description": "유사도 상위 N개에서 추천", "default": 20}
            }
        },
        outputSchema={
            "type": "object",
            "properties": {
                "recommendation": {"type": "string", "description": "추천 결과 및 설명"},
                "job_count": {"type": "integer", "description": "추천된 공고 수"}
            }
        }
    )
}

# MCP 요청/응답 모델
class MCPRequest(BaseModel):
    method: str
    params: Dict[str, Any]
    id: Optional[str] = None

class MCPResponse(BaseModel):
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]
    authorization: Optional[str] = None  # Bearer 토큰

class ToolCallResponse(BaseModel):
    content: List[Dict[str, Any]]

# FastAPI 서버와 통신하는 클라이언트
class FastAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def call_api(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """FastAPI 서버의 엔드포인트를 호출합니다."""
        try:
            url = f"{self.base_url}{endpoint}"
            request_headers = headers or {}
            
            if params:
                # GET 요청의 경우 쿼리 파라미터로 전달
                response = await self.client.get(url, params=params, headers=request_headers, follow_redirects=True)
            else:
                response = await self.client.get(url, headers=request_headers, follow_redirects=True)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"FastAPI 서버 호출 실패: {str(e)}")
    
    async def put_api(self, endpoint: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """FastAPI 서버의 PUT 엔드포인트를 호출합니다."""
        try:
            url = f"{self.base_url}{endpoint}"
            request_headers = headers or {}
            response = await self.client.put(url, json=data, headers=request_headers, follow_redirects=True)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"FastAPI 서버 PUT 호출 실패: {str(e)}")

# FastAPI 클라이언트 인스턴스
fastapi_client = FastAPIClient(FASTAPI_SERVER_URL)

@app.get("/", summary="MCP 서버 상태 확인", description="MCP 서버가 정상적으로 동작하는지 확인합니다. 서버 버전과 사용 가능한 도구 목록을 반환합니다.")
async def root():
    """MCP 서버 상태 확인"""
    return {
        "message": "MCP Server is running",
        "version": "1.0.0",
        "available_tools": list(AVAILABLE_TOOLS.keys())
    }

@app.get("/tools", summary="사용 가능한 도구 목록 조회", description="MCP 서버에 등록된 모든 도구의 이름, 설명, 입력/출력 스키마를 반환합니다.")
async def list_tools():
    """사용 가능한 도구 목록을 반환합니다."""
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
                "outputSchema": tool.outputSchema
            }
            for tool in AVAILABLE_TOOLS.values()
        ]
    }

@app.post("/tools/{tool_name}/call", summary="특정 도구 호출", description="지정한 도구 이름과 파라미터로 FastAPI 서버의 기능을 호출하고 결과를 반환합니다.")
async def call_tool(tool_name: str, request: ToolCallRequest):
    """특정 도구를 호출합니다."""
    if tool_name not in AVAILABLE_TOOLS:
        raise HTTPException(status_code=404, detail=f"도구 '{tool_name}'을 찾을 수 없습니다")
    
    try:
        # 도구별 엔드포인트 매핑
        endpoint_mapping = {
            "job_posts": "/job_posts/",
            "certificates": "/certificates/",
            "skills": "/skills/",
            "roadmaps": "/roadmaps/",
            "visualization": "/visualization/weekly_skill_frequency",
            "get_my_resume": "/users/me/resume",
            "update_resume": "/users/me/resume",
            "job_recommendation": "/recommend/jobs"
        }
        
        endpoint = endpoint_mapping.get(tool_name)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"도구 '{tool_name}'에 대한 엔드포인트가 정의되지 않았습니다")
        
        # FastAPI 서버의 해당 엔드포인트 호출
        headers = {}
        if request.authorization:
            headers["Authorization"] = request.authorization
        
        if tool_name == "update_resume":
            # PUT 요청으로 처리
            result = await fastapi_client.put_api(
                endpoint,
                request.arguments.get("resume_data", {}),
                headers=headers
            )
            return ToolCallResponse(content=[
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False)
                }
            ])
        else:
            # GET 요청으로 처리
            result = await fastapi_client.call_api(endpoint, request.arguments, headers=headers)
            return ToolCallResponse(content=[
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False)
                }
            ])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"도구 호출 실패: {str(e)}")

@app.post("/chat", summary="MCP 프로토콜 채팅", description="MCP 프로토콜을 통해 도구 목록 조회, 도구 호출 등 다양한 기능을 제공합니다.")
async def chat_with_mcp(request: MCPRequest):
    """MCP 프로토콜을 통한 채팅"""
    if request.method == "tools/list":
        return MCPResponse(
            result={"tools": list(AVAILABLE_TOOLS.keys())},
            id=request.id
        )
    elif request.method == "tools/call":
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        if tool_name not in AVAILABLE_TOOLS:
            return MCPResponse(
                error={"message": f"도구 '{tool_name}'을 찾을 수 없습니다"},
                id=request.id
            )
        
        try:
            # FastAPI 서버 호출
            endpoint = f"/{tool_name}/"
            api_result = await fastapi_client.call_api(endpoint, arguments)
            
            if isinstance(api_result, list):
                jobs = api_result
            else:
                jobs = api_result.get("jobs", [])

            if jobs:
                answer = f"채용공고를 {len(jobs)}개 찾았습니다! ..."
            else:
                answer = "현재 등록된 채용공고가 없습니다."

            return MCPResponse(
                result={"content": [{"type": "text", "text": answer}]},
                id=request.id
            )
        except Exception as e:
            return MCPResponse(
                error={"message": f"도구 호출 실패: {str(e)}"},
                id=request.id
            )
    else:
        return MCPResponse(
            error={"message": f"지원하지 않는 메서드: {request.method}"},
            id=request.id
        )

@app.get("/health", summary="서버 상태 확인", description="MCP 서버의 헬스체크 엔드포인트. 서버가 정상 동작 중인지 확인합니다.")
async def health_check():
    """서버 상태 확인"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "mcp_server:app",
        host=MCP_SERVER_HOST,
        port=MCP_SERVER_PORT,
        reload=True
    ) 