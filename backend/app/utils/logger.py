import logging
import sys
from typing import Optional

def setup_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """로거 설정을 위한 유틸리티 함수"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:  # 중복 핸들러 방지
        logger.setLevel(level or logging.INFO)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # 포맷터
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger

# 기본 로거들
app_logger = setup_logger("app")
auth_logger = setup_logger("auth")
similarity_logger = setup_logger("similarity")
recommender_logger = setup_logger("recommender")
mcp_logger = setup_logger("mcp") 