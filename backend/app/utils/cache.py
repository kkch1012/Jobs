import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from functools import wraps
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class CacheManager:
    """공통 캐시 관리자"""
    
    def __init__(self, default_ttl: timedelta = timedelta(hours=1)):
        self.caches: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
    
    def get_cache(self, cache_name: str) -> Dict[str, Any]:
        """캐시 딕셔너리를 가져오거나 생성"""
        if cache_name not in self.caches:
            self.caches[cache_name] = {}
        return self.caches[cache_name]
    
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
    
    def is_cache_valid(self, cache_entry: Dict[str, Any], ttl: Optional[timedelta] = None) -> bool:
        """캐시가 유효한지 확인"""
        if not cache_entry:
            return False
        
        created_time = cache_entry.get('created_time')
        if not created_time:
            return False
        
        if isinstance(created_time, str):
            created_time = datetime.fromisoformat(created_time)
        
        cache_ttl = ttl or self.default_ttl
        return datetime.now() - created_time < cache_ttl
    
    def get_cached_data(self, cache_name: str, cache_key: str, ttl: Optional[timedelta] = None) -> Optional[Any]:
        """캐시된 데이터 조회"""
        cache = self.get_cache(cache_name)
        cached_result = cache.get(cache_key)
        
        if self.is_cache_valid(cached_result, ttl):
            logger.info(f"캐시 히트: {cache_name}:{cache_key}")
            return cached_result.get('data')
        
        return None
    
    def set_cached_data(self, cache_name: str, cache_key: str, data: Any, ttl: Optional[timedelta] = None) -> None:
        """데이터를 캐시에 저장"""
        cache = self.get_cache(cache_name)
        cache[cache_key] = {
            'data': data,
            'created_time': datetime.now(),
            'ttl': ttl or self.default_ttl
        }
        logger.info(f"캐시 저장: {cache_name}:{cache_key}")
    
    def clear_user_cache(self, user_id: int, cache_names: Optional[list] = None) -> int:
        """사용자별 캐시 삭제"""
        deleted_count = 0
        
        if cache_names is None:
            cache_names = list(self.caches.keys())
        
        for cache_name in cache_names:
            cache = self.get_cache(cache_name)
            keys_to_remove = []
            
            for cache_key in cache.keys():
                if f":{user_id}:" in cache_key:
                    keys_to_remove.append(cache_key)
            
            for key in keys_to_remove:
                del cache[key]
                deleted_count += 1
        
        logger.info(f"사용자 캐시 삭제 완료: 사용자 {user_id}, 삭제된 캐시 수: {deleted_count}")
        return deleted_count
    
    def get_cache_status(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """캐시 상태 조회"""
        status = {
            "total_caches": {},
            "user_caches": {}
        }
        
        for cache_name, cache in self.caches.items():
            status["total_caches"][cache_name] = len(cache)
            
            if user_id:
                user_cache = {}
                for cache_key, cache_data in cache.items():
                    if f":{user_id}:" in cache_key:
                        user_cache[cache_key] = {
                            "created_time": cache_data['created_time'].isoformat(),
                            "is_valid": self.is_cache_valid(cache_data)
                        }
                status["user_caches"][cache_name] = user_cache
        
        if user_id:
            status["user_cache_counts"] = {
                cache_name: len(cache_data) for cache_name, cache_data in status["user_caches"].items()
            }
        
        return status

# 전역 캐시 매니저 인스턴스
cache_manager = CacheManager()

def cache_result(cache_name: str, ttl: Optional[timedelta] = None, key_generator: Optional[Callable] = None):
    """캐싱 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성
            if key_generator:
                cache_key = key_generator(*args, **kwargs)
            else:
                cache_key = cache_manager.generate_cache_key(cache_name, *args, **kwargs)
            
            # force_refresh 파라미터 확인
            force_refresh = kwargs.pop('force_refresh', False)
            
            # 캐시 확인 (force_refresh가 False인 경우만)
            if not force_refresh:
                cached_data = cache_manager.get_cached_data(cache_name, cache_key, ttl)
                if cached_data is not None:
                    return cached_data
            
            # 함수 실행
            result = func(*args, **kwargs)
            
            # 결과 캐시에 저장
            cache_manager.set_cached_data(cache_name, cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

def cache_endpoint(cache_name: str, ttl: Optional[timedelta] = None):
    """엔드포인트용 캐싱 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 사용자 ID 추출 (current_user에서)
            user_id = None
            for arg in args:
                if hasattr(arg, 'id'):
                    user_id = arg.id
                    break
            
            # force_refresh 파라미터 확인
            force_refresh = kwargs.get('force_refresh', False)
            
            # 캐시 키 생성 (사용자 ID 포함)
            cache_key_parts = [cache_name]
            if user_id:
                cache_key_parts.append(f"user:{user_id}")
            
            # 주요 파라미터들 추가
            for key, value in kwargs.items():
                if key not in ['db', 'current_user', 'force_refresh'] and value is not None:
                    cache_key_parts.append(f"{key}:{value}")
            
            cache_key = ":".join(cache_key_parts)
            
            # 캐시 확인 (force_refresh가 False인 경우만)
            if not force_refresh:
                cached_data = cache_manager.get_cached_data(cache_name, cache_key, ttl)
                if cached_data is not None:
                    return cached_data
            
            # 함수 실행
            result = func(*args, **kwargs)
            
            # 결과 캐시에 저장
            cache_manager.set_cached_data(cache_name, cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator 