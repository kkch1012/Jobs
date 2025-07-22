import json
import re
from typing import Dict, List, Any, Optional
from app.config import settings
import logging
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
import anyio.to_thread
from app.utils.text_utils import clean_markdown_text

logger = logging.getLogger(__name__)

class OpenRouterClient:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    async def chat_completion(
        self,
        messages: List[ChatCompletionMessageParam],
        model: str = "qwen/qwen-vl-max",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        extra_headers: dict = {},
        extra_body: dict = {},
    ) -> Optional[str]:
        headers = {
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "JOBS MCP Chat"
        }
        headers.update(extra_headers)
        body = extra_body

        def sync_call():
            completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_headers=headers,
                extra_body=body,
            )
            return completion

        try:
            completion = await anyio.to_thread.run_sync(sync_call)
            content = completion.choices[0].message.content
            # 마크다운 형식 제거 및 텍스트 정리
            return clean_markdown_text(content)
        except Exception as e:
            logger.error(f"OpenRouter API 호출 중 오류: {str(e)}")
            return None

    async def analyze_intent(self, user_message: str, available_apis: List[str]) -> Dict[str, Any]:
        """사용자 메시지의 의도를 LLM을 사용하여 분석하고 파라미터를 추출합니다."""
        
        # API별 파라미터 정보 정의
        api_parameters = {
            "job_posts": {
                "description": "채용공고 검색",
                "parameters": {
                    "company_name": "회사명 (예: 삼성, 네이버, 카카오)",
                    "job_name": "직무명 (예: 프론트엔드 개발자, 백엔드 엔지니어, 데이터 사이언티스트)",
                    "applicant_type": "지원자격 (신입/경력)",
                    "employment_type": "고용형태 (정규직/계약직/인턴)",
                    "tech_stack": "기술스택 (예: Python, React, Java, AWS)",
                    "limit": "검색 결과 개수 (기본값: 10)"
                }
            },
            "certificates": {
                "description": "자격증 정보 검색",
                "parameters": {
                    "limit": "검색 결과 개수 (기본값: 10)"
                }
            },
            "skills": {
                "description": "기술스택 정보 검색",
                "parameters": {
                    "limit": "검색 결과 개수 (기본값: 10)"
                }
            },
            "roadmaps": {
                "description": "학습 로드맵 검색",
                "parameters": {
                    "limit": "검색 결과 개수 (기본값: 10)"
                }
            },
            "visualization": {
                "description": "데이터 시각화",
                "parameters": {
                    "job_name": "직무명 (예: 프론트엔드 개발자)",
                    "field": "분석 필드 (tech_stack/qualifications, 기본값: tech_stack)"
                }
            },
            "job_recommendation": {
                "description": "맞춤형 직무 추천",
                "parameters": {
                    "top_n": "추천 개수 (기본값: 20)"
                }
            },
            "update_resume": {
                "description": "이력서 정보 수정/추가",
                "parameters": {
                    "job_name": "희망직무 (예: 프론트엔드 개발자, 백엔드 엔지니어) - 기존 직무에 추가됨",
                    "university": "대학교명",
                    "major": "전공",
                    "gpa": "학점 (예: 4.0, 3.5)",
                    "education_status": "학적상태 (재학중/졸업/휴학)",
                    "degree": "학위 (학사/석사/박사)",
                    "language_score": "어학점수 (예: TOEIC 900, IELTS 7.0)",
                    "working_year": "경력연차 (예: 3년, 신입)",
                    "skills": "기술스택 목록",
                    "certificates": "자격증 목록",
                    "experience": "경험 목록"
                }
            },
            "get_my_resume": {
                "description": "내 이력서 조회",
                "parameters": {}
            }
        }
        
        system_prompt = f"""
당신은 사용자의 메시지를 분석하여 적절한 API를 선택하고, 관련 파라미터를 정확히 추출하는 AI 어시스턴트입니다.

**사용 가능한 API 목록:**
{json.dumps(available_apis, ensure_ascii=False, indent=2)}

**API별 파라미터 정보:**
{json.dumps(api_parameters, ensure_ascii=False, indent=2)}

**중요한 파라미터 추출 규칙:**
1. **직무명 추출**: 
   - "프론트엔드 개발자", "백엔드 엔지니어", "데이터 사이언티스트", "PM", "UI/UX 디자이너" 등
   - 구체적이고 정확한 직무명을 추출하세요

2. **기술스택 추출**:
   - "Python", "React", "Java", "AWS", "Docker", "Kubernetes" 등
   - 여러 기술이 있으면 콤마로 구분하여 하나의 문자열로 만드세요

3. **회사명 추출**:
   - "삼성", "네이버", "카카오", "구글", "마이크로소프트" 등
   - "에서", "의" 등의 조사를 제거하세요

4. **지원자격/고용형태**:
   - 신입/경력, 정규직/계약직/인턴 등

5. **숫자 파라미터**:
   - "많이", "더 많은" → 더 큰 숫자
   - "적게", "몇 개" → 더 작은 숫자

6. **이력서 업데이트 파라미터**:
   - "희망직무 추가", "직무 추가" → job_name 파라미터 추출
   - "대학교", "전공", "학점" → university, major, gpa 파라미터 추출
   - "어학점수", "TOEIC", "IELTS" → language_score 파라미터 추출
   - "경력", "연차" → working_year 파라미터 추출

**Intent 분류 규칙:**
- 이력서 관련: "내 이력서", "이력서 보여줘" → `get_my_resume`
- 이력서 수정: "이력서 수정", "이력서 업데이트" → `update_resume`
- 채용공고: "채용공고", "구인", "일자리" → `job_posts`
- 자격증: "자격증", "증명서" → `certificates`
- 기술: "기술", "스킬" → `skills`
- 로드맵: "로드맵", "학습경로" → `roadmaps`
- 시각화: "분석", "통계", "차트" → `visualization`
- 추천: "추천", "맞춤" → `job_recommendation`

**응답 형식:**
{{
    "intent": "API 이름 또는 'general'",
    "confidence": 0.0-1.0,
    "parameters": {{
        "파라미터명": "추출된 값"
    }},
    "reasoning": "분석 근거"
}}

**예시:**
- "프론트엔드 개발자 채용공고 찾아줘" → {{"intent": "job_posts", "parameters": {{"job_name": "프론트엔드 개발자"}}}}
- "Python, React 사용하는 백엔드 개발자 구인" → {{"intent": "job_posts", "parameters": {{"job_name": "백엔드 개발자", "tech_stack": "Python, React"}}}}
- "네이버에서 신입 개발자 채용" → {{"intent": "job_posts", "parameters": {{"company_name": "네이버", "applicant_type": "신입", "job_name": "개발자"}}}}
- "내 희망직무에 서버 개발자도 추가해줘" → {{"intent": "update_resume", "parameters": {{"job_name": "서버 개발자"}}}}
- "이력서에 서울대학교 컴퓨터공학과 추가" → {{"intent": "update_resume", "parameters": {{"university": "서울대학교", "major": "컴퓨터공학과"}}}}
"""

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"사용자 메시지: {user_message}"}
        ]
        
        response = await self.chat_completion(messages, temperature=0.3)
        
        if response:
            try:
                # 코드블록 제거
                response_clean = re.sub(r'```[a-zA-Z]*\n|```', '', response).strip()
                # JSON 응답 파싱
                result = json.loads(response_clean)
                return result
            except json.JSONDecodeError:
                logger.error(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {response}")
                return {
                    "intent": "general",
                    "confidence": 0.0,
                    "parameters": {},
                    "reasoning": "JSON 파싱 실패"
                }
        else:
            return {
                "intent": "general",
                "confidence": 0.0,
                "parameters": {},
                "reasoning": "LLM 응답 실패"
            }
    
    async def generate_response(self, user_message: str, context: str = "") -> str:
        """일반적인 대화에 대한 응답을 생성합니다."""
        system_prompt = """
당신은 취업과 직무 관련 정보를 제공하는 친근한 AI 어시스턴트입니다.
사용자의 질문에 대해 도움이 되는 답변을 제공해주세요.
한국어로 자연스럽게 응답해주세요.
"""

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"컨텍스트: {context}\n\n사용자: {user_message}"}
        ]
        
        response = await self.chat_completion(messages, temperature=0.7)
        return response or "죄송합니다. 응답을 생성할 수 없습니다."

# 전역 LLM 클라이언트 인스턴스
llm_client = OpenRouterClient() 