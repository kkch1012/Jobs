from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.services.llm_client import llm_client
from app.services.mcp_client import mcp_client
from app.utils.dependencies import get_current_user
from app.utils.exceptions import NotFoundException, BadRequestException, InternalServerException
from app.utils.logger import app_logger
from typing import List, Dict, Any
from openai.types.chat import ChatCompletionMessageParam
import json

router = APIRouter(prefix="/todo", tags=["todo"])

@router.post("/generate", summary="맞춤형 todo-list 생성")
async def generate_todo_list(
    course: str,
    days: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 이력과 코스 정보를 바탕으로 맞춤형 todo-list를 생성합니다.
    
    Args:
        course: 학습할 코스명
        days: 학습 기간 (일)
        current_user: 현재 로그인한 사용자
        db: 데이터베이스 세션
    
    Returns:
        생성된 todo-list
    """
    try:
        # 사용자 정보 요약
        user_summary = f"""
        사용자: {current_user.name}
        희망 직무: {current_user.desired_job}
        기술 스택: {[f"{s.skill.name}({s.proficiency})" for s in current_user.user_skills]}
        자격증: {[c.certificate.name for c in current_user.user_certificates]}
        """
        
        # LLM을 사용한 todo-list 생성
        prompt = f"""
        다음 사용자 정보와 코스 정보를 바탕으로 {days}일간의 상세한 학습 계획을 JSON 형태로 생성해주세요.
        
        [사용자 정보]
        {user_summary}
        
        [코스 정보]
        코스명: {course}
        학습 기간: {days}일
        
        [요구사항]
        1. 일별로 구체적인 학습 목표와 태스크를 설정
        2. 사용자의 현재 수준을 고려한 난이도 조정
        3. 실습과 이론을 균형있게 배치
        4. 주말에는 복습과 정리 시간 포함
        5. JSON 형태로 반환 (todos 배열에 일별 태스크 포함)
        
        응답은 반드시 유효한 JSON 형태여야 합니다.
        """
        
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": "당신은 학습 계획 수립 전문가입니다. 구체적이고 실현 가능한 학습 계획을 수립해주세요."},
            {"role": "user", "content": prompt}
        ]
        
        response = await llm_client.chat_completion(messages)
        
        if not response:
            raise BadRequestException("LLM 응답을 받지 못했습니다.")
        
        # JSON 파싱 시도
        try:
            # JSON 부분만 추출
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                todo_data = json.loads(json_str)
            else:
                # JSON이 없으면 기본 구조 생성
                todo_data = {
                    "course": course,
                    "duration_days": days,
                    "todos": [
                        {
                            "day": i + 1,
                            "tasks": [f"{course} 학습 - Day {i + 1}"],
                            "goals": [f"Day {i + 1} 학습 목표 달성"]
                        }
                        for i in range(days)
                    ]
                }
        except json.JSONDecodeError:
            app_logger.warning(f"LLM 응답 JSON 파싱 실패: {response}")
            # 기본 구조 생성
            todo_data = {
                "course": course,
                "duration_days": days,
                "todos": [
                    {
                        "day": i + 1,
                        "tasks": [f"{course} 학습 - Day {i + 1}"],
                        "goals": [f"Day {i + 1} 학습 목표 달성"]
                    }
                    for i in range(days)
                ]
            }
        
        # 사용자 모델에 todo_list 저장
        setattr(current_user, 'todo_list', todo_data)
        db.commit()
        
        app_logger.info(f"사용자 {current_user.id}의 todo-list 생성 완료: {course}")
        
        return {
            "success": True,
            "message": f"{course} 코스의 {days}일 학습 계획이 생성되었습니다.",
            "data": todo_data
        }
        
    except Exception as e:
        app_logger.error(f"todo-list 생성 실패: {str(e)}")
        raise InternalServerException(f"todo-list 생성 중 오류가 발생했습니다: {str(e)}")

@router.get("/user", summary="유저의 todo-list 조회")
def get_user_todo_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    현재 로그인한 사용자의 todo-list를 조회합니다.
    
    Args:
        current_user: 현재 로그인한 사용자
        db: 데이터베이스 세션
    
    Returns:
        사용자의 todo-list
    """
    try:
        todo_list = getattr(current_user, 'todo_list', None)
        if not todo_list or todo_list == []:
            return {
                "success": True,
                "message": "등록된 todo-list가 없습니다.",
                "data": None
            }
        
        app_logger.info(f"사용자 {current_user.id}의 todo-list 조회")
        
        return {
            "success": True,
            "message": "todo-list 조회 성공",
            "data": todo_list
        }
        
    except Exception as e:
        app_logger.error(f"todo-list 조회 실패: {str(e)}")
        raise InternalServerException(f"todo-list 조회 중 오류가 발생했습니다: {str(e)}")

@router.put("/update", summary="todo-list 업데이트")
def update_user_todo_list(
    todo_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 todo-list를 업데이트합니다.
    
    Args:
        todo_data: 업데이트할 todo-list 데이터
        current_user: 현재 로그인한 사용자
        db: 데이터베이스 세션
    
    Returns:
        업데이트 결과
    """
    try:
        setattr(current_user, 'todo_list', todo_data)
        db.commit()
        
        app_logger.info(f"사용자 {current_user.id}의 todo-list 업데이트 완료")
        
        return {
            "success": True,
            "message": "todo-list가 성공적으로 업데이트되었습니다.",
            "data": todo_data
        }
        
    except Exception as e:
        app_logger.error(f"todo-list 업데이트 실패: {str(e)}")
        raise InternalServerException(f"todo-list 업데이트 중 오류가 발생했습니다: {str(e)}")

@router.delete("/clear", summary="todo-list 삭제")
def clear_user_todo_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 todo-list를 삭제합니다.
    
    Args:
        current_user: 현재 로그인한 사용자
        db: 데이터베이스 세션
    
    Returns:
        삭제 결과
    """
    try:
        setattr(current_user, 'todo_list', [])
        db.commit()
        
        app_logger.info(f"사용자 {current_user.id}의 todo-list 삭제 완료")
        
        return {
            "success": True,
            "message": "todo-list가 성공적으로 삭제되었습니다."
        }
        
    except Exception as e:
        app_logger.error(f"todo-list 삭제 실패: {str(e)}")
        raise InternalServerException(f"todo-list 삭제 중 오류가 발생했습니다: {str(e)}")