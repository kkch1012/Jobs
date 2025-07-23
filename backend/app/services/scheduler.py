"""
FastAPI 애플리케이션 내 스케줄러 서비스
매일 아침 8시에 유사도 계산 배치 작업과 일간 스킬 통계 생성을 실행합니다.
"""

import asyncio
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.similarity_scores import async_auto_compute_all_users_similarity
from app.services.weekly_stats_service import WeeklyStatsService
from app.utils.logger import similarity_logger

APSCHEDULER_AVAILABLE = True
# 전역 스케줄러 인스턴스
scheduler = AsyncIOScheduler()

async def run_similarity_batch_job():
    """매일 아침 8시에 실행되는 유사도 계산 배치 작업"""
    try:
        similarity_logger.info("스케줄된 유사도 계산 배치 작업 시작")
        
        # 새로운 DB 세션 생성
        db = SessionLocal()
        try:
            # 비동기 유사도 계산 실행
            results = await async_auto_compute_all_users_similarity(db)
            
            similarity_logger.info(f"스케줄된 배치 작업 완료: "
                                 f"총 {results['total_users']}명, "
                                 f"성공 {results['success_count']}, "
                                 f"실패 {results['error_count']}, "
                                 f"건너뜀 {results['skipped_count']}")
            
            # 에러가 있는 경우 상세 로깅
            if results['error_count'] > 0:
                similarity_logger.warning("일부 사용자에서 오류 발생:")
                for detail in results['details']:
                    if detail.get('status') == 'error':
                        similarity_logger.warning(f"  사용자 {detail['user_id']}: {detail.get('error', 'Unknown error')}")
                        
        finally:
            db.close()
            
    except Exception as e:
        similarity_logger.error(f"스케줄된 배치 작업 실행 중 오류: {str(e)}")

async def run_daily_stats_job():
    """매일 아침 8시에 실행되는 일간 스킬 통계 생성 작업"""
    try:
        similarity_logger.info("스케줄된 일간 스킬 통계 생성 작업 시작")
        
        # 새로운 DB 세션 생성
        db = SessionLocal()
        try:
            # 모든 필드 타입에 대해 일간 통계 생성
            field_types = ["tech_stack", "required_skills", "preferred_skills", "main_tasks_skills"]
            total_stats_created = 0
            
            for field_type in field_types:
                try:
                    similarity_logger.info(f"필드 타입 '{field_type}' 일간 통계 생성 시작")
                    result = WeeklyStatsService.generate_weekly_stats(db, field_type)
                    
                    if result["success"]:
                        stats_created = result['total_stats_created']
                        total_stats_created += stats_created
                        similarity_logger.info(f"필드 타입 '{field_type}' 일간 통계 생성 완료: {stats_created}개")
                    else:
                        similarity_logger.error(f"필드 타입 '{field_type}' 일간 통계 생성 실패: {result['error']}")
                        
                except Exception as e:
                    similarity_logger.error(f"필드 타입 '{field_type}' 일간 통계 생성 중 오류: {str(e)}")
            
            similarity_logger.info(f"스케줄된 일간 통계 생성 작업 완료: 총 {total_stats_created}개 통계 생성")
                        
        finally:
            db.close()
            
    except Exception as e:
        similarity_logger.error(f"스케줄된 일간 통계 생성 작업 실행 중 오류: {str(e)}")

async def run_daily_batch_jobs():
    """매일 아침 8시에 실행되는 모든 배치 작업 (유사도 계산 + 일간 통계 생성)"""
    try:
        similarity_logger.info("매일 아침 배치 작업 시작")
        
        # 1. 유사도 계산 실행
        await run_similarity_batch_job()
        
        # 2. 일간 스킬 통계 생성 실행
        await run_daily_stats_job()
        
        similarity_logger.info("매일 아침 배치 작업 완료")
        
    except Exception as e:
        similarity_logger.error(f"매일 아침 배치 작업 실행 중 오류: {str(e)}")

def start_scheduler():
    """스케줄러 시작"""
    # 테스트 환경에서는 스케줄러 자동 실행 비활성화
    import os
    if os.getenv("DISABLE_SCHEDULER", "false").lower() == "true":
        similarity_logger.info("스케줄러가 비활성화되어 있습니다. (DISABLE_SCHEDULER=true)")
        return
        
    if not APSCHEDULER_AVAILABLE or scheduler is None:
        similarity_logger.warning("APScheduler가 설치되지 않았습니다. 스케줄러 기능이 비활성화됩니다.")
        return
        
    try:
        # 매일 아침 8시에 통합 배치 작업 실행 (유사도 계산 + 일간 통계 생성)
        scheduler.add_job(
            run_daily_batch_jobs,
            CronTrigger(hour=8, minute=0),  # 매일 아침 8시
            id='daily_batch_jobs',
            name='매일 아침 배치 작업 (유사도 계산 + 일간 통계 생성)',
            replace_existing=True
        )
        
        # 스케줄러 시작
        scheduler.start()
        similarity_logger.info("스케줄러가 시작되었습니다. 매일 아침 8시에 유사도 계산과 일간 통계 생성이 실행됩니다.")
        
    except Exception as e:
        similarity_logger.error(f"스케줄러 시작 실패: {str(e)}")
        raise

def stop_scheduler():
    """스케줄러 중지"""
    if not APSCHEDULER_AVAILABLE or scheduler is None:
        return
        
    try:
        scheduler.shutdown()
        similarity_logger.info("스케줄러가 중지되었습니다.")
    except Exception as e:
        similarity_logger.error(f"스케줄러 중지 실패: {str(e)}")

def get_scheduler_status():
    """스케줄러 상태 조회"""
    if not APSCHEDULER_AVAILABLE or scheduler is None:
        return {
            "running": False,
            "available": False,
            "message": "APScheduler가 설치되지 않았습니다.",
            "jobs": []
        }
        
    return {
        "running": scheduler.running,
        "available": True,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in scheduler.get_jobs()
        ]
    } 