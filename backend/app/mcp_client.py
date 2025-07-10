import os
import httpx


async def parse_mcp(message: str, user_id: int) -> dict:
    """
    프론트엔드에서 받은 자연어 메시지를 처리하여 적절한 로직을 실행하거나 데이터를 반환하는 함수
    - 현재는 모의 로직 기반으로 동작
    """
    msg = message.lower()
    result = {"status": "success", "input": message}

    # 0) 간단한 테스트 응답 (헬로월드 느낌)
    if "hello" in msg or "테스트" in msg:
        result["message"] = f" MCP 테스트 성공: '{message}' 메시지를 잘 받았습니다."
        return result

    # 1) '파이썬'과 '로드맵'이라는 단어가 포함된 메시지에 대해 처리
    if "파이썬" in msg and "로드맵" in msg:
        # (1) 파이썬이 포함된 로드맵 모의 추천 결과
        roadmaps = [
            {"id": 1, "title": "Python 입문 로드맵"},
            {"id": 2, "title": "백엔드 개발자 로드맵"}
        ]

        # (2) 사용자 기술스택에 '파이썬' 추가하는 로직 호출 (모의 구현)
        # 실제로는 다음과 같이 HTTP 호출로 처리 가능:
        # async with httpx.AsyncClient() as client:
        #     await client.post(f"http://localhost:8080/users/{user_id}/skills", json={"skill": "파이썬"})

        updated_user_skills = ["파이썬"]  # 모의 결과

        # (3) 사용자의 기술스택 기반 채용 공고 추천 (모의 구현)
        jobs = [
            {"id": 101, "title": "Python 백엔드 개발자"},
            {"id": 102, "title": "데이터 분석가"}
        ]

        result.update({
            "roadmaps": roadmaps,
            "updated_skills": updated_user_skills,
            "recommended_jobs": jobs,
            "message": " '파이썬' 기반 로드맵 추천 및 공고 추천 완료"
        })
        return result

    # 2) 향후 자연어 규칙 확장 가능 (예: 자격증, 경력 추가 등)
    if "자격증" in msg:
        # TODO: 자격증 관련 라우터 호출 및 처리
        result["message"] = "자격증 관련 처리를 여기에 추가할 수 있습니다."
        return result

    # 3) 기본 응답
    result["status"] = "fail"
    result["message"] = "해당 명령을 이해하지 못했습니다. 더 구체적으로 입력해 주세요."
    return result


def get_mcp_response(message: str) -> dict:
    """
    (옵션) 단순히 입력 메시지를 흉내내서 반환하는 모의 함수 (테스트용)
    """
    return {
        "status": "success",
        "message": message,
        "data": f"Processed: {message}"
    }
