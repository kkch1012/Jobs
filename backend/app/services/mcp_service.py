from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from fastapi.concurrency import run_in_threadpool
from openai import OpenAI
from sqlalchemy.orm import Session
from app.config import settings
from app.models.mongo import MCPMessage
from app.schemas.mcp import MCPIntent, MCPContext

client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url=settings.OPENROUTER_BASE_URL,
)

class MCPService:
    """MCP(Model Context Protocol) 서비스 클래스"""
    
    def __init__(self):
        self.available_tools = [
            "/job_posts",
            "/certificates", 
            "/roadmaps",
            "/skills",
            "/visualizations",
            "/user_skills",
            "/user_certificates",
            "/user_profile",
            "/update_user_profile"
        ]
    
    async def analyze_intent(self, user_message: str, context: Optional[MCPContext] = None) -> Optional[MCPIntent]:
        """사용자 메시지의 의도를 분석합니다."""
        try:
            system_prompt = self._build_system_prompt(context)
            
            print(f"OpenAI API 호출 시작...")
            print(f"API Key: {settings.OPENROUTER_API_KEY[:10]}...")
            print(f"Base URL: {settings.OPENROUTER_BASE_URL}")
            print(f"Model: deepseek/deepseek-chat-v3-0324")
            
            response = await run_in_threadpool(
                client.chat.completions.create,
                model="deepseek/deepseek-chat-v3-0324",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            response_content = response.choices[0].message.content
            print(f"OpenAI API 응답 성공: {response_content}")
            
            # JSON 코드 블록에서 JSON 추출
            if response_content.startswith("```json"):
                response_content = response_content.replace("```json", "").replace("```", "").strip()
            elif response_content.startswith("```"):
                response_content = response_content.replace("```", "").strip()
            
            print(f"정제된 JSON: {response_content}")
            
            intent_data = json.loads(response_content)
            return MCPIntent(**intent_data)
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 실패: {e}")
            print(f"응답 내용: {response.choices[0].message.content if 'response' in locals() else '응답 없음'}")
            return None
        except Exception as e:
            print(f"Intent 분석 실패: {e}")
            print(f"에러 타입: {type(e).__name__}")
            # OpenAI API 에러인 경우 추가 정보 출력
            if hasattr(e, 'response') and e.response is not None:
                try:
                    print(f"API 응답: {e.response.text}")
                except:
                    print(f"API 응답: {e.response}")
            return None
    
    def _build_system_prompt(self, context: Optional[MCPContext] = None) -> str:
        """시스템 프롬프트를 구성합니다."""
        base_prompt = (
            "당신은 채용공고 플랫폼의 AI 도우미입니다. "
            "사용자의 요청을 분석하여 호출해야 할 FastAPI 라우터 경로와 파라미터를 추론하세요. "
            "결과는 반드시 JSON 형식으로 다음처럼 반환해야 합니다:\n"
            '{ "router": "/job_posts", "parameters": {} }\n\n'
            "반환 가능한 router 예시는 다음과 같습니다:\n"
        )
        
        for tool in self.available_tools:
            base_prompt += f"- {tool}: {self._get_tool_description(tool)}\n"
        
        base_prompt += "\n그 외 라우터는 지원하지 않습니다. JSON 외의 문장을 절대 출력하지 마세요."
        
        if context and context.conversation_history:
            base_prompt += "\n\n이전 대화 컨텍스트:\n"
            for msg in context.conversation_history[-3:]:  # 최근 3개 메시지만
                base_prompt += f"{msg['role']}: {msg['content']}\n"
        
        return base_prompt
    
    def _get_tool_description(self, tool: str) -> str:
        """도구별 설명을 반환합니다."""
        descriptions = {
            "/job_posts": "전체 채용공고 목록을 조회합니다.",
            "/certificates": "자격증 목록을 조회합니다.",
            "/roadmaps": "취업 로드맵을 조회합니다.",
            "/skills": "기술 스택 목록을 조회합니다.",
            "/visualizations": "데이터 시각화를 요청합니다.",
            "/user_skills": "사용자 기술 정보를 조회합니다. (로그인 필요)",
            "/user_certificates": "사용자 자격증 정보를 조회합니다. (로그인 필요)",
            "/user_profile": "사용자 프로필 정보를 조회합니다. (로그인 필요)",
            "/update_user_profile": "사용자 프로필 정보를 수정합니다. (로그인 필요, parameters에 수정할 필드와 값 포함)"
        }
        return descriptions.get(tool, "지원하지 않는 도구입니다.")
    
    async def save_message(self, session_id: str, role: str, content: str, 
                          intent: Optional[Dict[str, Any] | list | None] = None,
                          tool_calls: Optional[List] = None,
                          tool_results: Optional[List] = None) -> MCPMessage:
        """메시지를 저장합니다."""
        message = MCPMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.utcnow(),
            intent=intent,
            tool_calls=tool_calls,
            tool_results=tool_results
        )
        await message.insert()
        return message
    
    async def get_conversation_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """대화 히스토리를 조회합니다."""
        messages = await MCPMessage.find(
            MCPMessage.session_id == session_id
        ).sort("+created_at").limit(limit).to_list()
        
        # MCPMessage 객체를 딕셔너리로 변환
        history = []
        for msg in messages:
            history.append({
                "id": str(msg.id),
                "session_id": msg.session_id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at
            })
        return history
    
    async def summarize_response(self, original_message: str, api_result: Optional[Dict[str, Any] | list]) -> str:
        """API 결과를 자연스러운 응답으로 요약합니다."""
        if api_result is None:
            response = await run_in_threadpool(
                client.chat.completions.create,
                model="deepseek/deepseek-chat-v3-0324",
                messages=[
                    {"role": "user", "content": original_message}
                ]
            )
            return response.choices[0].message.content.strip()

        # SQLAlchemy 객체를 딕셔너리로 변환
        serializable_result = self._convert_to_serializable(api_result)

        system_prompt = """다음 데이터를 사용자에게 자연스럽게 설명해 주세요.\n\n응답 작성 규칙:\n- 마크다운, 특수문자, 이모지, 줄바꿈, 강조, 리스트, 표, 코드블록 등 일체 사용 금지\n- 오직 순수한 한글/영문/숫자만 사용\n- 한 문단의 자연스러운 설명으로만 작성\n- 불필요한 장식이나 강조 표시 제거\n- 핵심 정보만 간결하게 전달\n- 친근하지만 전문적인 톤 유지\n- 프론트엔드에서 쉽게 처리할 수 있도록 작성"""

        response = await run_in_threadpool(
            client.chat.completions.create,
            model="deepseek/deepseek-chat-v3-0324",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(serializable_result, ensure_ascii=False)}
            ],
            temperature=0.3
        )
        
        # 응답 후처리: 특수문자 제거
        content = response.choices[0].message.content.strip()
        content = self._clean_response_text(content)
        return content
    
    def _convert_to_serializable(self, obj: Any) -> Any:
        """SQLAlchemy 객체를 JSON 직렬화 가능한 형태로 변환합니다."""
        if obj is None:
            return None
        elif isinstance(obj, dict):
            return {key: self._convert_to_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__') and hasattr(obj, '_sa_instance_state'):
            # SQLAlchemy 모델 객체인 경우
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):
                    result[key] = self._convert_to_serializable(value)
            return result
        elif hasattr(obj, 'isoformat'):  # datetime 객체
            return obj.isoformat()
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        else:
            return str(obj)
    
    def _clean_response_text(self, text: str) -> str:
        """응답 텍스트에서 특수문자, 마크다운, 이모지, 줄바꿈, 리스트, 헤더, 코드블록, 연속공백 모두 제거"""
        import re
        # 마크다운 볼드/이탤릭/헤더/리스트/코드블록/줄바꿈 등 모두 제거
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **볼드**
        text = re.sub(r'\*(.*?)\*', r'\1', text)        # *이탤릭*
        text = re.sub(r'`+', '', text)                     # `코드`
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)  # # 헤더
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)  # 리스트
        text = re.sub(r'\n|\r|\r\n', ' ', text)         # 줄바꿈
        text = re.sub(r'\s+', ' ', text)                  # 연속 공백
        text = re.sub(r'[^\u0020-\u007E\uAC00-\uD7A3]', '', text)  # 이모지 등 특수문자
        return text.strip()

# 전역 MCP 서비스 인스턴스
mcp_service = MCPService() 