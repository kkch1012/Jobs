#!/usr/bin/env python3
"""
매일 아침 8시에 실행되는 유사도 계산 배치 스크립트
크롤링된 채용공고 데이터가 적재된 후 모든 사용자의 유사도 점수를 재계산합니다.
"""

import sys
import os
from datetime import datetime
import logging

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.services.similarity_scores import auto_compute_all_users_similarity
from app.utils.logger import similarity_logger

# 배치 전용 로거 설정
batch_logger = logging.getLogger("similarity_batch")
batch_logger.setLevel(logging.INFO)

def run_similarity_batch():
    """유사도 계산 배치 작업 실행"""
    start_time = datetime.now()
    batch_logger.info(f"유사도 계산 배치 작업 시작: {start_time}")
    
    db = SessionLocal()
    try:
        # 전체 사용자 유사도 계산 실행
        results = auto_compute_all_users_similarity(db)
        
        # 결과 로깅
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        batch_logger.info(f"배치 작업 완료: {end_time}")
        batch_logger.info(f"소요 시간: {duration:.2f}초")
        batch_logger.info(f"총 사용자 수: {results['total_users']}")
        batch_logger.info(f"성공: {results['success_count']}, 실패: {results['error_count']}, 건너뜀: {results['skipped_count']}")
        
        # 상세 결과 로깅 (에러가 있는 경우)
        if results['error_count'] > 0:
            batch_logger.warning("일부 사용자에서 오류 발생:")
            for detail in results['details']:
                if detail.get('status') == 'error':
                    batch_logger.warning(f"  사용자 {detail['user_id']}: {detail.get('error', 'Unknown error')}")
        
        return results
        
    except Exception as e:
        batch_logger.error(f"배치 작업 실행 중 오류 발생: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    try:
        results = run_similarity_batch()
        print(f"배치 작업 완료: 성공 {results['success_count']}, 실패 {results['error_count']}")
        sys.exit(0 if results['error_count'] == 0 else 1)
    except Exception as e:
        print(f"배치 작업 실패: {str(e)}")
        sys.exit(1) 