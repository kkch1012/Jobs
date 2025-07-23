import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from functools import wraps
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)

class RedisCacheManager:
    """Redis 기반 분산 캐시 관리자"""
    
    def __init__(self, redis_url: str = None, default_ttl: timedelta = timedelta(hours=1)):
        self.redis_url = redis_url or getattr(settings, 'REDIS_URL', 'redis://localhost:6379')
        self.default_ttl = default_ttl
        self._redis = None
    
    async def get_redis(self):
        """Redis 연결 가져오기"""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def close(self):
        """Redis 연결 종료"""
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    def generate_cache_key(self, cache_name: str, *args, **kwargs) -> str:
        """캐시 키 생성"""
        key_parts = [cache_name]
        
        # 위치 인자들 추가
        for arg in args:
            key_parts.append(str(arg))
        
        # 키워드 인자들을 정렬하여 추가
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")
        
        return ":".join(key_parts)
    
    async def get_cached_data(self, cache_name: str, cache_key: str, ttl: Optional[timedelta] = None) -> Optional[Any]:
        """캐시된 데이터 조회"""
        try:
            redis = await self.get_redis()
            full_key = f"{cache_name}:{cache_key}"
            cached_data = await redis.get(full_key)
            
            if cached_data:
                logger.info(f"Redis 캐시 히트: {full_key}")
                return json.loads(cached_data)
            
            return None
        except Exception as e:
            logger.error(f"Redis 캐시 조회 실패: {str(e)}")
            return None
    
    async def set_cached_data(self, cache_name: str, cache_key: str, data: Any, ttl: Optional[timedelta] = None) -> None:
        """데이터를 캐시에 저장"""
        try:
            redis = await self.get_redis()
            full_key = f"{cache_name}:{cache_key}"
            cache_ttl = int((ttl or self.default_ttl).total_seconds())
            
            await redis.setex(full_key, cache_ttl, json.dumps(data, default=str))
            logger.info(f"Redis 캐시 저장: {full_key}, TTL: {cache_ttl}초")
        except Exception as e:
            logger.error(f"Redis 캐시 저장 실패: {str(e)}")
    
    async def clear_user_cache(self, user_id: int, cache_names: Optional[list] = None) -> int:
        """사용자별 캐시 삭제"""
        try:
            redis = await self.get_redis()
            deleted_count = 0
            
            if cache_names is None:
                # 모든 캐시에서 사용자 관련 키 삭제
                pattern = f"*:user:{user_id}:*"
                keys = await redis.keys(pattern)
                if keys:
                    deleted_count = await redis.delete(*keys)
            else:
                for cache_name in cache_names:
                    pattern = f"{cache_name}:*:user:{user_id}:*"
                    keys = await redis.keys(pattern)
                    if keys:
                        deleted_count += await redis.delete(*keys)
            
            logger.info(f"사용자 Redis 캐시 삭제 완료: 사용자 {user_id}, 삭제된 캐시 수: {deleted_count}")
            return deleted_count
        except Exception as e:
            logger.error(f"사용자 Redis 캐시 삭제 실패: {str(e)}")
            return 0
    
    async def get_cache_status(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """캐시 상태 조회"""
        try:
            redis = await self.get_redis()
            status = {
                "redis_connected": True,
                "total_keys": await redis.dbsize(),
                "user_caches": {}
            }
            
            if user_id:
                pattern = f"*:user:{user_id}:*"
                keys = await redis.keys(pattern)
                status["user_caches"] = {
                    "user_id": user_id,
                    "cache_count": len(keys),
                    "cache_keys": keys[:10]  # 최대 10개만 표시
                }
            
            return status
        except Exception as e:
            logger.error(f"Redis 캐시 상태 조회 실패: {str(e)}")
            return {
                "redis_connected": False,
                "error": str(e)
            }

# 전역 Redis 캐시 매니저 인스턴스
redis_cache_manager = RedisCacheManager()

def redis_cache_result(cache_name: str, ttl: Optional[timedelta] = None, key_generator: Optional[Callable] = None):
    """Redis 캐싱 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 캐시 키 생성
            if key_generator:
                cache_key = key_generator(*args, **kwargs)
            else:
                cache_key = redis_cache_manager.generate_cache_key(cache_name, *args, **kwargs)
            
            # force_refresh 파라미터 확인
            force_refresh = kwargs.pop('force_refresh', False)
            
            # 캐시 확인 (force_refresh가 False인 경우만)
            if not force_refresh:
                cached_data = await redis_cache_manager.get_cached_data(cache_name, cache_key, ttl)
                if cached_data is not None:
                    return cached_data
            
            # 함수 실행
            result = await func(*args, **kwargs) if hasattr(func, '__await__') else func(*args, **kwargs)
            
            # 결과 캐시에 저장
            await redis_cache_manager.set_cached_data(cache_name, cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator 