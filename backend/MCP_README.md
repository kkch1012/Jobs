# MCP (Model Context Protocol) 연동 가이드

## 개요

이 프로젝트는 MCP(Model Context Protocol)를 사용하여 AI 챗봇과 백엔드 API를 연동합니다. 사용자의 자연어 요청을 분석하여 적절한 API를 호출하고, 결과를 자연스러운 응답으로 변환합니다.

## 주요 기능

### 1. 의도 분석 (Intent Analysis)
- 사용자의 자연어 메시지를 분석하여 호출할 API를 결정
- JSON 형태의 의도 데이터로 구조화

### 2. 컨텍스트 관리
- 대화 히스토리 저장 및 관리
- 세션별 메시지 추적
- 이전 대화 컨텍스트를 활용한 응답 생성

### 3. API 라우팅
- 지원하는 API 엔드포인트:
  - `/job_posts`: 채용공고 목록 조회
  - `/certificates`: 자격증 목록 조회
  - `/roadmaps`: 취업 로드맵 조회
  - `/skills`: 기술 스택 목록 조회
  - `/visualizations`: 데이터 시각화

## API 엔드포인트

### 1. 채팅
```http
POST /chat/
Content-Type: application/json

{
  "session_id": "user_session_123",
  "message": "채용공고 목록을 보여주세요"
}
```

### 2. 대화 히스토리 조회
```http
GET /chat/history/?session_id=user_session_123&limit=50
```

### 3. MCP 컨텍스트 조회
```http
GET /chat/context/user_session_123
```

### 4. 스트리밍 채팅
```http
POST /chat/stream/
Content-Type: application/json

{
  "session_id": "user_session_123",
  "message": "자격증 목록을 알려주세요"
}
```

## 사용 예시

### 1. 채용공고 조회
```bash
curl -X POST "http://localhost:8000/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user_123",
    "message": "최근에 올라온 채용공고를 보여주세요"
  }'
```

### 2. 자격증 정보 조회
```bash
curl -X POST "http://localhost:8000/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user_123",
    "message": "IT 관련 자격증 목록을 알려주세요"
  }'
```

### 3. 기술 스택 조회
```bash
curl -X POST "http://localhost:8000/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user_123",
    "message": "프로그래밍 언어 목록을 보여주세요"
  }'
```

## 데이터 구조

### MCPMessage 모델
```python
class MCPMessage(Document):
    session_id: str
    role: str  # "user" 또는 "assistant"
    content: str
    created_at: datetime
    tool_calls: Optional[list] = None
    tool_results: Optional[list] = None
    intent: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
```

### MCPIntent 스키마
```python
class MCPIntent(BaseModel):
    router: str  # 호출할 라우터 경로
    parameters: Dict[str, Any]  # 라우터 파라미터
```

## 설정

### 환경 변수
```env
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=jobs_db
```

### 의존성
```txt
fastapi
openai
beanie
motor
sqlalchemy
pydantic
```

## 확장 방법

### 1. 새로운 API 추가
1. `mcp_service.py`의 `available_tools` 리스트에 새 라우터 추가
2. `_get_tool_description()` 메서드에 설명 추가
3. `analyze_and_route()` 함수에 라우팅 로직 추가

### 2. 새로운 도구 추가
```python
# mcp_service.py
self.available_tools.append("/new_tool")

def _get_tool_description(self, tool: str) -> str:
    descriptions = {
        # ... 기존 도구들
        "/new_tool": "새로운 도구 설명"
    }
```

### 3. 컨텍스트 확장
```python
class MCPContext(BaseModel):
    # ... 기존 필드들
    user_preferences: Optional[Dict[str, Any]] = None
    system_settings: Optional[Dict[str, Any]] = None
```

## 주의사항

1. **인증이 필요한 API**: 사용자별 데이터 조회는 인증이 필요하므로 MCP에서 직접 호출할 수 없습니다.
2. **세션 관리**: 각 사용자별로 고유한 session_id를 사용해야 합니다.
3. **에러 처리**: API 호출 실패 시 적절한 에러 메시지를 반환합니다.
4. **성능**: 대화 히스토리는 최근 10개 메시지만 컨텍스트로 사용합니다.

## 트러블슈팅

### 1. 의도 분석 실패
- LLM 응답이 JSON 형식이 아닌 경우
- 지원하지 않는 라우터 요청 시

### 2. API 호출 실패
- 데이터베이스 연결 문제
- 인증이 필요한 API 호출 시

### 3. 메시지 저장 실패
- MongoDB 연결 문제
- 세션 ID 누락

## 향후 개선 계획

1. **스트리밍 응답**: 실시간 응답 스트리밍 구현
2. **멀티모달 지원**: 이미지, 파일 등 다양한 입력 지원
3. **플러그인 시스템**: 동적 도구 로딩 시스템
4. **성능 최적화**: 캐싱 및 배치 처리
5. **모니터링**: 대화 품질 및 사용량 모니터링 