from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.job_post import JobPost
from app.models.job_required_skill import JobRequiredSkill
from app.models.weekly_skill_stat import WeeklySkillStat
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import pytz

logger = logging.getLogger(__name__)

class WeeklyStatsService:
    """주간 스킬 통계 생성 및 관리 서비스"""
    
    # 백그라운드 실행을 위한 스레드 풀
    _executor = ThreadPoolExecutor(max_workers=2)
    
    # 중복 실행 방지를 위한 락
    _stats_generation_lock = threading.Lock()
    
    @staticmethod
    def generate_weekly_stats(db: Session, field_type: str = "tech_stack") -> Dict[str, Any]:
        """
        모든 직무에 대해 주간 스킬 통계를 생성합니다.
        
        Args:
            db: 데이터베이스 세션
            field_type: 분석할 필드 타입 (tech_stack, required_skills, preferred_skills, main_tasks_skills)
        
        Returns:
            생성된 통계 정보
        """
        try:
            logger.info(f"주간 스킬 통계 생성 시작: field_type={field_type}")
            
            # 1. 해당 필드 타입의 기존 통계 전체 삭제 (덮어쓰기 보장)
            # 특정 날짜의 통계만 삭제
            seoul_tz = pytz.timezone('Asia/Seoul')
            today = datetime.now(seoul_tz).date()
            deleted_count = db.query(WeeklySkillStat).filter(
                WeeklySkillStat.field_type == field_type,
                func.date(WeeklySkillStat.created_date) == today
            ).delete()
            db.commit()
            logger.info(f"기존 통계 삭제 완료: {deleted_count}개 (field_type={field_type})")
            
            # 2. 모든 직무 조회
            job_roles = db.query(JobRequiredSkill).all()
            total_stats_created = 0
            
            for job_role in job_roles:
                stats_created = WeeklyStatsService._generate_stats_for_job_role(
                    db, job_role, field_type
                )
                total_stats_created += stats_created
                logger.info(f"직무 '{job_role.job_name}' 통계 생성 완료: {stats_created}개")
            
            logger.info(f"주간 스킬 통계 생성 완료: 총 {total_stats_created}개 통계 생성")
            return {
                "success": True,
                "total_stats_created": total_stats_created,
                "field_type": field_type,
                "job_roles_processed": len(job_roles),
                "deleted_previous": deleted_count
            }
            
        except Exception as e:
            logger.error(f"주간 스킬 통계 생성 실패: {str(e)}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    async def auto_generate_stats_after_job_post_save(db: Session, job_post_id: Optional[int] = None):
        """
        채용공고 저장 후 자동으로 통계를 생성합니다.
        
        Args:
            db: 데이터베이스 세션
            job_post_id: 새로 저장된 채용공고 ID (선택사항)
        """
        try:
            logger.info(f"채용공고 저장 후 자동 통계 생성 시작: job_post_id={job_post_id}")
            
            # 백그라운드에서 실행하여 응답 지연 방지
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                WeeklyStatsService._executor,
                WeeklyStatsService._generate_all_field_types_stats,
                db
            )
            
            logger.info("자동 통계 생성 완료")
            
        except Exception as e:
            logger.error(f"자동 통계 생성 실패: {str(e)}")

    @staticmethod
    def _generate_all_field_types_stats(db: Session):
        """
        모든 필드 타입에 대해 통계를 생성합니다.
        """
        # 중복 실행 방지를 위한 락 사용
        if not WeeklyStatsService._stats_generation_lock.acquire(blocking=False):
            logger.warning("이미 통계 생성이 진행 중입니다. 중복 실행을 건너뜁니다.")
            return
        
        try:
            field_types = ["tech_stack", "required_skills", "preferred_skills", "main_tasks_skills"]
            
            for field_type in field_types:
                try:
                    logger.info(f"필드 타입 '{field_type}' 통계 생성 시작")
                    result = WeeklyStatsService.generate_weekly_stats(db, field_type)
                    
                    if result["success"]:
                        logger.info(f"필드 타입 '{field_type}' 통계 생성 완료: {result['total_stats_created']}개")
                    else:
                        logger.error(f"필드 타입 '{field_type}' 통계 생성 실패: {result['error']}")
                        
                except Exception as e:
                    logger.error(f"필드 타입 '{field_type}' 통계 생성 중 오류: {str(e)}")
        finally:
            WeeklyStatsService._stats_generation_lock.release()
    
    @staticmethod
    def _generate_stats_for_job_role(db: Session, job_role: JobRequiredSkill, field_type: str) -> int:
        """
        특정 직무에 대해 주간 스킬 통계를 생성합니다.
        
        Args:
            db: 데이터베이스 세션
            job_role: 직무 정보
            field_type: 분석할 필드 타입
        
        Returns:
            생성된 통계 개수
        """
        # 1. 해당 직무의 채용공고 조회 (연속 주차 계산)
        posts = db.query(
            JobPost.posting_date,
            getattr(JobPost, field_type)
        ).filter(
            JobPost.job_required_skill_id == job_role.id
        ).all()
        
        # 2. 주별로 스킬 카운트 (ISO 주차 사용)
        week_skill_counter = defaultdict(Counter)
        for row in posts:
            posting_date, field_value = row.posting_date, row[1]
            
            # ISO 주차.요일 계산 (정확한 달력 주차)
            year, week_number, day_of_week = posting_date.isocalendar()
            week_day = f"{week_number}.{day_of_week}"
            
            skills = []
            
            # 필드 타입에 따른 처리
            if field_type == "tech_stack":
                # tech_stack은 문자열 필드
                if isinstance(field_value, str) and field_value.strip():
                    skills = [s.strip() for s in field_value.replace(';', ',').replace('/', ',').split(',') if s.strip()]
            else:
                # required_skills, preferred_skills, main_tasks_skills는 JSONB 필드
                if isinstance(field_value, list):
                    skills = [str(skill).strip() for skill in field_value if skill]
                elif isinstance(field_value, str) and field_value.strip():
                    # JSON 문자열인 경우 파싱 시도
                    try:
                        import json
                        parsed = json.loads(field_value)
                        if isinstance(parsed, list):
                            skills = [str(skill).strip() for skill in parsed if skill]
                    except:
                        # 파싱 실패 시 문자열로 처리
                        skills = [s.strip() for s in field_value.replace(';', ',').replace('/', ',').split(',') if s.strip()]
            
            # 스킬명 길이 제한 (500자)
            if skills:
                limited_skills = []
                for skill in skills:
                    if len(skill) > 500:
                        skill = skill[:497] + "..."  # 500자로 제한
                    limited_skills.append(skill)
                week_skill_counter[week_day].update(limited_skills)
        
        # 3. 기존 통계는 상위에서 이미 삭제되었으므로 건너뜀
        
        # 4. 새로운 통계 생성
        stats_created = 0
        for week_day, counter in week_skill_counter.items():
            # 해당 주차.요일의 기존 통계 삭제
            db.query(WeeklySkillStat).filter(
                WeeklySkillStat.job_role_id == job_role.id,
                WeeklySkillStat.week_day == week_day,  # week_day는 문자열 "290.1"
                WeeklySkillStat.field_type == field_type
            ).delete()
            
            # 새로운 통계 생성 (created_date는 __init__에서 자동으로 서울 시간 설정)
            for skill, count in counter.items():
                stat = WeeklySkillStat(
                    job_role_id=job_role.id,
                    week_day=week_day,
                    skill=skill,
                    count=count,
                    field_type=field_type
                )
                db.add(stat)
                stats_created += 1
        
        db.commit()
        return stats_created
    
    @staticmethod
    def get_weekly_stats(
        db: Session, 
        job_name: str, 
        field_type: str = "tech_stack",
        weeks_back: int = 12
    ) -> List[Dict[str, Any]]:
        """
        특정 직무의 주간 스킬 통계를 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            job_name: 직무명
            field_type: 필드 타입
            weeks_back: 몇 주 전까지 조회할지
        
        Returns:
            주간 스킬 통계 리스트
        """
        try:
            # 1. 직무 조회
            job_role = db.query(JobRequiredSkill).filter(
                JobRequiredSkill.job_name == job_name
            ).first()
            
            if not job_role:
                return []
            
            # 2. 최근 N주 데이터 조회 (서울 시간 기준)
            seoul_tz = pytz.timezone('Asia/Seoul')
            current_date = datetime.now(seoul_tz)
            target_date = current_date - timedelta(weeks=weeks_back)
            
            stats = db.query(WeeklySkillStat).filter(
                WeeklySkillStat.job_role_id == job_role.id,
                WeeklySkillStat.field_type == field_type,
                WeeklySkillStat.created_date.isnot(None),
                WeeklySkillStat.created_date >= target_date
            ).order_by(
                WeeklySkillStat.week_day.desc(),
                WeeklySkillStat.count.desc()
            ).all()
            
            # 3. 응답 형식으로 변환
            result = []
            for stat in stats:
                created_date_str = None
                if stat.created_date is not None:
                    created_date_str = stat.created_date.isoformat()
                
                result.append({
                    "week_day": stat.week_day,
                    "skill": stat.skill,
                    "count": stat.count,
                    "created_date": created_date_str
                })
            
            return result
            
        except Exception as e:
            logger.error(f"주간 스킬 통계 조회 실패: {str(e)}")
            return []
    
    @staticmethod
    def get_trend_data(
        db: Session,
        job_name: str,
        skill: str,
        field_type: str = "tech_stack"
    ) -> List[Dict[str, Any]]:
        """
        특정 스킬의 트렌드 데이터를 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            job_name: 직무명
            skill: 스킬명
            field_type: 필드 타입
        
        Returns:
            트렌드 데이터 리스트
        """
        try:
            # 1. 직무 조회
            job_role = db.query(JobRequiredSkill).filter(
                JobRequiredSkill.job_name == job_name
            ).first()
            
            if not job_role:
                return []
            
            # 2. 특정 스킬의 모든 트렌드 조회
            stats = db.query(WeeklySkillStat).filter(
                WeeklySkillStat.job_role_id == job_role.id,
                WeeklySkillStat.skill == skill,
                WeeklySkillStat.field_type == field_type
            ).order_by(
                WeeklySkillStat.week_day.asc()
            ).all()
            
            # 3. 응답 형식으로 변환
            result = []
            for stat in stats:
                result.append({
                    "week_day": stat.week_day,
                    "count": stat.count,
                    "date": f"Week {stat.week_day}"
                })
            
            return result
            
        except Exception as e:
            logger.error(f"트렌드 데이터 조회 실패: {str(e)}")
            return [] 