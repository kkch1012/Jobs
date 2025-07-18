from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.user_roadmap import UserRoadmap
from app.models.roadmap import Roadmap
from app.models.job_post import JobPost
from app.models.user_preference import UserPreference
from app.services.llm_client import llm_client
from app.services.mcp_client import mcp_client
from app.services.gap_model import perform_gap_analysis_todo
from app.services.roadmap_model import get_roadmap_recommendations
from app.utils.dependencies import get_current_user
from app.utils.exceptions import NotFoundException, BadRequestException, InternalServerException
from app.utils.logger import app_logger
from typing import List, Dict, Any, Optional, Union
from openai.types.chat import ChatCompletionMessageParam
import json
from datetime import datetime, timedelta

router = APIRouter(prefix="/todo", tags=["todo"])

async def get_user_favorites(user: User, db: Session) -> Dict[str, Any]:
    """사용자가 찜한 로드맵과 공고 목록 조회"""
    try:
        # 찜한 로드맵 조회
        user_roadmaps = (
            db.query(UserRoadmap)
            .join(Roadmap, UserRoadmap.roadmaps_id == Roadmap.id)
            .filter(UserRoadmap.user_id == user.id)
            .all()
        )
        
        roadmap_list = []
        for ur in user_roadmaps:
            roadmap_list.append({
                "id": ur.roadmap.id,
                "name": ur.roadmap.name,
                "type": ur.roadmap.type,
                "start_date": ur.roadmap.start_date,
                "end_date": ur.roadmap.end_date,
                "status": ur.roadmap.status,
                "company": ur.roadmap.company,
                "program_course": ur.roadmap.program_course,
                "skill_description": ur.roadmap.skill_description
            })
        
        # 찜한 공고 조회 (UserPreference 테이블에서 조회)
        job_posts = []
        user_preferences = db.query(UserPreference).filter(UserPreference.user_id == user.id).all()
        for pref in user_preferences:
            job = db.query(JobPost).filter(JobPost.id == pref.job_post_id).first()
            if job:
                job_posts.append({
                    "id": job.id,
                    "title": job.title,
                    "company": job.company_name,  # company_name 필드 사용
                    "posting_date": job.posting_date,
                    "deadline": job.deadline,
                    "required_skills": job.required_skills
                })
        
        return {
            "roadmaps": roadmap_list,
            "job_posts": job_posts
        }
    except Exception as e:
        app_logger.error(f"찜한 목록 조회 실패: {str(e)}")
        return {"roadmaps": [], "job_posts": []}

async def get_job_gap_analysis(job_title: str, user_id: int, db: Session) -> List[str]:
    """직무별 갭 분석을 통해 상위 10개 스택 조회"""
    try:
        app_logger.info(f"갭 분석 시작 - 직무: {job_title}, 사용자 ID: {user_id}")
        
        # gap_model을 사용하여 갭 분석 수행
        gap_result = perform_gap_analysis_todo(user_id, job_title, db)
        
        app_logger.info(f"갭 분석 결과: {gap_result}")
        
        # top_skills에서 상위 10개만 반환 (최대 10개)
        top_skills = gap_result.get("top_skills", [])
        app_logger.info(f"추출된 top_skills: {top_skills}")
        
        result = top_skills[:10]  # 상위 10개만 반환
        app_logger.info(f"최종 반환할 스킬: {result}")
        
        return result
        
    except Exception as e:
        app_logger.error(f"갭 분석 실패: {str(e)}")
        app_logger.error(f"상세 에러: {e.__class__.__name__}: {str(e)}")
        return []

async def generate_schedule_from_favorites(
    user: User,
    job_title: str,
    days: int,
    db: Session
) -> Dict[str, Any]:
    """찜한 로드맵/공고와 갭 분석을 기반으로 일정 생성"""
    
    # 1. 찜한 목록 조회
    favorites = await get_user_favorites(user, db)
    
    # 2. 직무별 상위 10 조회
    user_id = getattr(user, 'id', None)
    if user_id is None:
        raise BadRequestException("사용자 ID를 찾을 수 없습니다.")
    top_skills = await get_job_gap_analysis(job_title, user_id, db)
    
    # 3. 갭 분석 결과와 매칭되는 강의들 조회
    gap_analysis_result = perform_gap_analysis_todo(user_id, job_title, db)
    recommended_roadmaps = get_roadmap_recommendations(
        user_id=user_id,
        category=job_title,
        gap_result_text=gap_analysis_result["gap_result"],
        db=db,
        limit=50  # 더 많은 로드맵을 가져와서 선택
    )
    
    # 4. 부족한 스킬에 매칭되는 강의들 필터링
    matching_courses = []
    for roadmap in recommended_roadmaps:
        if roadmap.get('type') == '강의':
            # skill_description에서 스킬 추출
            skill_description = roadmap.get('skill_description', [])
            if isinstance(skill_description, str):
                try:
                    skill_description = json.loads(skill_description)
                except:
                    skill_description = [skill_description]
            
            # 부족한 스킬과 매칭되는지 확인
            for skill in top_skills:
                if any(skill.lower() in str(s).lower() for s in skill_description):
                    matching_courses.append({
                        "id": roadmap.get('id'),
                        "name": roadmap.get('name'),
                        "type": roadmap.get('type'),
                        "skill_description": roadmap.get('skill_description'),
                        "company": roadmap.get('company'),
                        "price": roadmap.get('price'),
                        "url": roadmap.get('url'),
                        "matched_skill": skill
                    })
                    break  # 한 스킬이라도 매칭되면 추가
    
    # 5. 찜한 로드맵과 매칭 강의를 합쳐서 최종 로드맵 목록 생성
    final_roadmaps = []
    
    # 찜한 부트캠프는 1-2개만 포함
    bootcamps = [r for r in favorites['roadmaps'] if r.get('type') != '강의']
    final_roadmaps.extend(bootcamps[:2])  # 최대 2개
    
    # 찜한 강의들 추가
    favorite_courses = [r for r in favorites['roadmaps'] if r.get('type') == '강의']
    final_roadmaps.extend(favorite_courses)
    
    # 매칭된 강의들 추가 (중복 제거)
    existing_ids = {r.get('id') for r in final_roadmaps}
    for course in matching_courses:
        if course.get('id') not in existing_ids:
            final_roadmaps.append(course)
            existing_ids.add(course.get('id'))
    
    # 최대 10개로 제한
    final_roadmaps = final_roadmaps[:10]
    
    #3 LLM을 통한 일정 생성
    # 현재 날짜 계산
    from datetime import datetime, timedelta
    current_date = datetime.now()
    
    prompt = f"""
    다음 정보를 바탕으로 {days}일간의 학습 일정을 생성해주세요:
    
    [목표 직무]
    {job_title}
    
    [필요한 상위 기술 스택 (최대 10개)]
    {', '.join(top_skills[:10])}
    
    [찜한 로드맵 목록]
    {json.dumps(favorites['roadmaps'], ensure_ascii=False, default=str)}
    
    [추천 로드맵 목록 (부족한 스킬에 매칭되는 강의 포함)]
    {json.dumps(final_roadmaps, ensure_ascii=False, default=str)}
    
    [찜한 공고 목록]
    {json.dumps(favorites['job_posts'], ensure_ascii=False, default=str)}
    
    요구사항]
    1. 찜한 부트캠프는 1-2개만 포함하고, 나머지는 강의 위주로 구성
    2. 부족한 스킬에 매칭되는 강의들을 우선적으로 일정에 포함
    3. 찜한 로드맵의 시작일/마감일을 고려한 일정 배치
    4. 찜한 공고의 마감일을 고려한 준비 일정
    5. 상위 10개 기술 스택 학습 계획
    6. 일별 구체적인 학습 목표와 태스크 설정
    7. 주말에는 복습과 실습 프로젝트 포함
    8. 공고 마감일 전 준비 완료되도록 일정 조정
    9. 날짜는 오늘({current_date.strftime('%Y-%m-%d')})부터 시작하여 {days}일간 설정
    
출력 형식]
    다음 JSON 형태로 응답해주세요:
    {{
        job_title: "{job_title}",
        duration_days: {days},
        target_skills": {json.dumps(top_skills, ensure_ascii=False)},
    "schedule":{{
        day1
               date": "{current_date.strftime('%Y-%m-%d')}",
                goals": ["목표1", "목표2"],
         tasks                   {{
                      title": "태스크 제목",
                        description": "상세 설명",
                      duration": "2시간",
                       type": "roadmap|skill_study|job_prep|review|project",
                        related_roadmap": "로드맵명 또는 null",
                        related_job": "공고명 또는 null"
                    }}
                ],
                notes: "항이나 팁"
            }}
        ],
        roadmap_deadlines:{{
                roadmap_name": "로드맵명",
                deadline": "2025-01-15",
                days_remaining": 15        }}
        ],
      job_deadlines:{{
               job_title": "공고명",
                company": "회사명",
                deadline": "2025-01-20",
                days_remaining": 20        }}
        ]
    }}
    """
    
    messages: List[ChatCompletionMessageParam] = [
        {
            "role": "system", 
            "content": "당신은 취업 준비생을 위한 학습 일정 수립 전문가입니다. 사용자가 찜한 로드맵과 공고 정보, 그리고 목표 직무의 필요 기술 스택을 종합적으로 고려하여 실현 가능하고 효과적인 학습 일정을 수립해주세요."
        },
        {"role": "user", "content": prompt}
    ]
    
    response = await llm_client.chat_completion(messages)
    
    if not response:
        raise BadRequestException("LLM 응답을 받지 못했습니다.")
    
    # JSON 파싱
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_str = response[json_start:json_end]
            schedule_data = json.loads(json_str)
        else:
            # 기본 구조 생성
            schedule_data = create_fallback_schedule(job_title, days, top_skills, favorites, final_roadmaps)
    except json.JSONDecodeError:
        app_logger.warning(f"LLM 응답 JSON 파싱 실패: {response}")
        schedule_data = create_fallback_schedule(job_title, days, top_skills, favorites, final_roadmaps)
    
    return schedule_data

def create_fallback_schedule(
    job_title: str, 
    days: int, 
    top_skills: List[str], 
    favorites: Dict[str, Any],
    final_roadmaps: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """LLM 응답 실패 시 기본 일정 생성"""
    
    # 현재 날짜부터 시작
    from datetime import datetime, timedelta
    start_date = datetime.now()
    
    schedule = []
    for i in range(days):
        day_tasks = []
        
        # 기술 스택 학습 (상위 10개를 60일간 분산)
        skill_index = i % len(top_skills) if top_skills else -1
        if skill_index >= 0 and skill_index < len(top_skills):
            skill = top_skills[skill_index]
            day_tasks.append({
                "title": f"{skill} 학습",
                "description": f"{skill}에 대한 기본 개념과 실습",
                "duration": "3시간",
                "type": "skill_study",
                "related_roadmap": None,
                "related_job": None
            })
        
        # 로드맵 학습 (최종 로드맵 목록 사용)
        roadmaps_to_use = final_roadmaps if final_roadmaps else favorites['roadmaps']
        if roadmaps_to_use and i % 3 == 0:
            roadmap = roadmaps_to_use[i % len(roadmaps_to_use)]
            roadmap_type = roadmap.get('type', '로드맵')
            task_type = "course" if roadmap_type == "강의" else "roadmap"
            day_tasks.append({
                "title": f"{roadmap['name']} 학습",
                "description": f"{roadmap['name']} 학습 ({roadmap_type})",
                "duration": "2시간",
                "type": task_type,
                "related_roadmap": roadmap['name'],
                "related_job": None
            })
        
        # 공고 준비 (찜한 공고가 있는 경우)
        if favorites['job_posts'] and i % 2 == 0:
            job = favorites['job_posts'][i % len(favorites['job_posts'])]
            day_tasks.append({
                "title": f"{job['title']} 지원서 작성 및 준비",
                "description": f"{job['company']} {job['title']} 지원서 작성 및 준비",
                "duration": "1.5시간",
                "type": "job_prep",
                "related_roadmap": None,
                "related_job": job['title']
            })
        
        # 주말 복습 및 프로젝트
        if i % 7 == 6:
            day_tasks.append({
                "title": "주간 복습 및 프로젝트",
                "description": "이번 주 학습 내용 복습 및 실습 프로젝트",
                "duration": "4시간",
                "type": "review",
                "related_roadmap": None,
                "related_job": None
            })
        
        schedule.append({
            "day": i + 1,
            "date": (start_date + timedelta(days=i)).strftime("%Y-%m-%d"),
            "goals": [f"Day {i + 1} 학습 목표 달성"],
            "tasks": day_tasks,
            "notes": "꾸준한 학습과 실습이 중요합니다."
        })
    
    # 마감일 정보 생성
    roadmap_deadlines = []
    for roadmap in favorites['roadmaps']:
        if roadmap.get('end_date'):
            deadline = roadmap['end_date']
            days_remaining = (deadline - datetime.now()).days
            roadmap_deadlines.append({
                "roadmap_name": roadmap['name'],
                "deadline": deadline.strftime("%Y-%m-%d"),
                "days_remaining": max(0, days_remaining)
            })
    
    job_deadlines = []
    for job in favorites['job_posts']:
        if job.get('deadline'):
            deadline = job['deadline']
            days_remaining = (deadline - datetime.now()).days
            job_deadlines.append({
                "job_title": job['title'],
                "company": job['company'],  # get_user_favorites에서 이미 company_name으로 설정됨
                "deadline": deadline.strftime("%Y-%m-%d"),
                "days_remaining": max(0, days_remaining)
            })
    
    return {
        "job_title": job_title,
        "duration_days": days,
        "target_skills": top_skills,
        "schedule": schedule,
        "roadmap_deadlines": roadmap_deadlines,
        "job_deadlines": job_deadlines
    }

@router.post("/generate", summary="찜한 로드맵/공고 기반 일정 생성")
async def generate_todo_list(
    job_title: str,
    days: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자가 찜한 로드맵/공고 정보, 그리고 직무별 갭 분석을 기반으로 맞춤 일정을 생성합니다.
    
    - 기존 todo_list가 있으면 새로운 일정으로 덮어씁니다.
    - 새로운 일정은 사용자의 찜한 로드맵, 공고, 갭 분석 결과를 종합하여 생성됩니다.
    
    Args:
        job_title: 목표 직무명
        days: 학습 기간 (일)
        current_user: 현재 로그인한 사용자
        db: 데이터베이스 세션
    
    Returns:
        생성된 일정
    """
    try:
        app_logger.info(f"사용자 {current_user.id}의 일정 생성 시작: {job_title}, {days}일")
        
        # 일정 생성
        schedule_data = await generate_schedule_from_favorites(current_user, job_title, days, db)
        
        # 기존 todo_list 확인
        existing_todo = getattr(current_user, 'todo_list', None)
        if existing_todo:
            app_logger.info(f"사용자 {current_user.id}의 기존 todo-list를 새로운 일정으로 덮어씁니다.")
        
        # 사용자 모델에 todo_list 저장 (JSON 형태로 저장) - 기존 데이터 덮어쓰기
        setattr(current_user, 'todo_list', schedule_data)
        db.commit()
        
        app_logger.info(f"사용자 {current_user.id}의 일정 생성 완료: {job_title}")
        
        return {
            "success": True,
            "message": f"{job_title} 직무를 위한 {days}일 학습 일정이 생성되었습니다.",
            "data": schedule_data
        }
        
    except Exception as e:
        app_logger.error(f"일정 생성 실패: {str(e)}")
        raise InternalServerException(f"일정 생성 중 오류가 발생했습니다: {str(e)}")

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