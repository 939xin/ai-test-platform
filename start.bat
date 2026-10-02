@echo off
REM NOTE: keep this file ASCII-only and CRLF. Chinese text in .bat breaks
REM cmd parsing on a CP936 console (verified on this machine).
setlocal enabledelayedexpansion
cd /d "%~dp0"
REM Call system tools by absolute path: a Git Bash shell on PATH would
REM otherwise shadow "timeout" with coreutils' version of the same name.
set "SYS=%SystemRoot%\System32"

echo ==========================================
echo   AI Test Platform - One-click Start
echo ==========================================
echo.

REM ---------- 1. Docker daemon ----------
REM Use "docker info" not "where docker": we need the daemon up, not just the CLI on PATH.
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running.
    echo         Start Docker Desktop, wait until it is fully ready, then re-run.
    pause
    exit /b 1
)
echo [1/5] Docker is ready

REM ---------- 2. MySQL (host port 3307, 3306 is usually taken) ----------
docker compose up -d mysql
if errorlevel 1 (
    echo [ERROR] Failed to start MySQL. Check docker-compose.yml.
    pause
    exit /b 1
)
echo [2/5] MySQL container started, waiting for healthy...

set /a TRIES=0
:waitdb
set "STATUS="
for /f "delims=" %%s in ('docker inspect -f "{{.State.Health.Status}}" test-platform-mysql 2^>nul') do set "STATUS=%%s"
if /i "!STATUS!"=="healthy" goto dbok
set /a TRIES+=1
if !TRIES! GEQ 40 (
    echo [ERROR] MySQL did not become healthy within 120s.
    echo         Diagnose with: docker logs test-platform-mysql
    pause
    exit /b 1
)
REM Sleep ~3s with ping rather than timeout: timeout refuses to run when
REM stdin is redirected, which would make this script untestable in a pipeline.
"%SYS%\ping.exe" -n 4 127.0.0.1 >nul
goto waitdb
:dbok
echo [3/5] MySQL is ready

REM ---------- 3. Backend deps (install only when missing) ----------
if not exist "backend\venv\Scripts\python.exe" (
    echo       First run: creating backend venv and installing deps, this takes a while...
    py -3 -m venv backend\venv
    backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install backend dependencies.
        pause
        exit /b 1
    )
)
if not exist "backend\.env" (
    copy "backend\.env.example" "backend\.env" >nul
    echo       [INFO] Created backend\.env from .env.example. Set DEEPSEEK_API_KEY to enable AI features.
)
echo [4/5] Backend dependencies ready

REM ---------- 4. Frontend deps ----------
if not exist "frontend\node_modules" (
    echo       First run: installing frontend deps, this takes a while...
    pushd frontend
    call npm install
    if errorlevel 1 (
        popd
        echo [ERROR] Failed to install frontend dependencies.
        pause
        exit /b 1
    )
    popd
)
echo [5/5] Frontend dependencies ready

REM ---------- 5. Launch services ----------
REM Use start /D to set the working directory: avoids nested quotes, which
REM cmd handles badly when the path contains spaces or non-ASCII characters.
echo.
echo Opening service windows...
start "backend" /D "%~dp0backend" cmd /k "chcp 65001 >nul & venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"
start "frontend" /D "%~dp0frontend" cmd /k "chcp 65001 >nul & npm run dev -- --host 127.0.0.1"

echo.
echo ==========================================
echo   Started
echo.
echo   Web UI      : http://127.0.0.1:5173
echo   API docs    : http://127.0.0.1:8000/docs
echo   Default user: admin / admin123
echo.
echo   To stop, run stop.bat (or just close the two windows).
echo   The backend needs a few seconds to create tables on first start.
echo ==========================================
pause
