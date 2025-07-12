import requests
import json

# 서버 URL
BASE_URL = "http://localhost:8000"

def test_chat_with_auth():
    """인증된 사용자로 채팅 테스트"""
    
    # 1. 로그인
    print("=== 로그인 ===")
    login_data = {
        "username": "user@example.com",
        "password": "strongpassword"
    }
    
    login_response = requests.post(f"{BASE_URL}/token", data=login_data)
    if login_response.status_code == 200:
        token_data = login_response.json()
        access_token = token_data["access_token"]
        print(f"✅ 로그인 성공: {token_data['token_type']}")
    else:
        print(f"❌ 로그인 실패: {login_response.status_code}")
        return
    
    # 2. 인증된 채팅 테스트
    print("\n=== 인증된 채팅 테스트 ===")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    chat_data = {
        "session_id": 1,
        "message": "나의 자격증이 뭐가있나요?"
    }
    
    chat_response = requests.post(f"{BASE_URL}/chat/", json=chat_data, headers=headers)
    if chat_response.status_code == 200:
        result = chat_response.json()
        print(f"✅ 채팅 성공")
        print(f"응답: {json.dumps(result, ensure_ascii=False, indent=2)}")
    else:
        print(f"❌ 채팅 실패: {chat_response.status_code}")
        print(f"에러: {chat_response.text}")

if __name__ == "__main__":
    test_chat_with_auth() 