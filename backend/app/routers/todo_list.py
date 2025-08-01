from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.database import get_db
from app.models.todo_list import TodoList
from app.models.user import User
from app.models.user_roadmap import UserRoadmap
from app.models.roadmap import Roadmap
from app.models.job_post import JobPost
from app.models.user_preference import UserPreference
from app.schemas.todo_list import (
    TodoListCreate, 
    TodoListUpdate, 
    TodoListResponse, 
    TodoListListResponse
)
from app.utils.dependencies import get_current_user
from app.utils.logger import app_logger
from app.services.llm_client import llm_client
from app.services.mcp_client import mcp_client
from app.services.gap_model import perform_gap_analysis_todo
from app.services.roadmap_model import get_roadmap_recommendations
from openai.types.chat import ChatCompletionMessageParam
import json

router = APIRouter(prefix="/todo-list", tags=["todo_list"])

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
                    "company": job.company_name,
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
        raise HTTPException(status_code=400, detail="사용자 ID를 찾을 수 없습니다.")
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
    
    # 4. 부족한 스킬에 매칭되는 강의들 필터링 (강의는 기간 제한 없음)
    matching_courses = []
    for roadmap in recommended_roadmaps:
        if roadmap.get('type') == '강의':
            # 강의는 기간 상관없이 모두 포함
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
                    app_logger.info(f"강의 '{roadmap.get('name')}' 추천: 스킬 매칭 ({skill})")
                    break  # 한 스킬이라도 매칭되면 추가
    
    # 5. 찜한 로드맵과 매칭 강의를 합쳐서 최종 로드맵 목록 생성 (기간 고려)
    final_roadmaps = []
    
    # 찜한 부트캠프도 기간 확인 후 추가
    bootcamps = [r for r in favorites['roadmaps'] if r.get('type') != '강의']
    suitable_bootcamps = []
    
    for bootcamp in bootcamps:
        start_date = bootcamp.get('start_date')
        end_date = bootcamp.get('end_date')
        
        if start_date and end_date:
            try:
                if isinstance(start_date, str):
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                else:
                    start_dt = start_date
                
                if isinstance(end_date, str):
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                else:
                    end_dt = end_date
                
                bootcamp_duration = (end_dt - start_dt).days
                
                # 부트캠프는 좀 더 관대하게 판단 (2배까지 허용)
                if bootcamp_duration <= days * 2:
                    suitable_bootcamps.append(bootcamp)
                    app_logger.info(f"부트캠프 '{bootcamp.get('name')}' 추천: 기간 적합 ({bootcamp_duration}일)")
                else:
                    app_logger.info(f"부트캠프 '{bootcamp.get('name')}' 제외: 기간이 너무 김 ({bootcamp_duration}일 > {days * 2}일)")
                    
            except (ValueError, TypeError) as e:
                app_logger.warning(f"부트캠프 '{bootcamp.get('name')}' 날짜 파싱 실패: {str(e)}")
                # 날짜 파싱 실패시 제외
                continue
        else:
            # 날짜 정보가 없는 부트캠프는 제외
            app_logger.info(f"부트캠프 '{bootcamp.get('name')}' 제외: 날짜 정보 없음")
            continue
    
    final_roadmaps.extend(suitable_bootcamps[:2])  # 최대 2개
    
    # 찜한 강의들은 기간 상관없이 모두 추가
    favorite_courses = [r for r in favorites['roadmaps'] if r.get('type') == '강의']
    final_roadmaps.extend(favorite_courses)
    
    for course in favorite_courses:
        app_logger.info(f"찜한 강의 '{course.get('name')}' 추천: 사용자가 찜한 강의")
    
    # 매칭된 강의들 추가 (중복 제거)
    existing_ids = {r.get('id') for r in final_roadmaps}
    for course in matching_courses:
        if course.get('id') not in existing_ids:
            final_roadmaps.append(course)
            existing_ids.add(course.get('id'))
    
    # 최대 10개로 제한
    final_roadmaps = final_roadmaps[:10]
    
    app_logger.info(f"최종 선택된 로드맵/강의: {len(final_roadmaps)}개 (요청 기간: {days}일)")
    for roadmap in final_roadmaps:
        roadmap_type = roadmap.get('type', '알 수 없음')
        if roadmap_type == '강의':
            app_logger.info(f"- {roadmap.get('name')} (강의) - 기간 제한 없음")
        else:
            duration_info = roadmap.get('duration_days', '알 수 없음')
            app_logger.info(f"- {roadmap.get('name')} ({roadmap_type}) - 기간: {duration_info}일")
    
    # 6. LLM을 통한 일정 생성
    # 현재 날짜 계산
    current_date = datetime.now()
    
    prompt = f"""
    다음 정보를 바탕으로 {days}일간의 학습 일정을 생성해주세요:
    
    [목표 직무]
    {job_title}
    
    [필요한 상위 기술 스택 (최대 10개)]
    {', '.join(top_skills[:10])}
    
    [찜한 로드맵 목록]
    {json.dumps(favorites['roadmaps'], ensure_ascii=False, default=str)}
    
    [추천 로드맵 목록 (기간에 맞는 것만 선별됨)]
    {json.dumps(final_roadmaps, ensure_ascii=False, default=str)}
    
    [찜한 공고 목록]
    {json.dumps(favorites['job_posts'], ensure_ascii=False, default=str)}
    
    [요구사항]
    1. **기간 준수**: 총 {days}일 기간에 맞춰 일정을 구성해주세요
    2. **로드맵 우선순위**: 추천 로드맵 목록의 부트캠프는 기간이 검증되었고, 강의는 기간 제한 없이 활용 가능
    3. **부트캠프 제한**: 찜한 부트캠프는 1-2개만 포함하고, 나머지는 강의 위주로 구성
    4. **스킬 학습 계획**: 부족한 스킬에 매칭되는 강의들을 우선적으로 일정에 포함
    5. **마감일 고려**: 찜한 로드맵의 시작일/마감일을 고려한 일정 배치
    6. **공고 준비**: 찜한 공고의 마감일을 고려한 준비 일정
    7. **일별 목표**: 일별 구체적인 학습 목표와 태스크 설정
    8. **주말 활용**: 주말에는 복습과 실습 프로젝트 포함
    9. **현실적 계획**: 공고 마감일 전 준비 완료되도록 일정 조정
    10. **날짜 설정**: 오늘({current_date.strftime('%Y-%m-%d')})부터 시작하여 {days}일간 설정
    
    [중요 알림]
    - 부트캠프는 요청 기간({days}일)에 적합한 것들만 선별되었습니다
    - 강의는 기간 제한 없이 모든 관련 강의가 포함되어 있습니다
    - 로드맵이 부족한 경우, 스킬 학습 위주로 일정을 구성해주세요
    - 무리한 일정보다는 현실적이고 달성 가능한 계획을 세워주세요
    
    출력 형식]
    다음 JSON 형태로 응답해주세요:
    {{
        "job_title": "{job_title}",
        "duration_days": {days},
        "target_skills": {json.dumps(top_skills, ensure_ascii=False)},
        "schedule": [
            {{
                "day": 1,
                "date": "{current_date.strftime('%Y-%m-%d')}",
                "goals": ["목표1", "목표2"],
                "tasks": [
                    {{
                        "title": "태스크 제목",
                        "description": "상세 설명",
                        "duration": "2시간",
                        "type": "roadmap|skill_study|job_prep|review|project",
                        "related_roadmap": "로드맵명 또는 null",
                        "related_job": "공고명 또는 null"
                    }}
                ],
                "notes": "항이나 팁"
            }}
        ],
        "roadmap_deadlines": [
            {{
                "roadmap_name": "로드맵명",
                "deadline": "2025-01-15",
                "days_remaining": 15
            }}
        ],
        "job_deadlines": [
            {{
                "job_title": "공고명",
                "company": "회사명",
                "deadline": "2025-01-20",
                "days_remaining": 20
            }}
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
        raise HTTPException(status_code=400, detail="LLM 응답을 받지 못했습니다.")
    
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
                "company": job['company'],
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

@router.post("/", response_model=TodoListResponse, summary="할 일 생성")
def create_todo(
    todo: TodoListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """새로운 할 일을 생성합니다."""
    try:
        db_todo = TodoList(
            user_id=current_user.id,
            title=todo.title,
            description=todo.description,
            is_completed=todo.is_completed,
            priority=todo.priority,
            due_date=todo.due_date,
            category=todo.category
        )
        db.add(db_todo)
        db.commit()
        db.refresh(db_todo)
        
        app_logger.info(f"할 일 생성 완료: 사용자 {current_user.id}, 할 일 ID {db_todo.id}")
        return db_todo
        
    except Exception as e:
        app_logger.error(f"할 일 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"할 일 생성 중 오류가 발생했습니다: {str(e)}")

@router.get("/", response_model=TodoListListResponse, summary="할 일 목록 조회")
def get_todos(
    is_completed: Optional[bool] = Query(None, description="완료 여부로 필터링"),
    priority: Optional[str] = Query(None, description="우선순위로 필터링 (low, medium, high)"),
    category: Optional[str] = Query(None, description="카테고리로 필터링"),
    due_date_from: Optional[datetime] = Query(None, description="마감일 시작 (YYYY-MM-DD)"),
    due_date_to: Optional[datetime] = Query(None, description="마감일 종료 (YYYY-MM-DD)"),
    sort_by: str = Query("created_at", description="정렬 기준 (created_at, due_date, priority, title)"),
    sort_order: str = Query("desc", description="정렬 순서 (asc, desc)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """사용자의 할 일 목록을 조회합니다. 다양한 필터링과 정렬 옵션을 지원합니다."""
    try:
        # 기본 쿼리
        query = db.query(TodoList).filter(TodoList.user_id == current_user.id)
        
        # 필터링
        if is_completed is not None:
            query = query.filter(TodoList.is_completed == is_completed)
        
        if priority:
            query = query.filter(TodoList.priority == priority)
        
        if category:
            query = query.filter(TodoList.category == category)
        
        if due_date_from:
            query = query.filter(TodoList.due_date >= due_date_from)
        
        if due_date_to:
            query = query.filter(TodoList.due_date <= due_date_to)
        
        # 정렬
        if sort_by == "due_date":
            order_column = TodoList.due_date
        elif sort_by == "priority":
            order_column = TodoList.priority
        elif sort_by == "title":
            order_column = TodoList.title
        else:
            order_column = TodoList.created_at
        
        if sort_order == "asc":
            query = query.order_by(asc(order_column))
        else:
            query = query.order_by(desc(order_column))
        
        todos = query.all()
        
        # 통계 계산
        total_count = len(todos)
        completed_count = sum(1 for todo in todos if todo.is_completed)
        pending_count = total_count - completed_count
        
        app_logger.info(f"할 일 목록 조회 완료: 사용자 {current_user.id}, 총 {total_count}개")
        
        return TodoListListResponse(
            todo_lists=todos,
            total_count=total_count,
            completed_count=completed_count,
            pending_count=pending_count
        )
        
    except Exception as e:
        app_logger.error(f"할 일 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"할 일 목록 조회 중 오류가 발생했습니다: {str(e)}")

@router.get("/{todo_id}", response_model=TodoListResponse, summary="할 일 상세 조회")
def get_todo(
    todo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """특정 할 일의 상세 정보를 조회합니다."""
    try:
        todo = db.query(TodoList).filter(
            and_(
                TodoList.id == todo_id,
                TodoList.user_id == current_user.id
            )
        ).first()
        
        if not todo:
            raise HTTPException(status_code=404, detail="할 일을 찾을 수 없습니다.")
        
        return todo
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"할 일 상세 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"할 일 상세 조회 중 오류가 발생했습니다: {str(e)}")

@router.put("/{todo_id}", response_model=TodoListResponse, summary="할 일 수정")
def update_todo(
    todo_id: int,
    todo_update: TodoListUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """할 일을 수정합니다."""
    try:
        todo = db.query(TodoList).filter(
            and_(
                TodoList.id == todo_id,
                TodoList.user_id == current_user.id
            )
        ).first()
        
        if not todo:
            raise HTTPException(status_code=404, detail="할 일을 찾을 수 없습니다.")
        
        # 업데이트할 필드만 수정
        update_data = todo_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(todo, field, value)
        
        todo.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(todo)
        
        app_logger.info(f"할 일 수정 완료: 사용자 {current_user.id}, 할 일 ID {todo_id}")
        return todo
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"할 일 수정 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"할 일 수정 중 오류가 발생했습니다: {str(e)}")

@router.delete("/clear", summary="모든 할 일 삭제")
def delete_all_todos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """현재 사용자의 모든 할 일을 삭제합니다."""
    try:
        # 현재 사용자의 모든 할 일 조회
        todos = db.query(TodoList).filter(TodoList.user_id == current_user.id).all()
        
        if not todos:
            return {"message": "삭제할 할 일이 없습니다.", "deleted_count": 0}
        
        deleted_count = len(todos)
        
        # 모든 할 일 삭제
        for todo in todos:
            db.delete(todo)
        
        db.commit()
        
        app_logger.info(f"모든 할 일 삭제 완료: 사용자 {current_user.id}, 삭제된 할 일 수 {deleted_count}")
        return {
            "message": f"모든 할 일이 삭제되었습니다. (총 {deleted_count}개)",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        app_logger.error(f"모든 할 일 삭제 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"모든 할 일 삭제 중 오류가 발생했습니다: {str(e)}")

@router.delete("/{todo_id}", summary="할 일 삭제")
def delete_todo(
    todo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """할 일을 삭제합니다."""
    try:
        todo = db.query(TodoList).filter(
            and_(
                TodoList.id == todo_id,
                TodoList.user_id == current_user.id
            )
        ).first()
        
        if not todo:
            raise HTTPException(status_code=404, detail="할 일을 찾을 수 없습니다.")
        
        db.delete(todo)
        db.commit()
        
        app_logger.info(f"할 일 삭제 완료: 사용자 {current_user.id}, 할 일 ID {todo_id}")
        return {"message": "할 일이 삭제되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"할 일 삭제 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"할 일 삭제 중 오류가 발생했습니다: {str(e)}")

@router.patch("/{todo_id}/toggle", response_model=TodoListResponse, summary="할 일 완료 상태 토글")
def toggle_todo_completion(
    todo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """할 일의 완료 상태를 토글합니다."""
    try:
        todo = db.query(TodoList).filter(
            and_(
                TodoList.id == todo_id,
                TodoList.user_id == current_user.id
            )
        ).first()
        
        if not todo:
            raise HTTPException(status_code=404, detail="할 일을 찾을 수 없습니다.")
        
        todo.is_completed = not todo.is_completed
        todo.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(todo)
        
        status = "완료" if todo.is_completed else "미완료"
        app_logger.info(f"할 일 상태 변경: 사용자 {current_user.id}, 할 일 ID {todo_id}, 상태 {status}")
        return todo
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"할 일 상태 변경 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"할 일 상태 변경 중 오류가 발생했습니다: {str(e)}")

@router.get("/stats/summary", summary="할 일 통계 요약")
def get_todo_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """할 일 통계 정보를 조회합니다."""
    try:
        # 전체 할 일 수
        total_todos = db.query(TodoList).filter(TodoList.user_id == current_user.id).count()
        
        # 완료된 할 일 수
        completed_todos = db.query(TodoList).filter(
            and_(
                TodoList.user_id == current_user.id,
                TodoList.is_completed == True
            )
        ).count()
        
        # 오늘 마감인 할 일 수
        today = datetime.utcnow().date()
        today_todos = db.query(TodoList).filter(
            and_(
                TodoList.user_id == current_user.id,
                TodoList.due_date >= today,
                TodoList.due_date < today + timedelta(days=1),
                TodoList.is_completed == False
            )
        ).count()
        
        # 지연된 할 일 수
        overdue_todos = db.query(TodoList).filter(
            and_(
                TodoList.user_id == current_user.id,
                TodoList.due_date < today,
                TodoList.is_completed == False
            )
        ).count()
        
        # 우선순위별 통계
        high_priority = db.query(TodoList).filter(
            and_(
                TodoList.user_id == current_user.id,
                TodoList.priority == "high",
                TodoList.is_completed == False
            )
        ).count()
        
        medium_priority = db.query(TodoList).filter(
            and_(
                TodoList.user_id == current_user.id,
                TodoList.priority == "medium",
                TodoList.is_completed == False
            )
        ).count()
        
        low_priority = db.query(TodoList).filter(
            and_(
                TodoList.user_id == current_user.id,
                TodoList.priority == "low",
                TodoList.is_completed == False
            )
        ).count()
        
        return {
            "total_todos": total_todos,
            "completed_todos": completed_todos,
            "pending_todos": total_todos - completed_todos,
            "completion_rate": round((completed_todos / total_todos * 100) if total_todos > 0 else 0, 2),
            "today_due": today_todos,
            "overdue": overdue_todos,
            "priority_stats": {
                "high": high_priority,
                "medium": medium_priority,
                "low": low_priority
            }
        }
        
    except Exception as e:
        app_logger.error(f"할 일 통계 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"할 일 통계 조회 중 오류가 발생했습니다: {str(e)}")

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
        
        # 기존 todo_list 확인 및 삭제
        existing_todos = db.query(TodoList).filter(TodoList.user_id == current_user.id).all()
        if existing_todos:
            app_logger.info(f"사용자 {current_user.id}의 기존 todo-list {len(existing_todos)}개를 삭제합니다.")
            for todo in existing_todos:
                db.delete(todo)
        
        # 새로운 일정을 TodoList 테이블에 저장
        created_todos = []
        for day_schedule in schedule_data.get("schedule", []):
            for task in day_schedule.get("tasks", []):
                # 마감일 계산 (일정의 날짜와 동일하게 설정)
                try:
                    task_date = datetime.strptime(day_schedule["date"], "%Y-%m-%d")
                    due_date = task_date  # 같은 날로 설정
                except:
                    due_date = datetime.now()
                
                # 우선순위 결정
                priority = "medium"
                if task.get("type") == "job_prep":
                    priority = "high"
                elif task.get("type") == "review":
                    priority = "low"
                
                # 카테고리 결정
                category = task.get("type", "일반")
                if task.get("type") == "roadmap":
                    category = "로드맵 학습"
                elif task.get("type") == "skill_study":
                    category = "스킬 학습"
                elif task.get("type") == "job_prep":
                    category = "취업 준비"
                elif task.get("type") == "review":
                    category = "복습"
                elif task.get("type") == "project":
                    category = "프로젝트"
                
                # TodoList 생성
                todo = TodoList(
                    user_id=current_user.id,
                    title=task.get("title", "제목 없음"),
                    description=task.get("description", ""),
                    is_completed=False,
                    priority=priority,
                    due_date=due_date,
                    category=category
                )
                db.add(todo)
                created_todos.append(todo)
        
        db.commit()
        
        app_logger.info(f"사용자 {current_user.id}의 일정 생성 완료: {job_title}, {len(created_todos)}개 할 일 생성")
        
        return {
            "success": True,
            "message": f"{job_title} 직무를 위한 {days}일 학습 일정이 생성되었습니다. 총 {len(created_todos)}개의 할 일이 생성되었습니다.",
            "data": schedule_data,
            "created_todos_count": len(created_todos)
        }
        
    except Exception as e:
        app_logger.error(f"일정 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"일정 생성 중 오류가 발생했습니다: {str(e)}")