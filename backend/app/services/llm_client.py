import json
from typing import Dict, List, Any, Optional
from app.config import settings
import logging
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
import anyio.to_thread
import re

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
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenRouter API 호출 중 오류: {str(e)}")
            return None

    async def analyze_intent(self, user_message: str, available_apis: List[str]) -> Dict[str, Any]:
        """사용자 메시지의 의도를 LLM을 사용하여 분석합니다."""
        system_prompt = f"""
당신은 사용자의 메시지를 분석하여 적절한 API를 선택하고, 관련 파라미터(회사명, 직무명, 기술스택 등)를 최대한 많이 추출하는 AI 어시스턴트입니다.

- 사용 가능한 API 목록:
{json.dumps(available_apis, ensure_ascii=False, indent=2)}

**중요한 Intent 분류 규칙:**
1. **이력서 관련 질문**은 반드시 해당 intent로 분류:
   - "내 이력서", "이력서 보여줘", "내 정보", "내 대학교", "내 학력", "내 경력" → `get_my_resume`
   - "이력서 수정", "이력서 업데이트", "이력서 추가" → `update_resume`

2. **채용공고 관련 질문**:
   - "채용공고", "구인", "일자리", "회사" → `job_posts`
   - "기술", "스킬", "기술스택" → `skills`
   - "자격증", "증명서" → `certificates`
   - "로드맵", "학습경로" → `roadmaps`

3. **시각화 관련 질문**:
   - "분석", "통계", "차트", "그래프" → `visualization`

- 각 intent에 대해 추출 가능한 모든 파라미터(예: company_name, job_name, applicant_type, employment_type, tech_stack 등)를 최대한 많이 추출하세요.
- 파라미터는 null로 두지 말고, 메시지에서 추출 가능한 값이 하나라도 있으면 반드시 포함하세요.
- 하나의 조건만 있어도 검색이 가능하니, 일부 파라미터만 추출되어도 모두 포함하세요.
- 반드시 코드블록(예: ```json ... ```) 없이, 순수한 JSON만 반환하세요.

**예시:**
  {{"intent": "get_my_resume", "confidence": 0.95, "parameters": {{}}, "reasoning": "사용자가 '내 대학교 조회해줘'라고 요청했으므로, 이력서 조회 intent로 분류함."}}
  {{"intent": "get_my_resume", "confidence": 0.9, "parameters": {{}}, "reasoning": "사용자가 '내 이력서 보여줘'라고 요청했으므로, 이력서 조회 intent로 분류함."}}
  {{"intent": "job_posts", "confidence": 0.85, "parameters": {{"company_name": "더스윙"}}, "reasoning": "사용자가 '더스윙 채용공고 조회해줘'라고 요청했으므로, 회사명을 추출함."}}

다음 JSON 형식으로 응답하세요:
{{
    "intent": "API 이름 또는 'general'",
    "confidence": 0.0-1.0,
    "parameters": {{}},
    "reasoning": "분석 근거"
}}
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