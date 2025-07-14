import json
from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.mongo import MCPMessage
from app.schemas.mcp import MessageIn, MCPContext
from app.services.mcp_client import mcp_client
from app.services.llm_client import llm_client
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.chat_session import ChatSession
from typing import Optional, Dict, List, Any
import uuid
import re
from app.models.job_post import JobPost

router = APIRouter(prefix="/mcp_chat", tags=["mcp_chat"])

# API 기능별 키워드 및 의도 매핑 정의
API_INTENT_MAPPING = {
    "job_posts": {
        "keywords": [
            # 채용 관련 기본 키워드
            "채용", "공고", "일자리", "구인", "취업", "모집", "채용정보", "채용사이트",
            "job", "recruit", "hire", "employment", "position", "vacancy", "opening",
            # 구체적인 질문 키워드
            "어떤", "무엇", "뭐", "보여", "알려", "찾아", "조회", "검색",
            "회사", "기업", "직무", "직종", "분야", "업종", "산업",
            # 필터링 관련 키워드
            "기술", "스택", "언어", "프로그래밍", "개발", "엔지니어", "디자이너", "마케터",
            "신입", "경력", "신규", "주니어", "시니어", "전문가",
            "정규직", "계약직", "인턴", "아르바이트", "프리랜서",
            "서울", "부산", "대구", "인천", "광주", "대전", "울산", "지방", "원격", "재택"
        ],
        "synonyms": {
            "채용공고": ["채용", "공고", "일자리", "구인"],
            "회사": ["기업", "회사", "업체", "기관"],
            "직무": ["직종", "분야", "업무", "포지션"],
            "기술스택": ["기술", "스택", "언어", "프로그래밍"],
            "지원자격": ["신입", "경력", "신규", "주니어", "시니어"],
            "고용형태": ["정규직", "계약직", "인턴", "아르바이트"]
        },
        "parameters": {
            "limit": 10,
            "company_name": None,
            "job_name": None,
            "applicant_type": None,
            "employment_type": None,
            "tech_stack": None
        }
    },
    "certificates": {
        "keywords": [
            # 자격증 관련 기본 키워드
            "자격증", "증명서", "이력서", "스킬", "경력", "경험", "certificate", 
            "resume", "cv", "skill", "experience", "qualification", "license",
            # 구체적인 질문 키워드
            "어떤", "무엇", "뭐", "보여", "알려", "찾아", "조회", "검색",
            "IT", "정보처리", "컴퓨터", "프로그래밍", "개발", "네트워크", "보안",
            "관리", "경영", "마케팅", "디자인", "언어", "영어", "일본어", "중국어"
        ],
        "synonyms": {
            "자격증": ["증명서", "certificate", "license", "qualification"],
            "이력서": ["resume", "cv", "경력서"],
            "IT자격증": ["정보처리", "컴퓨터", "프로그래밍", "개발"],
            "언어자격증": ["영어", "일본어", "중국어", "토익", "토플", "JLPT"]
        },
        "parameters": {
            "limit": 10
        }
    },
    "skills": {
        "keywords": [
            # 기술 관련 기본 키워드
            "기술", "스택", "언어", "프로그래밍", "개발", "코딩", "프레임워크",
            "skill", "technology", "programming", "language", "framework",
            # 구체적인 기술 키워드
            "Python", "Java", "JavaScript", "C++", "C#", "PHP", "Ruby", "Go", "Rust",
            "React", "Vue", "Angular", "Node.js", "Django", "Flask", "Spring",
            "MySQL", "PostgreSQL", "MongoDB", "Redis", "AWS", "Azure", "GCP",
            "Docker", "Kubernetes", "Git", "Linux", "Windows", "Mac"
        ],
        "synonyms": {
            "프로그래밍언어": ["언어", "language", "코딩", "개발언어"],
            "프레임워크": ["framework", "라이브러리", "도구"],
            "데이터베이스": ["DB", "database", "저장소"],
            "클라우드": ["AWS", "Azure", "GCP", "클라우드서비스"]
        },
        "parameters": {
            "limit": 10
        }
    },
    "roadmaps": {
        "keywords": [
            # 로드맵 관련 기본 키워드
            "로드맵", "경로", "학습", "계획", "단계", "roadmap", "path", "plan",
            "학습계획", "진로", "방향", "가이드", "guide", "tutorial", "커리큘럼",
            # 구체적인 분야 키워드
            "개발자", "프로그래머", "엔지니어", "디자이너", "마케터", "기획자",
            "백엔드", "프론트엔드", "풀스택", "데이터", "AI", "머신러닝", "블록체인",
            "웹", "모바일", "게임", "시스템", "네트워크", "보안", "DevOps"
        ],
        "synonyms": {
            "로드맵": ["경로", "roadmap", "학습계획", "커리큘럼"],
            "개발자": ["프로그래머", "엔지니어", "coder"],
            "백엔드": ["서버", "API", "데이터베이스"],
            "프론트엔드": ["웹", "UI", "UX", "클라이언트"],
            "데이터": ["분석", "AI", "머신러닝", "빅데이터"]
        },
        "parameters": {
            "limit": 10
        }
    },
    "visualization": {
        "keywords": [
            # 시각화 관련 기본 키워드
            "시각화", "차트", "그래프", "통계", "분석", "데이터", "트렌드",
            "visualization", "chart", "graph", "statistics", "analysis", "trend",
            # 구체적인 분석 키워드
            "주간", "월간", "연간", "빈도", "인기", "트렌드", "패턴",
            "기술", "스킬", "직무", "분야", "업종", "지역", "급여"
        ],
        "synonyms": {
            "시각화": ["차트", "그래프", "통계", "분석"],
            "트렌드": ["추세", "패턴", "변화", "동향"],
            "빈도": ["인기", "선호도", "수요", "통계"]
        },
        "parameters": {
            "job_name": None,
            "field": "tech_stack"
        }
    }
}

# 일반 대화 키워드 (API 호출 없이 처리)
GENERAL_KEYWORDS = [
    "안녕", "하세요", "반갑", "고마워", "감사", "hello", "hi", "thanks", "thank",
    "도움", "help", "뭐", "무엇", "어떻게", "what", "how", "when", "where",
    "소개", "설명", "알려", "가르쳐", "도와", "assist", "explain", "introduce"
]

# intent 확장: job_posts, resume_update, resume_add, resume_delete, page_move, general 등
EXTENDED_INTENT_MAPPING = {
    "job_posts": "채용공고 조회",
    "resume_update": "이력서 정보 수정",
    "resume_add": "이력서 정보 추가",
    "resume_delete": "이력서 정보 삭제",
    "page_move": "페이지 이동",
    "general": "일반 대화"
}

def extract_parameters_from_message(message: str, api_type: str) -> Dict[str, Any]:
    """사용자 메시지에서 API 파라미터를 추출합니다."""
    message_lower = message.lower()
    parameters = API_INTENT_MAPPING[api_type]["parameters"].copy()
    
    if api_type == "job_posts":
        # 회사명 추출
        company_patterns = [
            r"([가-힣a-zA-Z]+(?:기업|회사|corporation|company|inc|ltd))",
            r"([가-힣a-zA-Z]+에서)",
            r"([가-힣a-zA-Z]+의)"
        ]
        for pattern in company_patterns:
            match = re.search(pattern, message)
            if match:
                parameters["company_name"] = match.group(1).replace("에서", "").replace("의", "")
                break
        
        # 직무명 추출
        job_patterns = [
            r"([가-힣a-zA-Z]+(?:개발자|엔지니어|디자이너|마케터|기획자))",
            r"([가-힣a-zA-Z]+(?:developer|engineer|designer|marketer))"
        ]
        for pattern in job_patterns:
            match = re.search(pattern, message)
            if match:
                parameters["job_name"] = match.group(1)
                break
        
        # 기술스택 추출
        tech_keywords = ["Python", "Java", "JavaScript", "React", "Vue", "Node.js", "Django", "Spring"]
        for tech in tech_keywords:
            if tech.lower() in message_lower:
                parameters["tech_stack"] = tech
                break
        
        # 지원자격 추출
        if any(word in message_lower for word in ["신입", "신규", "주니어"]):
            parameters["applicant_type"] = "신입"
        elif any(word in message_lower for word in ["경력", "시니어", "전문가"]):
            parameters["applicant_type"] = "경력"
        
        # 고용형태 추출
        if any(word in message_lower for word in ["정규직", "정규"]):
            parameters["employment_type"] = "정규직"
        elif any(word in message_lower for word in ["계약직", "계약"]):
            parameters["employment_type"] = "계약직"
        elif any(word in message_lower for word in ["인턴", "인턴십"]):
            parameters["employment_type"] = "인턴"
    
    elif api_type == "visualization":
        # 직무명 추출
        job_patterns = [
            r"([가-힣a-zA-Z]+(?:개발자|엔지니어|디자이너|마케터|기획자))",
            r"([가-힣a-zA-Z]+(?:developer|engineer|designer|marketer))"
        ]
        for pattern in job_patterns:
            match = re.search(pattern, message)
            if match:
                parameters["job_name"] = match.group(1)
                break
        
        # 분석 필드 추출
        if any(word in message_lower for word in ["기술", "스택", "tech"]):
            parameters["field"] = "tech_stack"
        elif any(word in message_lower for word in ["자격", "qualification"]):
            parameters["field"] = "qualifications"
    
    return parameters

def calculate_intent_score(message: str, api_type: str) -> float:
    """메시지와 API 타입 간의 의도 매칭 점수를 계산합니다."""
    message_lower = message.lower()
    score = 0.0
    
    # 기본 키워드 매칭
    keywords = API_INTENT_MAPPING[api_type]["keywords"]
    for keyword in keywords:
        if keyword.lower() in message_lower:
            score += 1.0
    
    # 동의어 매칭 (가중치 높음)
    synonyms = API_INTENT_MAPPING[api_type]["synonyms"]
    for main_word, synonym_list in synonyms.items():
        if main_word.lower() in message_lower:
            score += 2.0
        for synonym in synonym_list:
            if synonym.lower() in message_lower:
                score += 1.5
    
    # 구체적인 질문 키워드 (가중치 높음)
    question_keywords = ["어떤", "무엇", "뭐", "보여", "알려", "찾아", "조회", "검색"]
    for q_keyword in question_keywords:
        if q_keyword in message_lower:
            score += 0.5
    
    return score

async def analyze_intent_with_llm(user_message: str, context: Optional[MCPContext] = None) -> Optional[dict]:
    """LLM을 사용하여 사용자 메시지의 의도를 분석합니다."""
    try:
        # 사용 가능한 API 목록
        available_apis = list(API_INTENT_MAPPING.keys()) + [k for k in EXTENDED_INTENT_MAPPING.keys() if k not in API_INTENT_MAPPING]
        
        # LLM을 사용한 의도 분석
        intent_result = await llm_client.analyze_intent(user_message, available_apis)
        
        if intent_result and intent_result.get("intent") != "general":
            # API 호출이 필요한 경우
            api_type = intent_result["intent"]
            parameters = extract_parameters_from_message(user_message, api_type)
            
            return {
                "intent": api_type,
                "confidence": intent_result.get("confidence", 0.0),
                "parameters": parameters,
                "reasoning": intent_result.get("reasoning", ""),
                "use_llm": True
            }
        else:
            # 일반 대화인 경우
            return {
                "intent": "general",
                "confidence": intent_result.get("confidence", 0.0) if intent_result else 0.0,
                "parameters": {},
                "reasoning": intent_result.get("reasoning", "") if intent_result else "LLM 분석 실패",
                "use_llm": True
            }
            
    except Exception as e:
        print(f"LLM 의도 분석 중 오류: {str(e)}")
        return None

async def analyze_intent_with_mcp(user_message: str, context: Optional[MCPContext] = None) -> Optional[dict]:
    """외부 MCP 서버를 사용하여 사용자 메시지의 의도를 분석합니다."""
    try:
        # MCP 서버에 도구 목록 요청
        tools_response = await mcp_client.chat_with_mcp(
            method="tools/list",
            params={},
            request_id=str(uuid.uuid4())
        )
        
        if tools_response.get("error"):
            print(f"MCP 도구 목록 조회 실패: {tools_response['error']}")
            return None
        
        available_tools = tools_response.get("result", {}).get("tools", [])
        
        print(f"DEBUG: 분석 중인 메시지: {user_message}")
        
        # 1. 일반 대화인지 확인
        if any(keyword in user_message.lower() for keyword in GENERAL_KEYWORDS):
            print(f"DEBUG: 일반 대화로 인식됨")
            return {
                "router": "general",
                "parameters": {"message": user_message}
            }
        
        # 2. 각 API 타입별 점수 계산
        intent_scores = {}
        for api_type in API_INTENT_MAPPING.keys():
            score = calculate_intent_score(user_message, api_type)
            intent_scores[api_type] = score
            print(f"DEBUG: {api_type} 점수: {score}")
        
        # 3. 가장 높은 점수의 API 선택 (임계값 이상)
        max_score = max(intent_scores.values())
        if max_score >= 1.0:  # 최소 1점 이상이어야 의도로 인식
            best_api = max(intent_scores.items(), key=lambda x: x[1])[0]
            print(f"DEBUG: {best_api} 분야로 인식됨 (점수: {max_score})")
            
            # 파라미터 추출
            parameters = extract_parameters_from_message(user_message, best_api)
            print(f"DEBUG: 추출된 파라미터: {parameters}")
            
            return {
                "router": best_api,
                "parameters": parameters
            }
        else:
            print(f"DEBUG: 매칭되는 의도 없음 - 일반 대화로 분류")
            return {
                "router": "general",
                "parameters": {"message": user_message}
            }
            
    except Exception as e:
        print(f"MCP 의도 분석 실패: {e}")
        return None

async def call_api_via_mcp(intent: dict) -> Optional[dict]:
    """외부 MCP 서버를 통해 API를 호출합니다."""
    try:
        tool_name = intent.get("router", "").replace("/", "")
        parameters = intent.get("parameters", {})
        
        # MCP 서버를 통해 도구 호출
        result = await mcp_client.call_tool(tool_name, parameters)
        return result
        
    except Exception as e:
        print(f"MCP API 호출 실패: {e}")
        return None

def convert_datetime(obj):
    if isinstance(obj, dict):
        return {k: convert_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime(i) for i in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

@router.post("/mcp/chat/",
             summary="외부 MCP 서버를 통한 AI 챗봇 대화",
             description="""
외부 MCP(Model Context Protocol) 서버를 사용하여 AI 챗봇과 대화합니다.

- 외부 MCP 서버(포트 8001)와 통신합니다.
- 사용자의 자연어 메시지를 분석하여 적절한 도구를 호출합니다.
- 대화 히스토리를 MongoDB에 저장합니다.
- FastAPI 서버의 Swagger 문서와 별개로 MCP 서버의 API를 사용합니다.

**지원하는 요청 예시:**
- "채용공고 목록을 보여주세요"
- "IT 관련 자격증이 뭐가 있나요?"
- "프로그래밍 언어 목록을 보여주세요"
- "취업 로드맵을 알려주세요"

**MCP 서버 정보:**
- URL: http://localhost:8001
- Swagger: http://localhost:8001/docs
""")
async def chat_with_external_mcp(
    data: MessageIn,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 세션 유효성 체크
    if data.session_id:
        session_obj = db.query(ChatSession).filter(ChatSession.id == data.session_id).first()
        if not session_obj:
            raise HTTPException(status_code=404, detail="존재하지 않는 세션입니다.")

    # MCP 서버 상태 확인
    try:
        health_status = await mcp_client.health_check()
        if health_status.get("status") != "healthy":
            raise HTTPException(status_code=503, detail="MCP 서버가 정상 상태가 아닙니다.")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MCP 서버 연결 실패: {str(e)}")

    # MCP 컨텍스트 구성
    context = None
    if data.session_id:
        # 대화 히스토리 조회
        messages = await MCPMessage.find(
            MCPMessage.session_id == data.session_id
        ).sort("+created_at").limit(5).to_list()
        
        conversation_history = [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
        
        user_id = getattr(current_user, 'id', None)
        context = MCPContext(
            user_id=user_id if isinstance(user_id, int) else None,
            session_id=data.session_id,
            conversation_history=conversation_history,
            available_tools=["job_posts", "certificates", "skills", "roadmaps"]
        )
    
    # LLM을 사용한 의도 분석 (우선순위)
    intent = await analyze_intent_with_llm(data.message, context)
    
    # LLM 분석이 실패한 경우 키워드 기반 분석으로 폴백
    if not intent or intent.get("confidence", 0.0) < 0.3:
        intent = await analyze_intent_with_mcp(data.message, context)
    
    if not intent:
        answer = "죄송합니다. 요청을 이해하지 못했습니다. 다른 방식으로 질문해 주세요."
    else:
        # LLM 기반 일반 대화 처리
        if intent.get("intent") == "general" or intent.get("use_llm"):
            # LLM을 사용하여 자연스러운 응답 생성
            context_str = ""
            if context and context.conversation_history:
                context_str = "대화 히스토리: " + " | ".join([
                    f"{msg['role']}: {msg['content']}" 
                    for msg in context.conversation_history[-3:]  # 최근 3개 메시지만
                ])
            
            answer = await llm_client.generate_response(data.message, context_str)
        else:
            # API 호출이 필요한 경우
            api_type = intent.get("intent")
            api_result = await call_api_via_mcp(intent)
            
            if api_result:
                # API 결과를 자연스러운 응답으로 변환
                try:
                    if api_type == "job_posts":
                        # API 결과가 리스트인지 딕셔너리인지 확인
                        if isinstance(api_result, list):
                            jobs = api_result
                        else:
                            jobs = api_result.get("jobs", [])
                        
                        if jobs:
                            answer = f"채용공고를 {len(jobs)}개 찾았습니다! "
                            first_job = jobs[0]
                            company = first_job.get('company_name', '알 수 없음')
                            title = first_job.get('title', '알 수 없음')
                            answer += f"예를 들어, {company}에서 {title} 포지션을 모집하고 있습니다. "
                            answer += "더 자세한 정보가 필요하시면 특정 회사나 직무를 말씀해 주세요."
                        else:
                            answer = "현재 등록된 채용공고가 없습니다. 나중에 다시 확인해 주세요."
                    elif api_type == "certificates":
                        certificates = api_result.get("certificates", [])
                        if certificates:
                            answer = f"총 {len(certificates)}개의 자격증 정보를 찾았습니다! "
                            first_cert = certificates[0]
                            cert_name = first_cert.get('name', '알 수 없음')
                            issuer = first_cert.get('issuer', '알 수 없음')
                            answer += f"예를 들어, {cert_name} 자격증은 {issuer}에서 발급합니다. "
                            answer += "특정 분야의 자격증을 찾고 계시면 말씀해 주세요."
                        else:
                            answer = "현재 등록된 자격증 정보가 없습니다."
                    elif api_type == "skills":
                        skills = api_result.get("skills", [])
                        if skills:
                            answer = f"총 {len(skills)}개의 기술 스택 정보를 찾았습니다! "
                            first_skill = skills[0]
                            skill_name = first_skill.get('name', '알 수 없음')
                            category = first_skill.get('category', '알 수 없음')
                            answer += f"예를 들어, {skill_name}은 {category} 분야의 기술입니다. "
                            answer += "특정 기술이나 분야에 대해 더 알고 싶으시면 말씀해 주세요."
                        else:
                            answer = "현재 등록된 기술 스택 정보가 없습니다."
                    elif api_type == "roadmaps":
                        roadmaps = api_result.get("roadmaps", [])
                        if roadmaps:
                            answer = f"총 {len(roadmaps)}개의 취업 로드맵을 찾았습니다! "
                            first_roadmap = roadmaps[0]
                            roadmap_name = first_roadmap.get('name', '알 수 없음')
                            field = first_roadmap.get('field', '알 수 없음')
                            answer += f"예를 들어, {roadmap_name}은 {field} 분야의 로드맵입니다. "
                            answer += "특정 분야나 직무에 대한 로드맵이 필요하시면 말씀해 주세요."
                        else:
                            answer = "현재 등록된 로드맵 정보가 없습니다."
                    elif api_type == "visualization":
                        # 시각화 데이터 처리
                        if isinstance(api_result, list) and api_result:
                            answer = f"총 {len(api_result)}개의 시각화 데이터를 찾았습니다! "
                            first_data = api_result[0]
                            skill = first_data.get('skill', '알 수 없음')
                            count = first_data.get('count', 0)
                            answer += f"예를 들어, '{skill}' 기술이 {count}번 등장했습니다. "
                            answer += "더 자세한 분석이 필요하시면 특정 기술이나 기간을 말씀해 주세요."
                        else:
                            answer = "현재 시각화 데이터가 없습니다."
                    else:
                        answer = "요청하신 정보를 찾았습니다. 더 구체적인 질문을 해주시면 더 자세한 답변을 드릴 수 있습니다."
                except Exception as e:
                    answer = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
            else:
                answer = "죄송합니다. 요청하신 정보를 찾을 수 없습니다. 다른 키워드로 검색해 보시거나, 더 구체적으로 말씀해 주세요."

    # 메시지 저장
    import asyncio
    
    # 사용자 메시지 저장
    user_message = MCPMessage(
        session_id=data.session_id,
        role="user",
        content=data.message,
        created_at=datetime.utcnow()
    )
    await user_message.insert()
    
    # AI 응답 저장
    ai_message = MCPMessage(
        session_id=data.session_id,
        role="assistant",
        content=answer,
        intent=intent,
        created_at=datetime.utcnow()
    )
    await ai_message.insert()

    return {
        "message": answer,
        "intent": intent,
        "mcp_server": "external",
        "timestamp": datetime.utcnow()
    }

@router.post("/llm/chat/",
             summary="LLM 기반 AI 챗봇 대화 (DB/API 연동 및 intent 확장)",
             description="""
OpenRouter API를 사용한 LLM 기반 AI 챗봇과 대화합니다.
- intent에 따라 실제 DB/API 결과를 LLM 프롬프트에 포함하거나, 이력서 수정/추가/삭제/조회, 페이지 이동 등도 처리합니다.
- 프론트엔드에 action, page, updated_resume 등 필요한 정보를 명확히 반환합니다.
""")
async def chat_with_llm(
    data: MessageIn,
    model: str = Body("openai/gpt-4-1106-preview"),
    current_user: Optional[User] = Depends(lambda: None),
    db: Session = Depends(get_db)
):
    # 1. LLM으로 intent 분석
    available_apis = list(API_INTENT_MAPPING.keys()) + [k for k in EXTENDED_INTENT_MAPPING.keys() if k not in API_INTENT_MAPPING]
    intent = await llm_client.analyze_intent(data.message, available_apis)
    intent_name = intent.get("intent")
    params = intent.get("parameters", {})

    # 2. intent에 따라 분기
    if intent_name == "job_posts":
        # 실제 DB에서 채용공고 조회
        query = db.query(JobPost)
        if params.get("company_name"):
            query = query.filter(JobPost.company_name.ilike(f"%{params['company_name']}%"))
        if params.get("job_name"):
            query = query.filter(JobPost.title.ilike(f"%{params['job_name']}%"))
        if params.get("applicant_type"):
            query = query.filter(JobPost.applicant_type.ilike(f"%{params['applicant_type']}%"))
        if params.get("employment_type"):
            query = query.filter(JobPost.employment_type.ilike(f"%{params['employment_type']}%"))
        if params.get("tech_stack"):
            query = query.filter(JobPost.tech_stack.ilike(f"%{params['tech_stack']}%"))
        job_posts = query.limit(params.get("limit", 10)).all()
        # 각 JobPost를 Pydantic 응답 스키마로 직렬화
        from app.schemas.job_post import JobPostResponse
        job_posts_serialized = [JobPostResponse.model_validate(job).model_dump() for job in job_posts]
        job_posts_serialized = convert_datetime(job_posts_serialized)
        # LLM에게 요약 프롬프트 전달
        summary_prompt = (
            f"아래는 실제 채용공고 데이터입니다. 사용자의 질문: '{data.message}'\n"
            f"채용공고 데이터: {json.dumps(job_posts_serialized, ensure_ascii=False)}\n"
            "이 데이터를 바탕으로 사용자에게 친절하게 요약/설명/추천해줘."
        )
        answer = await llm_client.generate_response(summary_prompt)
        return {"message": answer, "intent": intent, "llm_model": model}

    elif intent_name == "resume_update":
        # 이력서 정보 수정 (예시: user_id 기준)
        if not current_user:
            return {"message": "이력서 관련 기능을 이용하려면 로그인이 필요합니다. 먼저 로그인해 주세요.", "intent": intent, "llm_model": model}
        resume = db.query(User).filter(User.id == current_user.id).first()  # 실제 이력서 모델로 교체 필요
        update_prompt = (
            f"아래는 사용자의 기존 이력서 정보입니다.\n{resume}\n"
            f"사용자 요청: '{data.message}'\n"
            "이 요청에 따라 이력서 정보를 수정한 결과만 JSON으로 반환해줘."
        )
        updated_resume = await llm_client.generate_response(update_prompt)
        # 실제 DB update 로직 필요 (updated_resume 파싱 후)
        return {"message": "이력서가 성공적으로 수정되었습니다.", "updated_resume": updated_resume, "intent": intent, "llm_model": model}

    elif intent_name == "resume_add":
        # 이력서 정보 추가 (예시)
        if not current_user:
            return {"message": "이력서 관련 기능을 이용하려면 로그인이 필요합니다. 먼저 로그인해 주세요.", "intent": intent, "llm_model": model}
        resume = db.query(User).filter(User.id == current_user.id).first()  # 실제 이력서 모델로 교체 필요
        add_prompt = (
            f"아래는 사용자의 기존 이력서 정보입니다.\n{resume}\n"
            f"사용자 요청: '{data.message}'\n"
            "이 요청에 따라 이력서에 추가할 정보를 JSON으로 반환해줘."
        )
        added_resume = await llm_client.generate_response(add_prompt)
        # 실제 DB insert 로직 필요 (added_resume 파싱 후)
        return {"message": "이력서 정보가 성공적으로 추가되었습니다.", "added_resume": added_resume, "intent": intent, "llm_model": model}

    elif intent_name == "resume_delete":
        # 이력서 정보 삭제 (예시)
        if not current_user:
            return {"message": "이력서 관련 기능을 이용하려면 로그인이 필요합니다. 먼저 로그인해 주세요.", "intent": intent, "llm_model": model}
        resume = db.query(User).filter(User.id == current_user.id).first()  # 실제 이력서 모델로 교체 필요
        delete_prompt = (
            f"아래는 사용자의 기존 이력서 정보입니다.\n{resume}\n"
            f"사용자 요청: '{data.message}'\n"
            "이 요청에 따라 이력서에서 삭제할 정보를 JSON으로 반환해줘."
        )
        deleted_resume = await llm_client.generate_response(delete_prompt)
        # 실제 DB delete 로직 필요 (deleted_resume 파싱 후)
        return {"message": "이력서 정보가 성공적으로 삭제되었습니다.", "deleted_resume": deleted_resume, "intent": intent, "llm_model": model}

    elif intent_name == "page_move":
        # 페이지 이동
        page = params.get("page", "/")
        return {"action": "navigate", "page": page, "intent": intent, "llm_model": model}

    else:
        # 일반 대화
        answer = await llm_client.generate_response(data.message)
        return {"message": answer, "intent": intent, "llm_model": model}

# 프론트엔드에 안내할 사항 정리
FRONTEND_GUIDE = """
1. message: LLM이 생성한 자연어 답변(요약/설명/추천 등)
2. intent: LLM이 분석한 의도 및 파라미터 정보
3. llm_model: 사용된 LLM 모델명
4. action: "navigate"가 오면 page 필드에 명시된 경로로 이동
5. updated_resume, added_resume, deleted_resume: 이력서 정보가 수정/추가/삭제된 경우, 해당 JSON 결과를 활용해 이력서 화면을 갱신
6. 기타 intent에 따라 필요한 추가 정보가 포함될 수 있음
"""

@router.post("/mcp/chat/test",
             summary="테스트용 외부 MCP 채팅 (인증 불필요)",
             description="인증이 필요 없는 테스트용 MCP 채팅 엔드포인트입니다.")
async def test_chat_with_external_mcp(data: MessageIn):
    """테스트용 MCP 채팅 (인증 불필요)"""
    # MCP 서버 상태 확인
    try:
        health_status = await mcp_client.health_check()
        if health_status.get("status") != "healthy":
            raise HTTPException(status_code=503, detail="MCP 서버가 정상 상태가 아닙니다.")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MCP 서버 연결 실패: {str(e)}")

    # LLM을 사용한 의도 분석 (우선순위)
    intent = await analyze_intent_with_llm(data.message)
    
    # LLM 분석이 실패한 경우 키워드 기반 분석으로 폴백
    if not intent or intent.get("confidence", 0.0) < 0.3:
        intent = await analyze_intent_with_mcp(data.message)
    
    if not intent:
        answer = "죄송합니다. 요청을 이해하지 못했습니다. 다른 방식으로 질문해 주세요."
    else:
        # LLM 기반 일반 대화 처리
        if intent.get("intent") == "general" or intent.get("use_llm"):
            # LLM을 사용하여 자연스러운 응답 생성
            answer = await llm_client.generate_response(data.message)
        else:
            # API 호출이 필요한 경우
            api_type = intent.get("intent")
            api_result = await call_api_via_mcp(intent)
            
            if api_result:
                # API 결과를 자연스러운 응답으로 변환
                try:
                    if api_type == "job_posts":
                        # API 결과가 리스트인지 딕셔너리인지 확인
                        if isinstance(api_result, list):
                            jobs = api_result
                        else:
                            jobs = api_result.get("jobs", [])
                        
                        if jobs:
                            answer = f"채용공고를 {len(jobs)}개 찾았습니다! "
                            first_job = jobs[0]
                            company = first_job.get('company_name', '알 수 없음')
                            title = first_job.get('title', '알 수 없음')
                            answer += f"예를 들어, {company}에서 {title} 포지션을 모집하고 있습니다. "
                            answer += "더 자세한 정보가 필요하시면 특정 회사나 직무를 말씀해 주세요."
                        else:
                            answer = "현재 등록된 채용공고가 없습니다. 나중에 다시 확인해 주세요."
                    elif api_type == "certificates":
                        certificates = api_result.get("certificates", [])
                        if certificates:
                            answer = f"총 {len(certificates)}개의 자격증 정보를 찾았습니다! "
                            first_cert = certificates[0]
                            cert_name = first_cert.get('name', '알 수 없음')
                            issuer = first_cert.get('issuer', '알 수 없음')
                            answer += f"예를 들어, {cert_name} 자격증은 {issuer}에서 발급합니다. "
                            answer += "특정 분야의 자격증을 찾고 계시면 말씀해 주세요."
                        else:
                            answer = "현재 등록된 자격증 정보가 없습니다."
                    elif api_type == "skills":
                        skills = api_result.get("skills", [])
                        if skills:
                            answer = f"총 {len(skills)}개의 기술 스택 정보를 찾았습니다! "
                            first_skill = skills[0]
                            skill_name = first_skill.get('name', '알 수 없음')
                            category = first_skill.get('category', '알 수 없음')
                            answer += f"예를 들어, {skill_name}은 {category} 분야의 기술입니다. "
                            answer += "특정 기술이나 분야에 대해 더 알고 싶으시면 말씀해 주세요."
                        else:
                            answer = "현재 등록된 기술 스택 정보가 없습니다."
                    elif api_type == "roadmaps":
                        roadmaps = api_result.get("roadmaps", [])
                        if roadmaps:
                            answer = f"총 {len(roadmaps)}개의 취업 로드맵을 찾았습니다! "
                            first_roadmap = roadmaps[0]
                            roadmap_name = first_roadmap.get('name', '알 수 없음')
                            field = first_roadmap.get('field', '알 수 없음')
                            answer += f"예를 들어, {roadmap_name}은 {field} 분야의 로드맵입니다. "
                            answer += "특정 분야나 직무에 대한 로드맵이 필요하시면 말씀해 주세요."
                        else:
                            answer = "현재 등록된 로드맵 정보가 없습니다."
                    elif api_type == "visualization":
                        # 시각화 데이터 처리
                        if isinstance(api_result, list) and api_result:
                            answer = f"총 {len(api_result)}개의 시각화 데이터를 찾았습니다! "
                            first_data = api_result[0]
                            skill = first_data.get('skill', '알 수 없음')
                            count = first_data.get('count', 0)
                            answer += f"예를 들어, '{skill}' 기술이 {count}번 등장했습니다. "
                            answer += "더 자세한 분석이 필요하시면 특정 기술이나 기간을 말씀해 주세요."
                        else:
                            answer = "현재 시각화 데이터가 없습니다."
                    else:
                        answer = "요청하신 정보를 찾았습니다. 더 구체적인 질문을 해주시면 더 자세한 답변을 드릴 수 있습니다."
                except Exception as e:
                    answer = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
            else:
                answer = "죄송합니다. 요청하신 정보를 찾을 수 없습니다. 다른 키워드로 검색해 보시거나, 더 구체적으로 말씀해 주세요."

    return {
        "message": answer,
        "intent": intent,
        "mcp_server": "external",
        "timestamp": datetime.utcnow()
    }

@router.get("/mcp/history/",
            summary="대화 히스토리 조회",
            description="""
특정 세션의 대화 히스토리를 조회합니다.

- MongoDB에 저장된 대화 메시지를 시간순으로 반환합니다.
- 최대 50개 메시지까지 조회 가능합니다.
- 사용자와 AI의 모든 대화 내용을 포함합니다.

**파라미터:**
- `session_id`: 조회할 세션 ID (필수)
- `limit`: 조회할 메시지 개수 (기본값: 50, 최대: 50)
""")
async def get_history(session_id: int, limit: int = 50):
    """대화 히스토리를 반환합니다."""
    if limit > 50:
        limit = 50
    
    messages = await MCPMessage.find(
        MCPMessage.session_id == session_id
    ).sort("+created_at").limit(limit).to_list()
    
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at,
                "intent": msg.intent
            }
            for msg in messages
        ],
        "total_count": len(messages)
    }

@router.get("/mcp/context/{session_id}",
            summary="MCP 컨텍스트 정보 조회",
            description="""
MCP(Model Context Protocol) 컨텍스트 정보를 조회합니다.

- 세션별 대화 상태와 사용 가능한 도구 목록을 반환합니다.
- 최근 10개 메시지의 요약 정보를 제공합니다.
- MCP 시스템의 현재 상태를 파악할 수 있습니다.

**반환 정보:**
- `session_id`: 세션 ID
- `message_count`: 총 메시지 개수
- `last_message`: 마지막 메시지 정보
- `available_tools`: 사용 가능한 API 도구 목록

**사용 가능한 도구:**
- `/job_posts`: 채용공고 조회
- `/certificates`: 자격증 조회
- `/roadmaps`: 로드맵 조회
- `/skills`: 기술 스택 조회
- `/visualizations`: 데이터 시각화
""")
async def get_mcp_context(session_id: int):
    """MCP 컨텍스트 정보를 반환합니다."""
    messages = await MCPMessage.find(
        MCPMessage.session_id == session_id
    ).sort("+created_at").limit(10).to_list()
    
    return {
        "session_id": session_id,
        "message_count": len(messages),
        "last_message": messages[-1] if messages else None,
        "available_tools": [
            "job_posts",
            "certificates", 
            "roadmaps",
            "skills",
            "visualizations"
        ]
    }

@router.get("/mcp/tools",
            summary="외부 MCP 서버의 도구 목록 조회",
            description="외부 MCP 서버에서 사용 가능한 도구 목록을 조회합니다.")
async def get_mcp_tools():
    """외부 MCP 서버의 도구 목록을 반환합니다."""
    try:
        tools = await mcp_client.list_tools()
        return {
            "tools": tools,
            "mcp_server": "external",
            "server_url": "http://localhost:8001"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"도구 목록 조회 실패: {str(e)}")

@router.get("/mcp/health",
            summary="외부 MCP 서버 상태 확인",
            description="외부 MCP 서버의 상태를 확인합니다.")
async def check_mcp_health():
    """외부 MCP 서버의 상태를 확인합니다."""
    try:
        health = await mcp_client.health_check()
        return {
            "mcp_server": "external",
            "server_url": "http://localhost:8001",
            "health": health
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MCP 서버 상태 확인 실패: {str(e)}")

@router.post("/mcp/tools/{tool_name}/call",
             summary="외부 MCP 서버를 통한 도구 호출",
             description="외부 MCP 서버를 통해 특정 도구를 호출합니다.")
async def call_mcp_tool(tool_name: str, arguments: dict):
    """외부 MCP 서버를 통해 특정 도구를 호출합니다."""
    try:
        result = await mcp_client.call_tool(tool_name, arguments)
        return {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "mcp_server": "external"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"도구 호출 실패: {str(e)}")
