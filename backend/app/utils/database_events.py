from sqlalchemy import event
from sqlalchemy.orm import Session
from app.models.job_post import JobPost
from app.services.weekly_stats_service import WeeklyStatsService
import logging
import asyncio
from app.database import SessionLocal

logger = logging.getLogger(__name__)

def setup_database_events():
    """데이터베이스 이벤트 리스너를 설정합니다."""
    
    @event.listens_for(JobPost, 'after_insert')
    def after_job_post_insert(mapper, connection, target):
        """채용공고 INSERT 후 자동 통계 생성"""
        try:
            logger.info(f"채용공고 INSERT 감지: job_id={target.id}")
            
            # 새로운 세션 생성 (이벤트 리스너에서는 기존 세션 사용 불가)
            db = SessionLocal()
            try:
                # 비동기 함수를 동기적으로 실행
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        WeeklyStatsService.auto_generate_stats_after_job_post_save(db, target.id)
                    )
                finally:
                    loop.close()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"채용공고 INSERT 후 통계 생성 실패: {str(e)}")

    @event.listens_for(JobPost, 'after_update')
    def after_job_post_update(mapper, connection, target):
        """채용공고 UPDATE 후 자동 통계 생성"""
        try:
            logger.info(f"채용공고 UPDATE 감지: job_id={target.id}")
            
            # 새로운 세션 생성
            db = SessionLocal()
            try:
                # 비동기 함수를 동기적으로 실행
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        WeeklyStatsService.auto_generate_stats_after_job_post_save(db, target.id)
                    )
                finally:
                    loop.close()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"채용공고 UPDATE 후 통계 생성 실패: {str(e)}")

    logger.debug("데이터베이스 이벤트 리스너 설정 완료") 