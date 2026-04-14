@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo ============================================
echo  Korean Law MCP - 설정 진단 도구
echo ============================================
echo.

set "ERRORS=0"

:: 1. Claude Desktop 설정 파일 확인
echo [1] Claude Desktop 설정 파일 확인
set "CONFIG_FILE=%APPDATA%\Claude\claude_desktop_config.json"
if exist "%CONFIG_FILE%" (
    echo   파일 위치: %CONFIG_FILE%
    echo   --- 내용 ---
    type "%CONFIG_FILE%"
    echo.
    echo   --- 끝 ---

    :: run_server.py가 포함되어 있는지 확인
    findstr /i "run_server" "%CONFIG_FILE%" >nul 2>&1
    if errorlevel 1 (
        echo   [문제] 설정에 run_server.py가 없습니다!
        echo   setup_claude_desktop.bat를 다시 실행하세요.
        set /a ERRORS+=1
    ) else (
        echo   [OK] run_server.py 설정 확인됨
    )

    :: -m src.main 이 포함되어 있는지 확인 (잘못된 설정)
    findstr /i "src.main" "%CONFIG_FILE%" >nul 2>&1
    if not errorlevel 1 (
        echo   [문제] 이전 설정(-m src.main)이 남아있습니다!
        echo   setup_claude_desktop.bat를 다시 실행하세요.
        set /a ERRORS+=1
    )
) else (
    echo   [문제] 설정 파일이 없습니다: %CONFIG_FILE%
    echo   setup_claude_desktop.bat를 실행하세요.
    set /a ERRORS+=1
)

echo.

:: 2. 다른 위치에 설정 파일이 있는지 확인
echo [2] 다른 위치의 설정 파일 확인
set "ALT1=%LOCALAPPDATA%\Claude\claude_desktop_config.json"
set "ALT2=%USERPROFILE%\.claude\claude_desktop_config.json"
set "ALT3=%USERPROFILE%\AppData\Local\Claude\claude_desktop_config.json"

if exist "%ALT1%" (
    echo   [주의] 추가 설정 발견: %ALT1%
    echo   --- 내용 ---
    type "%ALT1%"
    echo.
    echo   --- 끝 ---
    echo   이 파일이 우선 적용될 수 있습니다!
    set /a ERRORS+=1
) else (
    echo   %ALT1% - 없음 (정상)
)

if exist "%ALT2%" (
    echo   [주의] 추가 설정 발견: %ALT2%
    type "%ALT2%"
    echo.
    set /a ERRORS+=1
) else (
    echo   %ALT2% - 없음 (정상)
)

echo.

:: 3. Python 가상환경 확인
echo [3] Python 가상환경 확인
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "VENV_PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" (
    echo   [OK] Python: %VENV_PYTHON%
    "%VENV_PYTHON%" --version
) else (
    echo   [문제] 가상환경 Python을 찾을 수 없습니다: %VENV_PYTHON%
    set /a ERRORS+=1
)

echo.

:: 4. 필수 패키지 확인
echo [4] 필수 패키지 확인
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import fastmcp; print(f'  fastmcp {fastmcp.__version__}')" 2>nul || (echo   [문제] fastmcp 미설치 && set /a ERRORS+=1)
    "%VENV_PYTHON%" -c "import lxml; print(f'  lxml {lxml.__version__}')" 2>nul || (echo   [문제] lxml 미설치 && set /a ERRORS+=1)
    "%VENV_PYTHON%" -c "import requests; print(f'  requests {requests.__version__}')" 2>nul || (echo   [문제] requests 미설치 && set /a ERRORS+=1)
    "%VENV_PYTHON%" -c "import dotenv; print('  python-dotenv OK')" 2>nul || (echo   [문제] python-dotenv 미설치 && set /a ERRORS+=1)
    "%VENV_PYTHON%" -c "import pydantic; print(f'  pydantic {pydantic.__version__}')" 2>nul || (echo   [문제] pydantic 미설치 && set /a ERRORS+=1)
    "%VENV_PYTHON%" -c "import fastapi; print(f'  fastapi {fastapi.__version__}')" 2>nul || (echo   [문제] fastapi 미설치 && set /a ERRORS+=1)
)

echo.

:: 5. 서버 임포트 테스트
echo [5] 서버 임포트 테스트
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import sys; sys.path.insert(0, r'%PROJECT_DIR%'); from src.main import mcp; print('  [OK] 서버 임포트 성공')" 2>&1
    if errorlevel 1 (
        echo   [문제] 서버 임포트 실패
        set /a ERRORS+=1
    )
)

echo.

:: 6. .env 파일 확인
echo [6] API 키 확인
if exist "%PROJECT_DIR%\.env" (
    findstr /i "LAW_API_KEY" "%PROJECT_DIR%\.env" >nul 2>&1
    if errorlevel 1 (
        echo   [경고] .env에 LAW_API_KEY가 없습니다
    ) else (
        echo   [OK] LAW_API_KEY 설정됨
    )
) else (
    echo   [경고] .env 파일이 없습니다
)

echo.

:: 7. Claude 프로세스 확인
echo [7] Claude Desktop 프로세스 확인
tasklist /fi "imagename eq Claude.exe" 2>nul | findstr /i "Claude" >nul 2>&1
if not errorlevel 1 (
    echo   [주의] Claude Desktop이 실행 중입니다.
    echo   설정 변경 후에는 완전히 종료 후 재시작해야 합니다.
) else (
    echo   [OK] Claude Desktop이 실행 중이지 않습니다.
)

echo.
echo ============================================
if %ERRORS% EQU 0 (
    echo  진단 결과: 모든 항목 정상
) else (
    echo  진단 결과: %ERRORS%개 문제 발견
    echo  위의 [문제] 항목을 확인하세요.
)
echo ============================================
echo.
pause
