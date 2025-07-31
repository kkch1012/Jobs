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
from app.config import settings

MCP_SERVER_HOST = "localhost"
MCP_SERVER_PORT = 8001
FASTAPI_SERVER_URL = settings.FASTAPI_SERVER_URL  # 환경변수에서 가져오기

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
            "properties": {
                "requested_field": {"type": "string", "description": "요청한 특정 필드 (university, major, gpa, language_score, working_year, job_name, tech_stack, certificates, all)", "default": "all"}
            }
        },
        outputSchema={
            "type": "object",
            "properties": {
                "resume": {"type": "object", "description": "이력서 정보 (특정 필드 또는 전체)"}
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
    ),
    "get_my_skills": MCPTool(
        name="get_my_skills",
        description="내 보유 스킬 목록을 조회합니다 (특정 스킬 검색 가능)",
        inputSchema={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "특정 스킬명 (선택사항, 없으면 전체 조회)"
                }
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
    "add_my_skills": MCPTool(
        name="add_my_skills",
        description="내 보유 스킬을 추가합니다 (중복 검사 및 숙련도 확인 포함)",
        inputSchema={
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "스킬명 (한글/영어 모두 지원)"},
                "proficiency": {"type": "string", "description": "숙련도 (초급, 중급, 고급 또는 1-5점)"}
            },
            "required": ["skill_name"]
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "처리 상태 (success/duplicate/need_proficiency/skill_not_found)"},
                "message": {"type": "string", "description": "결과 메시지"},
                "skill_name": {"type": "string", "description": "스킬명"},
                "proficiency": {"type": "string", "description": "숙련도"},
                "skill_id": {"type": "integer", "description": "스킬 ID (중복/업데이트시)"}
            }
        }
    ),
    "get_my_certificates": MCPTool(
        name="get_my_certificates",
        description="내 보유 자격증 목록을 조회합니다",
        inputSchema={
            "type": "object",
            "properties": {}
        },
        outputSchema={
            "type": "object",
            "properties": {
                "certificates": {"type": "array", "items": {"type": "object"}},
                "total": {"type": "integer"}
            }
        }
    ),
    "add_my_certificates": MCPTool(
        name="add_my_certificates",
        description="내 보유 자격증을 추가합니다 (중복 검사 및 취득일 확인 포함)",
        inputSchema={
            "type": "object",
            "properties": {
                "certificate_name": {
                    "type": "string",
                    "description": "추가할 자격증명"
                },
                "acquired_date": {
                    "type": "string",
                    "description": "취득일 (YYYY-MM-DD 형식, 선택사항)"
                }
            },
            "required": ["certificate_name"]
        },
        outputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "message": {"type": "string"}
            }
        }
    ),
    "update_my_skill_proficiency": MCPTool(
        name="update_my_skill_proficiency",
        description="기존 보유 스킬의 숙련도를 업데이트합니다",
        inputSchema={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string", 
                    "description": "숙련도를 변경할 스킬명"
                },
                "proficiency": {
                    "type": "string",
                    "description": "새로운 숙련도 (초급/중급/고급)"
                }
            },
            "required": ["skill_name", "proficiency"]
        },
        outputSchema={
            "type": "object", 
            "properties": {
                "status": {"type": "string"},
                "message": {"type": "string"},
                "skill_name": {"type": "string"},
                "old_proficiency": {"type": "string"},
                "new_proficiency": {"type": "string"}
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
            
            print(f"[DEBUG] 요청 URL: {url}")
            print(f"[DEBUG] 요청 파라미터: {params}")
            print(f"[DEBUG] 요청 헤더: {request_headers}")
            
            if params:
                # GET 요청의 경우 쿼리 파라미터로 전달
                response = await self.client.get(url, params=params, headers=request_headers, follow_redirects=True)
            else:
                response = await self.client.get(url, headers=request_headers, follow_redirects=True)
            
            print(f"[DEBUG] 응답 상태코드: {response.status_code}")
            print(f"[DEBUG] 응답 내용: {response.text[:500]}")
            
            if response.status_code == 200:
                return response.json()
            else:
                error_detail = f"HTTP {response.status_code}: {response.text}"
                print(f"[ERROR] API 호출 실패: {error_detail}")
                raise HTTPException(status_code=response.status_code, detail=error_detail)
        except httpx.RequestError as e:
            error_detail = f"네트워크 요청 실패: {str(e)}"
            print(f"[ERROR] 네트워크 에러: {error_detail}")
            raise HTTPException(status_code=500, detail=error_detail)
        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP 상태 에러: {e.response.status_code} - {e.response.text}"
            print(f"[ERROR] HTTP 상태 에러: {error_detail}")
            raise HTTPException(status_code=e.response.status_code, detail=error_detail)
        except Exception as e:
            error_detail = f"예상치 못한 에러: {type(e).__name__}: {str(e)}"
            print(f"[ERROR] 예상치 못한 에러: {error_detail}")
            raise HTTPException(status_code=500, detail=error_detail)
    
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
    
    async def post_api(self, endpoint: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """FastAPI 서버의 POST 엔드포인트를 호출합니다."""
        try:
            url = f"{self.base_url}{endpoint}"
            request_headers = headers or {}
            response = await self.client.post(url, json=data, headers=request_headers, follow_redirects=True)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"FastAPI 서버 POST 호출 실패: {str(e)}")

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
            "job_recommendation": "/recommend/jobs/ids",
            "gap_analysis": "/visualization/gap_analysis",
            "roadmap_recommendations": "/visualization/roadmap_recommendations",
            "roadmap_recommendations_direct": "/visualization/roadmap_recommendations_direct",
            "resume_vs_job_skill_trend": "/visualization/resume_vs_job_skill_trend",
            "get_my_skills": "/users/me/skills",
            "add_my_skills": "/users/me/skills/smart-add",
            "get_my_certificates": "/users/me/certificates",
            "add_my_certificates": "/users/me/certificates/smart-add",
            "update_my_skill_proficiency": "/users/me/skills/update-proficiency-by-name"
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
                    value = arguments[arg_key]
                    
                    # skills와 certificates는 배열이어야 하므로 문자열이면 배열로 변환
                    if arg_key in ["skills", "certificates"] and isinstance(value, str):
                        value = [value]
                    
                    resume_data[resume_key] = value
            
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
        
        elif tool_name == "get_my_resume":
            # get_my_resume의 경우 requested_field 파라미터 처리
            arguments = request.arguments
            requested_field = arguments.get("requested_field", "all")
            
            try:
                # 전체 이력서 조회
                full_resume = await fastapi_client.call_api(endpoint, headers=headers)
                
                # requested_field에 따라 특정 필드만 반환
                if requested_field == "all":
                    # 전체 이력서 반환
                    result = {"resume": full_resume}
                else:
                    # 특정 필드만 추출
                    filtered_resume = {}
                    
                    if requested_field == "university":
                        filtered_resume["university"] = full_resume.get("university")
                    elif requested_field == "major":
                        filtered_resume["major"] = full_resume.get("major")
                    elif requested_field == "gpa":
                        filtered_resume["gpa"] = full_resume.get("gpa")
                    elif requested_field == "language_score":
                        filtered_resume["language_score"] = full_resume.get("language_score")
                    elif requested_field == "working_year":
                        filtered_resume["working_year"] = full_resume.get("working_year")
                    elif requested_field == "job_name":
                        filtered_resume["desired_job"] = full_resume.get("desired_job")
                    elif requested_field == "tech_stack":
                        filtered_resume["skills"] = full_resume.get("skills")
                    elif requested_field == "certificates":
                        filtered_resume["certificates"] = full_resume.get("certificates")
                    else:
                        # 알 수 없는 필드인 경우 전체 반환
                        filtered_resume = full_resume
                    
                    result = {"resume": filtered_resume}
                
                return ToolCallResponse(content=[
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False)
                    }
                ])
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"이력서 조회 실패: {str(e)}")
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
                # 추천 데이터 (채용공고 추천)
                recommend_data = await fastapi_client.call_api("/recommend/jobs/ids", headers=headers)
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
        elif tool_name == "get_my_skills":
            try:
                arguments = request.arguments
                skill_name = arguments.get("skill_name", "")
                if skill_name:
                    skills_data = await fastapi_client.call_api(endpoint, {"skill_name": skill_name}, headers=headers)
                else:
                    skills_data = await fastapi_client.call_api(endpoint, headers=headers)
                return ToolCallResponse(content=[
                    {
                        "type": "text",
                        "text": json.dumps(skills_data, ensure_ascii=False)
                    }
                ])
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"내 스킬 조회 실패: {str(e)}")
        elif tool_name == "add_my_skills":
            try:
                arguments = request.arguments
                skill_data = {
                    "skill_name": arguments.get("skill_name"),
                    "proficiency": arguments.get("proficiency", "")
                }
                
                # smart-add 엔드포인트 호출 (POST 요청)
                result = await fastapi_client.post_api(endpoint, skill_data, headers=headers)
                
                return ToolCallResponse(content=[
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False)
                    }
                ])
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"내 스킬 추가 실패: {str(e)}")
        elif tool_name == "get_my_certificates":
            try:
                certificates_data = await fastapi_client.call_api(endpoint, headers=headers)
                return ToolCallResponse(content=[
                    {
                        "type": "text",
                        "text": json.dumps(certificates_data, ensure_ascii=False)
                    }
                ])
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"내 자격증 조회 실패: {str(e)}")
        elif tool_name == "add_my_certificates":
            try:
                arguments = request.arguments
                certificate_data = {
                    "certificate_name": arguments.get("certificate_name"),
                    "acquired_date": arguments.get("acquired_date", "")
                }
                
                # smart-add 엔드포인트 호출 (POST 요청)
                result = await fastapi_client.post_api(endpoint, certificate_data, headers=headers)
                
                return ToolCallResponse(content=[
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False)
                    }
                ])
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"내 자격증 추가 실패: {str(e)}")
        elif tool_name == "update_my_skill_proficiency":
            try:
                arguments = request.arguments
                skill_name = arguments.get("skill_name")
                proficiency = arguments.get("proficiency")

                if not skill_name or not proficiency:
                    raise HTTPException(status_code=400, detail="skill_name과 proficiency 모두 필요합니다.")

                endpoint = "/users/me/skills/update-proficiency-by-name"
                result = await fastapi_client.put_api(endpoint, {"skill_name": skill_name, "proficiency": proficiency}, headers=headers)
                return ToolCallResponse(content=[
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False)
                    }
                ])
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"스킬 숙련도 업데이트 실패: {str(e)}")
        else:
            # GET 요청으로 처리
            # job_recommendation은 인증이 필요하고 쿼리 파라미터가 없음
            if tool_name == "job_recommendation":
                if not request.authorization:
                    return ToolCallResponse(content=[
                        {
                            "type": "text",
                            "text": json.dumps({
                                "error": "인증이 필요합니다",
                                "message": "job_recommendation 도구를 사용하려면 authorization 헤더에 Bearer 토큰을 포함해야 합니다.",
                                "example": {
                                    "name": "job_recommendation",
                                    "arguments": {},
                                    "authorization": "Bearer your_jwt_token_here"
                                }
                            }, ensure_ascii=False)
                        }
                    ])
                result = await fastapi_client.call_api(endpoint, None, headers=headers)
            else:
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
                "job_recommendation": "/recommend/jobs/ids",
                "gap_analysis": "/visualization/gap_analysis",
                "skill_search": "/visualization/skill_search",
                "roadmap_recommendations": "/visualization/roadmap_recommendations",
                "roadmap_recommendations_direct": "/visualization/roadmap_recommendations_direct",
                "resume_vs_job_skill_trend": "/visualization/resume_vs_job_skill_trend",
                "page_move": "/mcp/page-move",
                "get_my_skills": "/users/me/skills",
                "add_my_skills": "/users/me/skills/smart-add",
                "get_my_certificates": "/users/me/certificates",
                "add_my_certificates": "/users/me/certificates/smart-add",
                "update_my_skill_proficiency": "/users/me/skills/update-proficiency-by-name"
            }
            
            endpoint = endpoint_mapping.get(tool_name)
            if not endpoint:
                return MCPResponse(
                    error={"message": f"도구 '{tool_name}'에 대한 엔드포인트가 정의되지 않았습니다"},
                    id=request.id
                )
            
            # FastAPI 서버 호출 (인증이 필요한 엔드포인트는 헤더 전달)
            headers = {}
            if tool_name in ["job_recommendation", "get_my_resume", "gap_analysis", "roadmap_recommendations", "roadmap_recommendations_direct", "resume_vs_job_skill_trend", "get_my_skills", "add_my_skills", "get_my_certificates", "add_my_certificates", "update_my_skill_proficiency"]:
                # 인증이 필요한 엔드포인트는 authorization 헤더 필요
                # MCP 채팅에서는 인증 토큰을 별도로 받아야 함
                return MCPResponse(
                    error={"message": f"'{tool_name}' 도구는 인증이 필요합니다. /tools/{tool_name}/call 엔드포인트를 사용해주세요."},
                    id=request.id
                )
            
            api_result = await fastapi_client.call_api(endpoint, arguments, headers=headers)
            
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
                if isinstance(api_result, dict):
                    if "recommended_job" in api_result:
                        recommended_job = api_result["recommended_job"]
                        if recommended_job:
                            answer = f"추천 직무: {recommended_job}"
                        else:
                            answer = "현재 보유한 스킬로는 적합한 직무를 찾을 수 없습니다."
                    elif "recommendation" in api_result:
                        # 기존 형식도 지원
                        answer = clean_markdown_text(api_result["recommendation"])
                    else:
                        answer = "직무 추천을 받을 수 없습니다."
                else:
                    answer = "직무 추천을 받을 수 없습니다."
            elif tool_name == "page_move":
                if isinstance(api_result, dict) and "target_page" in api_result:
                    target_page = api_result["target_page"]
                    message = api_result.get("message", "")
                    answer = f"{message}\n\n이동할 페이지: {target_page}"
                else:
                    answer = "페이지 이동을 처리할 수 없습니다."
            elif tool_name == "get_my_skills":
                if isinstance(api_result, list):
                    skill_name = arguments.get("skill_name", "")
                    if skill_name and len(api_result) > 0:
                        answer = f"'{skill_name}' 스킬 정보를 찾았습니다."
                    elif skill_name and len(api_result) == 0:
                        answer = f"'{skill_name}' 스킬을 찾을 수 없습니다."
                    elif len(api_result) > 0:
                        answer = f"보유 스킬을 {len(api_result)}개 찾았습니다."
                    else:
                        answer = "보유 스킬이 없습니다."
                else:
                    answer = "보유 스킬을 조회할 수 없습니다."
            elif tool_name == "add_my_skills":
                if isinstance(api_result, dict) and "status" in api_result:
                    status = api_result["status"]
                    message = api_result["message"]
                    skill_name = api_result.get("skill_name")
                    proficiency = api_result.get("proficiency")
                    skill_id = api_result.get("skill_id")

                    if status == "success":
                        answer = f"'{skill_name}' 스킬을 추가했습니다. (ID: {skill_id})"
                    elif status == "duplicate":
                        answer = f"'{skill_name}'은(는) 이미 보유 중입니다."
                    elif status == "need_proficiency":
                        answer = f"'{proficiency}' 숙련도는 지원하지 않습니다. 초급, 중급, 고급 또는 1-5점 중 하나를 선택해주세요."
                    elif status == "skill_not_found":
                        answer = f"'{skill_name}' 스킬을 찾을 수 없습니다."
                    else:
                        answer = f"스킬 추가 실패: {message}"
                else:
                    answer = "스킬 추가를 처리할 수 없습니다."
            elif tool_name == "get_my_certificates":
                if isinstance(api_result, list) and len(api_result) > 0:
                    answer = f"보유 자격증을 {len(api_result)}개 찾았습니다."
                else:
                    answer = "보유 자격증이 없습니다."
            elif tool_name == "add_my_certificates":
                if isinstance(api_result, dict) and "status" in api_result:
                    status = api_result["status"]
                    message = api_result["message"]
                    certificate_name = api_result.get("certificate_name")
                    acquired_date = api_result.get("acquired_date")

                    if status == "success":
                        answer = f"'{certificate_name}' 자격증을 추가했습니다."
                    elif status == "duplicate":
                        answer = f"'{certificate_name}'은(는) 이미 보유 중입니다."
                    elif status == "need_acquired_date":
                        answer = f"'{certificate_name}' 자격증의 취득일을 입력해주세요."
                    elif status == "certificate_not_found":
                        answer = f"'{certificate_name}' 자격증을 찾을 수 없습니다."
                    else:
                        answer = f"자격증 추가 실패: {message}"
                else:
                    answer = "자격증 추가를 처리할 수 없습니다."
            elif tool_name == "update_my_skill_proficiency":
                if isinstance(api_result, dict) and "status" in api_result:
                    status = api_result["status"]
                    message = api_result["message"]
                    skill_name = api_result.get("skill_name")
                    old_proficiency = api_result.get("old_proficiency")
                    new_proficiency = api_result.get("new_proficiency")

                    if status == "success":
                        answer = f"'{skill_name}' 스킬의 숙련도가 '{old_proficiency}'에서 '{new_proficiency}'로 변경되었습니다."
                    else:
                        answer = f"스킬 숙련도 업데이트 실패: {message}"
                else:
                    answer = "스킬 숙련도 업데이트를 처리할 수 없습니다."
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
        "mcp_server:app",
        host=MCP_SERVER_HOST,
        port=MCP_SERVER_PORT,
        reload=True
    ) 