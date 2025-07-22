from fastapi import APIRouter, Depends, HTTPException
from app.services.scheduler import get_scheduler_status, start_scheduler, stop_scheduler
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

@router.get(
    "/status",
    summary="스케줄러 상태 조회",
    description="현재 스케줄러의 상태와 등록된 작업들을 조회합니다."
)
def get_status():
    """스케줄러 상태 조회"""
    return get_scheduler_status()

@router.post(
    "/start",
    summary="스케줄러 시작",
    description="스케줄러를 시작합니다."
)
def start():
    """스케줄러 시작"""
    try:
        # 현재 상태 확인
        current_status = get_scheduler_status()
        if current_status.get("running", False):
            return {"message": "스케줄러가 이미 실행 중입니다.", "status": current_status}
        
        start_scheduler()
        return {"message": "스케줄러가 시작되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄러 시작 실패: {str(e)}")

@router.post(
    "/stop",
    summary="스케줄러 중지",
    description="스케줄러를 중지합니다."
)
def stop():
    """스케줄러 중지"""
    try:
        stop_scheduler()
        return {"message": "스케줄러가 중지되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄러 중지 실패: {str(e)}")

@router.post(
    "/run-similarity-batch",
    summary="유사도 계산 배치 작업 수동 실행",
    description="매일 아침 8시에 자동으로 실행되는 유사도 계산 배치 작업을 수동으로 실행합니다."
)
def run_similarity_batch_manual(
    current_user: User = Depends(get_current_user)
):
    """유사도 계산 배치 작업 수동 실행"""
    # 관리자 권한 확인 (필요시)
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="관리자만 실행할 수 있습니다.")
    
    try:
        from app.services.similarity_scores import auto_compute_all_users_similarity
        from app.database import get_db
        from sqlalchemy.orm import Session
        
        db = next(get_db())
        try:
            results = auto_compute_all_users_similarity(db)
            return {
                "message": "유사도 계산 배치 작업이 완료되었습니다.",
                "results": results
            }
        finally:
            db.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"배치 작업 실행 실패: {str(e)}")

@router.post(
    "/run-daily-stats",
    summary="일간 스킬 통계 생성 작업 수동 실행",
    description="매일 아침 8시에 자동으로 실행되는 일간 스킬 통계 생성 작업을 수동으로 실행합니다."
)
def run_daily_stats_manual(
    current_user: User = Depends(get_current_user)
):
    """일간 스킬 통계 생성 작업 수동 실행"""
    # 관리자 권한 확인 (필요시)
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="관리자만 실행할 수 있습니다.")
    
    try:
        from app.services.weekly_stats_service import WeeklyStatsService
        from app.database import get_db
        from sqlalchemy.orm import Session
        
        db = next(get_db())
        try:
            # 모든 필드 타입에 대해 일간 통계 생성
            field_types = ["tech_stack", "required_skills", "preferred_skills", "main_tasks_skills"]
            total_results = {}
            total_stats_created = 0
            
            for field_type in field_types:
                result = WeeklyStatsService.generate_weekly_stats(db, field_type)
                total_results[field_type] = result
                if result["success"]:
                    total_stats_created += result['total_stats_created']
            
            return {
                "message": f"일간 스킬 통계 생성 작업이 완료되었습니다. 총 {total_stats_created}개 통계 생성",
                "total_stats_created": total_stats_created,
                "results": total_results
            }
        finally:
            db.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"일간 통계 생성 작업 실행 실패: {str(e)}")

@router.post(
    "/run-daily-batch",
    summary="매일 아침 배치 작업 수동 실행",
    description="매일 아침 8시에 자동으로 실행되는 모든 배치 작업(유사도 계산 + 일간 통계 생성)을 수동으로 실행합니다."
)
def run_daily_batch_manual(
    current_user: User = Depends(get_current_user)
):
    """매일 아침 배치 작업 수동 실행"""
    # 관리자 권한 확인 (필요시)
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="관리자만 실행할 수 있습니다.")
    
    try:
        from app.services.similarity_scores import auto_compute_all_users_similarity
        from app.services.weekly_stats_service import WeeklyStatsService
        from app.database import get_db
        from sqlalchemy.orm import Session
        
        db = next(get_db())
        try:
            # 1. 유사도 계산
            similarity_results = auto_compute_all_users_similarity(db)
            
            # 2. 일간 통계 생성
            field_types = ["tech_stack", "required_skills", "preferred_skills", "main_tasks_skills"]
            stats_results = {}
            total_stats_created = 0
            
            for field_type in field_types:
                result = WeeklyStatsService.generate_weekly_stats(db, field_type)
                stats_results[field_type] = result
                if result["success"]:
                    total_stats_created += result['total_stats_created']
            
            return {
                "message": "매일 아침 배치 작업이 완료되었습니다.",
                "similarity_results": similarity_results,
                "stats_results": {
                    "total_stats_created": total_stats_created,
                    "details": stats_results
                }
            }
        finally:
            db.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"매일 아침 배치 작업 실행 실패: {str(e)}") 