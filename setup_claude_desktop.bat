@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo ============================================
echo  Korean Law MCP - Claude Desktop 자동 설정
echo ============================================
echo.

:: 현재 스크립트 위치 = 프로젝트 루트
set "PROJECT_DIR=%~dp0"
:: 끝의 \ 제거
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo [1/5] 프로젝트 경로 확인...
echo   프로젝트: %PROJECT_DIR%

:: run_server.py 존재 확인
if not exist "%PROJECT_DIR%\run_server.py" (
    echo   [오류] run_server.py 파일을 찾을 수 없습니다.
    echo   이 배치 파일을 프로젝트 루트 폴더에서 실행하세요.
    goto :error
)
echo   run_server.py 확인 완료

echo.
echo [2/5] Python 가상환경 확인...

:: venv Python 경로
set "VENV_PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo   가상환경이 없습니다. 생성합니다...
    python -m venv "%PROJECT_DIR%\.venv"
    if errorlevel 1 (
        echo   [오류] 가상환경 생성 실패. Python이 설치되어 있는지 확인하세요.
        goto :error
    )
)
echo   Python: %VENV_PYTHON%

echo.
echo [3/5] 필수 패키지 설치...
"%VENV_PYTHON%" -m pip install --quiet --upgrade pip
"%VENV_PYTHON%" -m pip install --quiet fastmcp lxml requests cachetools python-dotenv certifi fastapi pydantic
if errorlevel 1 (
    echo   [오류] 패키지 설치 실패
    goto :error
)
echo   패키지 설치 완료

echo.
echo [4/5] 서버 테스트...
"%VENV_PYTHON%" -c "import sys; sys.path.insert(0, r'%PROJECT_DIR%'); from src.main import mcp; print('서버 임포트 성공')"
if errorlevel 1 (
    echo   [오류] 서버 임포트 실패
    goto :error
)
echo   서버 테스트 통과

echo.
echo [5/5] Claude Desktop 설정 파일 생성...

:: 설정 파일 경로
set "CONFIG_DIR=%APPDATA%\Claude"
set "CONFIG_FILE=%CONFIG_DIR%\claude_desktop_config.json"

:: 디렉토리 생성
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

:: 경로에서 백슬래시를 이스케이프 (JSON용 이중 백슬래시)
set "ESC_PYTHON=%VENV_PYTHON:\=\\%"
set "ESC_RUNNER=%PROJECT_DIR%\run_server.py"
set "ESC_RUNNER=%ESC_RUNNER:\=\\%"

:: API 키 확인
set "API_KEY="
if exist "%PROJECT_DIR%\.env" (
    for /f "tokens=2 delims==" %%a in ('findstr /i "LAW_API_KEY" "%PROJECT_DIR%\.env"') do (
        set "API_KEY=%%a"
    )
)

:: 기존 설정 백업
if exist "%CONFIG_FILE%" (
    copy /y "%CONFIG_FILE%" "%CONFIG_FILE%.backup" >nul 2>&1
    echo   기존 설정 백업: %CONFIG_FILE%.backup
)

:: 새 설정 파일 작성
if defined API_KEY (
    (
        echo {
        echo   "mcpServers": {
        echo     "korean-law": {
        echo       "command": "%ESC_PYTHON%",
        echo       "args": ["%ESC_RUNNER%"],
        echo       "env": {
        echo         "LAW_API_KEY": "%API_KEY%"
        echo       }
        echo     }
        echo   }
        echo }
    ) > "%CONFIG_FILE%"
) else (
    (
        echo {
        echo   "mcpServers": {
        echo     "korean-law": {
        echo       "command": "%ESC_PYTHON%",
        echo       "args": ["%ESC_RUNNER%"]
        echo     }
        echo   }
        echo }
    ) > "%CONFIG_FILE%"
    echo   [경고] .env 파일에서 LAW_API_KEY를 찾을 수 없습니다.
    echo   나중에 수동으로 추가하세요.
)

echo   설정 파일 저장 완료: %CONFIG_FILE%
echo.

:: 설정 내용 표시
echo ============================================
echo  생성된 설정 내용:
echo ============================================
type "%CONFIG_FILE%"
echo.
echo ============================================

echo.
echo [완료] Claude Desktop을 완전히 종료 후 다시 실행하세요.
echo.
echo   주의사항:
echo   1. Claude Desktop 트레이 아이콘도 완전히 종료하세요
echo   2. 작업관리자에서 "Claude" 프로세스가 없는지 확인하세요
echo   3. 다시 Claude Desktop을 실행하면 korean-law 도구가 표시됩니다
echo.
pause
exit /b 0

:error
echo.
echo [실패] 설정 중 오류가 발생했습니다.
echo 위의 오류 메시지를 확인하세요.
pause
exit /b 1
