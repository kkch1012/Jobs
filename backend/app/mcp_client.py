# mcp_client.py

"""
MCP API 호출을 모방하는 모의 클라이언트 모듈.
실제 외부 API를 호출하는 대신, 테스트용으로 예상 응답을 반환하는 함수를 제공합니다.
"""

def get_mcp_response(message: str) -> dict:
    """
    주어진 메시지를 MCP API에 보냈을 때 받을 법한 응답을 생성하여 반환합니다.
    실제 MCP API의 응답 구조를 흉내 내도록 구성합니다.
    """
    # 메시지를 처리하여 모의 응답 생성 (현재는 단순 에코 및 변형하여 예시 응답 구성)
    return {
        "status": "success",           # 예시: 성공을 나타내는 상태 필드
        "message": message,            # 요청으로 받은 메시지를 그대로 포함
        "data": f"Processed: {message}"  # 메시지를 처리한 결과를 가장한 값
    }
