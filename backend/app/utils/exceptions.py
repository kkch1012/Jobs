from fastapi import HTTPException, status
from typing import Any, Dict, Optional

class AppException(HTTPException):
    """애플리케이션 전용 예외 클래스"""
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.extra_data = extra_data or {}

def create_error_response(
    status_code: int,
    message: str,
    error_code: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """일관된 에러 응답 포맷 생성"""
    response = {
        "success": False,
        "error": {
            "code": error_code or f"ERR_{status_code}",
            "message": message
        }
    }
    
    if extra_data:
        response["error"]["details"] = extra_data
    
    return response

# 자주 사용되는 에러들
class NotFoundException(AppException):
    def __init__(self, resource: str, detail: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or f"{resource}을(를) 찾을 수 없습니다.",
            error_code="NOT_FOUND"
        )

class BadRequestException(AppException):
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
            error_code=error_code or "BAD_REQUEST"
        )

class UnauthorizedException(AppException):
    def __init__(self, message: str = "인증이 필요합니다."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            error_code="UNAUTHORIZED"
        )

class ForbiddenException(AppException):
    def __init__(self, message: str = "접근 권한이 없습니다."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=message,
            error_code="FORBIDDEN"
        )

class InternalServerException(AppException):
    def __init__(self, message: str = "서버 내부 오류가 발생했습니다."):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message,
            error_code="INTERNAL_ERROR"
        ) 