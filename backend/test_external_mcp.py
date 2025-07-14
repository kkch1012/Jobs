import asyncio
import httpx
import json
from datetime import datetime

# 서버 설정
FASTAPI_SERVER_URL = "http://localhost:8000"
MCP_SERVER_URL = "http://localhost:8001"

async def test_server_health():
    """서버 상태를 테스트합니다."""
    print("🔍 서버 상태 테스트 중...")
    
    async with httpx.AsyncClient() as client:
        # FastAPI 서버 상태 확인
        try:
            response = await client.get(f"{FASTAPI_SERVER_URL}/")
            if response.status_code == 200:
                print("✅ FastAPI 서버 정상 동작")
            else:
                print(f"❌ FastAPI 서버 오류: {response.status_code}")
        except Exception as e:
            print(f"❌ FastAPI 서버 연결 실패: {e}")
        
        # MCP 서버 상태 확인
        try:
            response = await client.get(f"{MCP_SERVER_URL}/health")
            if response.status_code == 200:
                print("✅ MCP 서버 정상 동작")
            else:
                print(f"❌ MCP 서버 오류: {response.status_code}")
        except Exception as e:
            print(f"❌ MCP 서버 연결 실패: {e}")

async def test_mcp_tools():
    """MCP 도구 목록을 테스트합니다."""
    print("\n🔧 MCP 도구 목록 테스트 중...")
    
    async with httpx.AsyncClient() as client:
        try:
            # FastAPI를 통한 MCP 도구 목록 조회
            response = await client.get(f"{FASTAPI_SERVER_URL}/mcp/tools")
            if response.status_code == 200:
                data = response.json()
                print("✅ MCP 도구 목록 조회 성공")
                print(f"   📋 도구 개수: {len(data.get('tools', []))}")
                for tool in data.get('tools', []):
                    print(f"   - {tool.get('name')}: {tool.get('description')}")
            else:
                print(f"❌ MCP 도구 목록 조회 실패: {response.status_code}")
        except Exception as e:
            print(f"❌ MCP 도구 목록 조회 실패: {e}")

async def test_mcp_chat():
    """MCP 채팅을 테스트합니다."""
    print("\n💬 MCP 채팅 테스트 중...")
    
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
                    print(f"   🔗 서버: {data.get('mcp_server', '')}")
                else:
                    print(f"❌ 채팅 응답 실패: {response.status_code}")
                    print(f"   📄 응답: {response.text}")
                    
            except Exception as e:
                print(f"❌ 채팅 테스트 실패: {e}")

async def test_direct_tool_call():
    """직접 도구 호출을 테스트합니다."""
    print("\n⚙️ 직접 도구 호출 테스트 중...")
    
    test_tools = [
        ("job_posts", {"limit": 3}),
        ("certificates", {"limit": 3}),
        ("skills", {"limit": 3}),
        ("roadmaps", {"limit": 3})
    ]
    
    async with httpx.AsyncClient() as client:
        for tool_name, arguments in test_tools:
            print(f"\n🔧 {tool_name} 도구 호출 테스트")
            
            try:
                payload = {
                    "name": tool_name,
                    "arguments": arguments
                }
                
                response = await client.post(
                    f"{FASTAPI_SERVER_URL}/mcp/tools/{tool_name}/call",
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print("✅ 도구 호출 성공")
                    print(f"   🎯 도구: {data.get('tool_name', '')}")
                    print(f"   📊 결과: {len(str(data.get('result', {})))} 문자")
                else:
                    print(f"❌ 도구 호출 실패: {response.status_code}")
                    print(f"   📄 응답: {response.text}")
                    
            except Exception as e:
                print(f"❌ 도구 호출 테스트 실패: {e}")

async def test_mcp_server_direct():
    """MCP 서버에 직접 접근을 테스트합니다."""
    print("\n🎯 MCP 서버 직접 접근 테스트 중...")
    
    async with httpx.AsyncClient() as client:
        try:
            # MCP 서버 루트 접근
            response = await client.get(f"{MCP_SERVER_URL}/")
            if response.status_code == 200:
                data = response.json()
                print("✅ MCP 서버 직접 접근 성공")
                print(f"   📋 사용 가능한 도구: {data.get('available_tools', [])}")
            else:
                print(f"❌ MCP 서버 직접 접근 실패: {response.status_code}")
        except Exception as e:
            print(f"❌ MCP 서버 직접 접근 실패: {e}")

async def main():
    """메인 테스트 함수"""
    print("🚀 외부 MCP 서버 + FastAPI 서버 연동 테스트")
    print("=" * 60)
    print(f"📅 테스트 시작 시간: {datetime.now()}")
    print(f"🔗 FastAPI 서버: {FASTAPI_SERVER_URL}")
    print(f"🔗 MCP 서버: {MCP_SERVER_URL}")
    print("=" * 60)
    
    # 테스트 실행
    await test_server_health()
    await test_mcp_tools()
    await test_mcp_chat()
    await test_direct_tool_call()
    await test_mcp_server_direct()
    
    print("\n" + "=" * 60)
    print(f"📅 테스트 완료 시간: {datetime.now()}")
    print("🎉 모든 테스트가 완료되었습니다!")

if __name__ == "__main__":
    asyncio.run(main()) 