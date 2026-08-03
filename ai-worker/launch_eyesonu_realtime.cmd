@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "EYESONU_EXE=%~dp0.venv\Scripts\eyesonu-realtime.exe"
if not exist "%EYESONU_EXE%" (
    echo EYES:ON U 실행 환경이 없습니다.
    echo 프로젝트 루트에서 uv sync --extra realtime 명령을 먼저 실행하세요.
    pause
    exit /b 1
)

"%EYESONU_EXE%"
set "EYESONU_EXIT_CODE=%errorlevel%"
if not "%EYESONU_EXIT_CODE%"=="0" (
    echo.
    echo 실행 중 오류가 발생했습니다. 위 메시지를 확인하세요.
    pause
)
exit /b %EYESONU_EXIT_CODE%
