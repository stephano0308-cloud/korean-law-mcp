#!/usr/bin/env python3
"""
MCP 서버 런처 스크립트
이 파일은 어디서 실행하든 올바르게 동작합니다.
Claude Desktop에서 이 파일의 절대 경로를 args에 지정하면 됩니다.
"""
import sys
import os

# 시작 로그 (Claude Desktop 로그에서 확인 가능)
print(f"[korean-law-mcp] run_server.py 시작", file=sys.stderr)
print(f"[korean-law-mcp] Python: {sys.executable}", file=sys.stderr)
print(f"[korean-law-mcp] 스크립트: {os.path.abspath(__file__)}", file=sys.stderr)

# 이 파일이 위치한 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# .env 파일 로드
env_path = os.path.join(script_dir, ".env")
if os.path.exists(env_path):
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f"[korean-law-mcp] .env 로드 완료", file=sys.stderr)

# 서버 실행
try:
    from src.main import mcp
    print(f"[korean-law-mcp] 서버 모듈 로드 성공", file=sys.stderr)
except ImportError as e:
    print(f"[korean-law-mcp] 모듈 로드 실패: {e}", file=sys.stderr)
    print(f"[korean-law-mcp] sys.path: {sys.path}", file=sys.stderr)
    raise

if __name__ == "__main__":
    mcp.run()
