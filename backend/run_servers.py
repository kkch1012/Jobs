import subprocess
import time
import sys
import os
from pathlib import Path

def run_server(script_name: str, port: int, description: str):
    """서버를 실행하는 함수"""
    print(f"🚀 {description} 시작 중... (포트: {port})")
    
    try:
        # Python 스크립트 실행
        process = subprocess.Popen([
            sys.executable, script_name
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # 서버 시작 대기
        time.sleep(3)
        
        if process.poll() is None:
            print(f"✅ {description}가 성공적으로 시작되었습니다!")
            print(f"   📍 URL: http://localhost:{port}")
            print(f"   📚 Swagger: http://localhost:{port}/docs")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"❌ {description} 시작 실패:")
            print(f"   stdout: {stdout}")
            print(f"   stderr: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ {description} 실행 중 오류 발생: {e}")
        return None

def main():
    print("🎯 외부 MCP 서버 + FastAPI 서버 연동 시스템")
    print("=" * 50)
    
    # 현재 디렉토리 확인
    current_dir = Path(__file__).parent
    print(f"📁 작업 디렉토리: {current_dir}")
    
    # 서버 실행
    processes = []
    
    # 1. MCP 서버 실행 (포트 8001)
    mcp_process = run_server("mcp_server.py", 8001, "MCP 서버")
    if mcp_process:
        processes.append(("MCP 서버", mcp_process))
    
    # 잠시 대기
    time.sleep(2)
    
    # 2. FastAPI 서버 실행 (포트 8000)
    fastapi_process = run_server("app/main.py", 8000, "FastAPI 서버")
    if fastapi_process:
        processes.append(("FastAPI 서버", fastapi_process))
    
    if not processes:
        print("❌ 모든 서버 시작에 실패했습니다.")
        return
    
    print("\n" + "=" * 50)
    print("🎉 서버 실행 완료!")
    print("\n📋 접속 정보:")
    print("   🔗 FastAPI 서버: http://localhost:8000")
    print("   📚 FastAPI Swagger: http://localhost:8000/docs")
    print("   🔗 MCP 서버: http://localhost:8001")
    print("   📚 MCP Swagger: http://localhost:8001/docs")
    print("\n🔄 외부 MCP 연동 API:")
    print("   📝 POST /mcp/chat/ - 외부 MCP를 통한 채팅")
    print("   📋 GET /mcp/tools - MCP 도구 목록")
    print("   💚 GET /mcp/health - MCP 서버 상태")
    print("   ⚙️ POST /mcp/tools/{tool_name}/call - 도구 호출")
    
    print("\n⏹️ 서버를 종료하려면 Ctrl+C를 누르세요...")
    
    try:
        # 서버들이 실행 중인 동안 대기
        while True:
            time.sleep(1)
            
            # 프로세스 상태 확인
            for name, process in processes:
                if process.poll() is not None:
                    print(f"⚠️ {name}가 예기치 않게 종료되었습니다.")
                    
    except KeyboardInterrupt:
        print("\n🛑 서버 종료 중...")
        
        # 모든 프로세스 종료
        for name, process in processes:
            if process.poll() is None:
                print(f"🔄 {name} 종료 중...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                    print(f"✅ {name} 종료 완료")
                except subprocess.TimeoutExpired:
                    print(f"⚠️ {name} 강제 종료")
                    process.kill()
        
        print("👋 모든 서버가 종료되었습니다.")

if __name__ == "__main__":
    main() 