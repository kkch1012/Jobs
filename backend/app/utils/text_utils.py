import re
from typing import Optional

def clean_markdown_text(text: Optional[str]) -> str:
    """
    마크다운 형식을 제거하고 읽기 좋은 텍스트로 변환합니다.
    
    Args:
        text: 정리할 텍스트
        
    Returns:
        정리된 텍스트
    """
    if not text:
        return ""
    
    # 마크다운 헤더 제거 (###, ##, #)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # 볼드 텍스트 제거 (**text** -> text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    
    # 이탤릭 텍스트 제거 (*text* -> text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    
    # 코드 블록 제거 (```code``` -> code)
    text = re.sub(r'```[a-zA-Z]*\n(.*?)\n```', r'\1', text, flags=re.DOTALL)
    
    # 인라인 코드 제거 (`code` -> code)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # 링크 제거 ([text](url) -> text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # 리스트 마커 정리 (-, *, + -> •)
    text = re.sub(r'^[\s]*[-*+]\s+', '• ', text, flags=re.MULTILINE)
    
    # 번호 리스트 정리 (1. -> 1)
    text = re.sub(r'^[\s]*\d+\.\s+', lambda m: m.group().replace('.', ''), text, flags=re.MULTILINE)
    
    # 빈 줄 정리 (3개 이상 연속된 줄바꿈을 2개로)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    return text 