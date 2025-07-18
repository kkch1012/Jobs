import asyncio
import httpx
import json
from datetime import datetime

FASTAPI_SERVER_URL = "http://localhost:8000"

async def test_llm_chat():
    print("\n💬 LLM 챗봇 테스트 중...")
    test_messages = [
        "채용공고 목록을 보여주세요",
        "IT 관련 자격증이 뭐가 있나요?",
        "프로그래밍 언어 목록을 보여주세요",
        "취업 로드맵을 알려주세요"
    ]
    async with httpx.AsyncClient() as client:
        for i, message in enumerate(test_messages, 1):
            print(f"\n📝 테스트 {i}: {message}")
            try:
                payload = {
                    "session_id": 123,
                    "message": message
                }
                response = await client.post(
                    f"{FASTAPI_SERVER_URL}/mcp/chat/test",
                    json=payload,
                    timeout=30.0
                )
                if response.status_code == 200:
                    data = response.json()
                    print("✅ 채팅 응답 성공")
                    print(f"   💬 응답: {data.get('message', '')[:100]}...")
                    print(f"   🎯 의도: {data.get('intent', {})}")
                else:
                    print(f"❌ 채팅 응답 실패: {response.status_code}")
                    print(f"   📄 응답: {response.text}")
            except Exception as e:
                print(f"❌ 채팅 테스트 실패: {e}")

async def main():
    print("🚀 LLM 챗봇 테스트")
    print("=" * 60)
    print(f"📅 테스트 시작 시간: {datetime.now()}")
    print(f"🔗 FastAPI 서버: {FASTAPI_SERVER_URL}")
    print("=" * 60)
    await test_llm_chat()
    print("\n" + "=" * 60)
    print(f"📅 테스트 완료 시간: {datetime.now()}")
    print("🎉 모든 테스트가 완료되었습니다!")

if __name__ == "__main__":
    asyncio.run(main()) 