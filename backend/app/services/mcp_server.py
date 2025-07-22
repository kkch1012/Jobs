from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import httpx
import json
from datetime import datetime
import asyncio
from app.utils.text_utils import clean_markdown_text

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
                "job_name": {"type": "string", "description": "직무명 (예: 백엔드 개발자)"},
                "field": {"type": "string", "description": "분석 필드", "default": "tech_stack", "enum": ["tech_stack", "qualifications", "preferences", "required_skills", "preferred_skills"]}
            },
            "required": ["job_name"]
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
                "job_name": {"type": "string", "description": "희망직무 (예: 프론트엔드 개발자) - 기존 직무에 추가됨"},
                "university": {"type": "string", "description": "대학교명"},
                "major": {"type": "string", "description": "전공"},
                "gpa": {"type": "string", "description": "학점 (예: 4.0, 3.5)"},
                "education_status": {"type": "string", "description": "학적상태 (재학중/졸업/휴학)"},
                "degree": {"type": "string", "description": "학위 (학사/석사/박사)"},
                "language_score": {"type": "string", "description": "어학점수 (예: TOEIC 900, IELTS 7.0)"},
                "working_year": {"type": "string", "description": "경력연차 (예: 3년, 신입)"},
                "skills": {"type": "array", "items": {"type": "string"}, "description": "기술스택 목록"},
                "certificates": {"type": "array", "items": {"type": "string"}, "description": "자격증 목록"},
                "experience": {"type": "array", "items": {"type": "object"}, "description": "경험 목록"}
            }
        },
        outputSchema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "수정 결과 메시지"},
                "status": {"type": "string", "description": "상태 (success/duplicate/error)"},
                "current_data": {"type": "object", "description": "현재 이력서 데이터 (중복 시)"}
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
    ),
    "gap_analysis": MCPTool(
        name="gap_analysis",
        description="사용자의 이력과 선택한 직무를 바탕으로 GPT 기반 갭 분석을 수행합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "직무 카테고리 (예: 프론트엔드 개발자)"}
            },
            "required": ["category"]
        },
        outputSchema={
            "type": "object",
            "properties": {
                "gap_result": {"type": "string", "description": "자연어 갭 분석 결과"},
                "top_skills": {"type": "array", "items": {"type": "string"}, "description": "부족한 스킬 Top 5"}
            }
        }
    ),
    "skill_search": MCPTool(
        name="skill_search",
        description="weekly_skill_stats 테이블에서 스킬명을 검색하여 통계 정보를 반환합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "검색할 스킬명 (부분 검색 지원)"}
            },
            "required": ["skill_name"]
        },
        outputSchema={
            "type": "object",
            "properties": {
                "skills": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "roadmap_recommendations": MCPTool(
        name="roadmap_recommendations",
        description="사용자의 갭 분석 결과를 바탕으로 맞춤형 로드맵을 추천합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "직무 카테고리 (예: 프론트엔드 개발자)"},
                "limit": {"type": "integer", "description": "추천받을 로드맵 개수", "default": 10}
            },
            "required": ["category"]
        },
        outputSchema={
            "type": "object",
            "properties": {
                "roadmaps": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "roadmap_recommendations_direct": MCPTool(
        name="roadmap_recommendations_direct",
        description="이미 수행된 갭 분석 결과를 직접 입력받아 로드맵을 추천합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "직무 카테고리 (예: 프론트엔드 개발자)"},
                "gap_result_text": {"type": "string", "description": "갭 분석 결과 텍스트"},
                "limit": {"type": "integer", "description": "추천받을 로드맵 개수", "default": 10}
            },
            "required": ["category", "gap_result_text"]
        },
        outputSchema={
            "type": "object",
            "properties": {
                "roadmaps": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "resume_vs_job_skill_trend": MCPTool(
        name="resume_vs_job_skill_trend",
        description="내 이력서(보유 스킬)와 선택한 직무의 주간 스킬 빈도 통계를 비교합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "job_name": {"type": "string", "description": "비교할 직무명 (예: 백엔드 개발자)"},
                "field": {"type": "string", "description": "분석 대상 필드명", "default": "tech_stack"}
            },
            "required": ["job_name"]
        },
        outputSchema={
            "type": "object",
            "properties": {
                "comparison": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "page_move": MCPTool(
        name="page_move",
        description="사용자 요청에 따라 적절한 페이지로 이동합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "user_intent": {"type": "string", "description": "사용자의 의도 (예: 채용공고 보기, 이력서 수정, 추천 받기)"},
                "current_page": {"type": "string", "description": "현재 페이지 (선택사항)"},
                "additional_context": {"type": "string", "description": "추가 컨텍스트 정보 (선택사항)"}
            },
            "required": ["user_intent"]
        },
        outputSchema={
            "type": "object",
            "properties": {
                "target_page": {"type": "string", "description": "이동할 페이지명"},
                "page_data": {"type": "object", "description": "페이지에 필요한 데이터"},
                "message": {"type": "string", "description": "페이지 이동 안내 메시지"},
                "action": {"type": "string", "description": "수행할 액션 (page_move)"}
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
            "job_recommendation": "/recommend/jobs",
            "gap_analysis": "/visualization/gap-analysis",
            "skill_search": "/visualization/skill_search",
            "roadmap_recommendations": "/visualization/roadmap_recommendations",
            "roadmap_recommendations_direct": "/visualization/roadmap_recommendations/direct",
            "resume_vs_job_skill_trend": "/visualization/resume_vs_job_skill_trend",
            "page_move": "/mcp/page-move"
        }
        
        endpoint = endpoint_mapping.get(tool_name)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"도구 '{tool_name}'에 대한 엔드포인트가 정의되지 않았습니다")
        
        # FastAPI 서버의 해당 엔드포인트 호출
        headers = {}
        if request.authorization:
            headers["Authorization"] = request.authorization
        
        if tool_name == "update_resume":
            # update_resume의 경우 파라미터를 resume_data 구조로 변환
            arguments = request.arguments
            
            # 모든 파라미터를 resume_data로 변환
            resume_data = {}
            field_mapping = {
                "job_name": "desired_job",
                "university": "university",
                "major": "major", 
                "gpa": "gpa",
                "education_status": "education_status",
                "degree": "degree",
                "language_score": "language_score",
                "working_year": "working_year",
                "skills": "skills",
                "certificates": "certificates",
                "experience": "experience"
            }
            
            for arg_key, resume_key in field_mapping.items():
                if arg_key in arguments and arguments[arg_key] is not None:
                    resume_data[resume_key] = arguments[arg_key]
            
            # 1단계: 현재 이력서 조회
            try:
                current_resume = await fastapi_client.call_api("/users/me/resume", headers=headers)
                
                # 2단계: 중복 체크
                duplicate_check = False
                duplicate_message = ""
                
                if "desired_job" in resume_data and current_resume.get("desired_job"):
                    # JSON 배열로 처리
                    current_jobs = current_resume["desired_job"] if isinstance(current_resume["desired_job"], list) else []
                    new_job = resume_data["desired_job"]
                    
                    if new_job in current_jobs:
                        duplicate_check = True
                        duplicate_message = f"이미 '{new_job}'이(가) 희망직무로 등록되어 있습니다."
                    else:
                        # 기존 직무에 새 직무 추가
                        current_jobs.append(new_job)
                        resume_data["desired_job"] = current_jobs
                
                if "university" in resume_data and current_resume.get("university"):
                    if resume_data["university"] == current_resume["university"]:
                        duplicate_check = True
                        duplicate_message = f"이미 '{resume_data['university']}'이(가) 등록되어 있습니다."
                
                if "major" in resume_data and current_resume.get("major"):
                    if resume_data["major"] == current_resume["major"]:
                        duplicate_check = True
                        duplicate_message = f"이미 '{resume_data['major']}' 전공이 등록되어 있습니다."
                
                # 중복이 있으면 메시지 반환
                if duplicate_check:
                    return ToolCallResponse(content=[
                        {
                            "type": "text",
                            "text": json.dumps({
                                "msg": clean_markdown_text(duplicate_message),
                                "status": "duplicate",
                                "current_data": current_resume
                            }, ensure_ascii=False)
                        }
                    ])
                
                # 3단계: 중복이 없으면 업데이트 진행
                result = await fastapi_client.put_api(
                    endpoint,
                    resume_data,  # 변환된 resume_data 사용
                    headers=headers
                )
                return ToolCallResponse(content=[
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False)
                    }
                ])
                
            except Exception as e:
                # 조회 실패 시에도 업데이트 시도 (기존 동작 유지)
                result = await fastapi_client.put_api(
                    endpoint,
                    resume_data,
                    headers=headers
                )
                return ToolCallResponse(content=[
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False)
                    }
                ])
        elif tool_name == "visualization":
            # visualization 도구는 job_name과 field 파라미터가 필요
            arguments = request.arguments
            if "job_name" not in arguments:
                raise HTTPException(status_code=400, detail="visualization 도구는 job_name 파라미터가 필요합니다")
            
            # field 파라미터가 없으면 기본값 사용
            if "field" not in arguments:
                arguments["field"] = "tech_stack"
            
            result = await fastapi_client.call_api(endpoint, arguments, headers=headers)
            return ToolCallResponse(content=[
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False)
                }
            ])
        elif tool_name == "page_move":
            # 페이지 이동 로직 처리
            arguments = request.arguments
            user_intent = arguments.get("user_intent", "")
            current_page = arguments.get("current_page", "")
            
            # 사용자 의도에 따른 페이지 결정
            page_mapping = {
                "채용공고": "job_posts",
                "구인": "job_posts", 
                "일자리": "job_posts",
                "이력서": "resume",
                "프로필": "resume",
                "추천": "recommendations",
                "맞춤": "recommendations",
                "자격증": "certificates",
                "기술": "skills",
                "로드맵": "roadmaps",
                "학습": "roadmaps",
                "분석": "analysis",
                "통계": "statistics",
                "시각화": "visualization"
            }
            
            target_page = "home"  # 기본값
            for keyword, page in page_mapping.items():
                if keyword in user_intent:
                    target_page = page
                    break
            
            # 페이지별 필요한 데이터 수집
            page_data = {}
            if target_page == "job_posts":
                # 채용공고 목록 데이터
                job_data = await fastapi_client.call_api("/job_posts/", {"limit": 10}, headers=headers)
                page_data = {"jobs": job_data}
            elif target_page == "resume":
                # 이력서 데이터
                resume_data = await fastapi_client.call_api("/users/me/resume", headers=headers)
                page_data = {"resume": resume_data}
            elif target_page == "recommendations":
                # 추천 데이터
                recommend_data = await fastapi_client.call_api("/recommend/jobs", headers=headers)
                page_data = {"recommendations": recommend_data}
            
            result = {
                "target_page": target_page,
                "page_data": page_data,
                "message": f"'{user_intent}' 요청에 따라 {target_page} 페이지로 이동합니다.",
                "action": "page_move"
            }
            
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
            # 도구별 엔드포인트 매핑
            endpoint_mapping = {
                "job_posts": "/job_posts/",
                "certificates": "/certificates/",
                "skills": "/skills/",
                "roadmaps": "/roadmaps/",
                "visualization": "/visualization/weekly_skill_frequency",
                "get_my_resume": "/users/me/resume",
                "update_resume": "/users/me/resume",
                "job_recommendation": "/recommend/jobs",
                "gap_analysis": "/visualization/gap-analysis",
                "skill_search": "/visualization/skill_search",
                "roadmap_recommendations": "/visualization/roadmap_recommendations",
                "roadmap_recommendations_direct": "/visualization/roadmap_recommendations/direct",
                "resume_vs_job_skill_trend": "/visualization/resume_vs_job_skill_trend"
            }
            
            endpoint = endpoint_mapping.get(tool_name)
            if not endpoint:
                return MCPResponse(
                    error={"message": f"도구 '{tool_name}'에 대한 엔드포인트가 정의되지 않았습니다"},
                    id=request.id
                )
            
            # FastAPI 서버 호출
            api_result = await fastapi_client.call_api(endpoint, arguments)
            
            # 도구별 응답 처리
            if tool_name == "gap_analysis":
                if isinstance(api_result, dict) and "gap_result" in api_result:
                    gap_result = clean_markdown_text(api_result['gap_result'])
                    answer = f"갭 분석이 완료되었습니다.\n\n분석 결과:\n{gap_result}\n\n부족한 스킬 Top 5:\n" + "\n".join([f"• {skill}" for skill in api_result.get('top_skills', [])])
                else:
                    answer = "갭 분석을 수행할 수 없습니다."
            elif tool_name == "skill_search":
                if isinstance(api_result, list) and len(api_result) > 0:
                    answer = f"'{arguments.get('skill_name', '')}' 관련 스킬을 {len(api_result)}개 찾았습니다."
                else:
                    answer = f"'{arguments.get('skill_name', '')}' 관련 스킬을 찾을 수 없습니다."
            elif tool_name == "roadmap_recommendations":
                if isinstance(api_result, list) and len(api_result) > 0:
                    answer = f"로드맵을 {len(api_result)}개 추천받았습니다."
                else:
                    answer = "추천할 로드맵이 없습니다."
            elif tool_name == "roadmap_recommendations_direct":
                if isinstance(api_result, list) and len(api_result) > 0:
                    answer = f"직접 로드맵을 {len(api_result)}개 추천받았습니다."
                else:
                    answer = "추천할 로드맵이 없습니다."
            elif tool_name == "resume_vs_job_skill_trend":
                if isinstance(api_result, list) and len(api_result) > 0:
                    answer = f"이력서 vs 직무 스킬 비교 결과를 {len(api_result)}개 찾았습니다."
                else:
                    answer = "스킬 비교 결과가 없습니다."
            elif tool_name == "visualization":
                if isinstance(api_result, list) and len(api_result) > 0:
                    job_name = arguments.get('job_name', '해당 직무')
                    field = arguments.get('field', 'tech_stack')
                    answer = f"'{job_name}' 직무의 {field} 주간 스킬 빈도 데이터를 {len(api_result)}개 찾았습니다."
                else:
                    job_name = arguments.get('job_name', '해당 직무')
                    field = arguments.get('field', 'tech_stack')
                    answer = f"'{job_name}' 직무의 {field} 주간 스킬 빈도 데이터가 없습니다."
            elif tool_name == "job_recommendation":
                if isinstance(api_result, dict) and "recommendation" in api_result:
                    answer = clean_markdown_text(api_result["recommendation"])
                else:
                    answer = "채용공고 추천을 받을 수 없습니다."
            elif tool_name == "page_move":
                if isinstance(api_result, dict) and "target_page" in api_result:
                    target_page = api_result["target_page"]
                    message = api_result.get("message", "")
                    answer = f"{message}\n\n이동할 페이지: {target_page}"
                else:
                    answer = "페이지 이동을 처리할 수 없습니다."
            elif tool_name in ["job_posts", "certificates", "skills", "roadmaps"]:
                if isinstance(api_result, list) and len(api_result) > 0:
                    answer = f"{tool_name.replace('_', ' ').title()}를 {len(api_result)}개 찾았습니다!"
                else:
                    answer = f"현재 등록된 {tool_name.replace('_', ' ')}가 없습니다."
            else:
                answer = f"{tool_name} 도구가 성공적으로 실행되었습니다."

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
        "app.services.mcp_server:app",
        host=MCP_SERVER_HOST,
        port=MCP_SERVER_PORT,
        reload=True
    ) 