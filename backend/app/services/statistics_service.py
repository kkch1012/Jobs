from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
import pytz
from collections import defaultdict
from app.models.weekly_skill_stat import WeeklySkillStat
from app.models.job_role import JobRole
from app.models.user_skill import UserSkill
from app.models.user import User
from app.schemas.visualization import WeeklySkillStat as WeeklySkillStatSchema
import logging

logger = logging.getLogger(__name__)

class StatisticsService:
    """통계 기능을 통합 관리하는 서비스 클래스"""
    
    @staticmethod
    def get_job_role_id(job_name: str, db: Session) -> int:
        """직무명으로 직무 ID를 조회합니다."""
        job_role = db.query(JobRole).filter(
            JobRole.job_name == job_name
        ).first()
        
        if not job_role:
            raise ValueError(f"직무 '{job_name}'을 찾을 수 없습니다.")
        
        return job_role.id
    
    @staticmethod
    def get_weekly_stats(job_name: str, week: Optional[int] = None, db: Session = None) -> List[Dict[str, Any]]:
        """주간 스킬 통계를 조회합니다."""
        try:
            job_role_id = StatisticsService.get_job_role_id(job_name, db)
            
            # 주차가 지정되지 않은 경우 현재 주차 사용
            if week is None:
                kst = pytz.timezone('Asia/Seoul')
                current_date = datetime.now(kst)
                week = current_date.isocalendar()[1]
            
            # 해당 주차의 통계 조회
            stats = db.query(WeeklySkillStat).filter(
                and_(
                    WeeklySkillStat.job_role_id == job_role_id,
                    WeeklySkillStat.week == week
                )
            ).all()
            
            return [
                {
                    "skill_name": stat.skill,
                    "frequency": stat.count,
                    "week": stat.week,
                    "job_role_id": stat.job_role_id
                }
                for stat in stats
            ]
            
        except Exception as e:
            logger.error(f"주간 통계 조회 실패: {str(e)}")
            raise
    
    @staticmethod
    def get_weekly_skill_frequency_range(
        job_name: str, 
        start_week: int, 
        end_week: int, 
        year: int, 
        field: str,
        db: Session
    ) -> List[Dict[str, Any]]:
        """특정 기간의 주간 스킬 빈도를 조회합니다."""
        try:
            job_role_id = StatisticsService.get_job_role_id(job_name, db)
            
            stats = db.query(WeeklySkillStat).filter(
                and_(
                    WeeklySkillStat.job_role_id == job_role_id,
                    WeeklySkillStat.field_type == field,
                    WeeklySkillStat.week >= start_week,
                    WeeklySkillStat.week <= end_week
                )
            ).all()
            
            # 주차별로 그룹화
            weekly_data = defaultdict(list)
            for stat in stats:
                weekly_data[stat.week].append({
                    "skill_name": stat.skill,
                    "frequency": stat.count
                })
            
            return [
                {
                    "week": week,
                    "skills": skills
                }
                for week, skills in sorted(weekly_data.items())
            ]
            
        except Exception as e:
            logger.error(f"주간 스킬 빈도 조회 실패: {str(e)}")
            raise
    
    @staticmethod
    def get_current_weekly_skill_frequency(
        job_name: str, 
        field: str, 
        db: Session
    ) -> List[Dict[str, Any]]:
        """현재 주차의 스킬 빈도를 조회합니다."""
        try:
            kst = pytz.timezone('Asia/Seoul')
            current_date = datetime.now(kst)
            current_week = current_date.isocalendar()[1]
            
            return StatisticsService.get_weekly_skill_frequency_range(
                job_name, current_week, current_week, current_date.year, field, db
            )
            
        except Exception as e:
            logger.error(f"현재 주차 스킬 빈도 조회 실패: {str(e)}")
            raise

    @staticmethod
    def get_daily_skill_frequency_range(
        job_name: str, 
        start_date: str, 
        end_date: str, 
        field: str,
        db: Session,
        rank_start: Optional[int] = None,
        rank_end: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """특정 날짜 범위의 일간 스킬 빈도를 조회합니다."""
        try:
            job_role_id = StatisticsService.get_job_role_id(job_name, db)
            
            # 날짜 파싱
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            stats = db.query(WeeklySkillStat).filter(
                and_(
                    WeeklySkillStat.job_role_id == job_role_id,
                    WeeklySkillStat.field_type == field,
                    WeeklySkillStat.date >= start_dt,
                    WeeklySkillStat.date <= end_dt
                )
            ).all()
            
            # 날짜별로 그룹화
            daily_data = defaultdict(list)
            for stat in stats:
                daily_data[stat.date.isoformat()].append({
                    "skill_name": stat.skill,
                    "frequency": stat.count
                })
            
            # 순위 범위가 지정된 경우 처리
            if rank_start is not None and rank_end is not None:
                # 각 날짜별로 count 기준 내림차순 정렬 후 순위 범위 필터링
                filtered_daily_data = {}
                for date, skills in daily_data.items():
                    # count 기준 내림차순 정렬
                    sorted_skills = sorted(skills, key=lambda x: x["frequency"], reverse=True)
                    
                    # 순위 범위 필터링 (1부터 시작하는 인덱스)
                    rank_start_idx = rank_start - 1  # 0부터 시작하는 인덱스로 변환
                    rank_end_idx = rank_end
                    
                    if rank_start_idx < len(sorted_skills):
                        filtered_skills = sorted_skills[rank_start_idx:rank_end_idx]
                        # 순위 정보 추가
                        for i, skill in enumerate(filtered_skills):
                            skill["rank"] = rank_start + i
                        if filtered_skills:  # 필터링된 결과가 있는 경우만 추가
                            filtered_daily_data[date] = filtered_skills
                
                daily_data = filtered_daily_data
            else:
                # 순위 범위가 지정되지 않은 경우에도 순위 정보 추가
                for date, skills in daily_data.items():
                    # count 기준 내림차순 정렬
                    sorted_skills = sorted(skills, key=lambda x: x["frequency"], reverse=True)
                    # 순위 정보 추가
                    for i, skill in enumerate(sorted_skills):
                        skill["rank"] = i + 1
                    daily_data[date] = sorted_skills
            
            return [
                {
                    "date": date,
                    "skills": skills
                }
                for date, skills in sorted(daily_data.items())
            ]
            
        except Exception as e:
            logger.error(f"일간 스킬 빈도 조회 실패: {str(e)}")
            raise
    
    @staticmethod
    def search_skills_by_keyword(keyword: str, db: Session) -> Dict[str, List[Dict[str, Any]]]:
        """키워드로 스킬을 검색합니다."""
        try:
            # 직무별 스킬에서 검색
            job_skills = db.query(JobRole).filter(
                JobRole.job_name.ilike(f"%{keyword}%")
            ).all()
            
            # 사용자 스킬에서 검색
            user_skills = db.query(UserSkill).filter(
                UserSkill.skill_name.ilike(f"%{keyword}%")
            ).all()
            
            result = {
                "job_skills": [
                    {
                        "skill_name": skill.job_name,
                        "job_name": skill.job_name,
                        "id": skill.id
                    }
                    for skill in job_skills
                ],
                "user_skills": [
                    {
                        "skill_name": skill.skill_name,
                        "user_id": skill.user_id,
                        "proficiency_level": skill.proficiency_level
                    }
                    for skill in user_skills
                ]
            }
            
            return result
            
        except Exception as e:
            logger.error(f"스킬 검색 실패: {str(e)}")
            return {
                "job_skills": [],
                "user_skills": []
            } 