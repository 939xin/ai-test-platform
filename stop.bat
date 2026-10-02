@echo off
REM NOTE: keep this file ASCII-only and CRLF. Chinese text in .bat breaks
REM cmd parsing on a CP936 console (verified on this machine).
cd /d "%~dp0"
REM System tools by absolute path, so a Git Bash shell on PATH cannot shadow
REM them. NOTE: do NOT quote these inside a "for /f ('...')" command --
REM cmd then treats the quoted string as a filename. System32 has no spaces.
set "SYS=%SystemRoot%\System32"

echo ==========================================
echo   AI Test Platform - Stop Services
echo ==========================================
echo.

REM ---------- 1. Kill whatever holds the app ports ----------
REM Look the processes up by port rather than by window title: cmd rewrites
REM window titles, so title matching is unreliable.
for %%P in (8000 5173) do (
    set "FOUND="
    for /f "tokens=5" %%a in ('%SYS%\netstat.exe -ano ^| %SYS%\findstr.exe ":%%P " ^| %SYS%\findstr.exe "LISTENING"') do (
        %SYS%\taskkill.exe /F /PID %%a >nul 2>&1
        set "FOUND=1"
    )
    if defined FOUND (
        echo     Killed process listening on port %%P
    ) else (
        echo     Nothing listening on port %%P
    )
)

REM ---------- 2. Best-effort sweep by window title ----------
%SYS%\taskkill.exe /FI "WINDOWTITLE eq backend*" /T /F >nul 2>&1
%SYS%\taskkill.exe /FI "WINDOWTITLE eq frontend*" /T /F >nul 2>&1

REM ---------- 3. Stop MySQL ----------
REM "stop" not "down": the data volume is kept, so data survives a restart.
docker compose stop mysql
if errorlevel 1 (
    echo     [SKIP] Could not stop MySQL - Docker may already be down.
)

echo.
echo Stopped.
echo Note: MySQL was only stopped, its data is kept.
echo       To wipe the data too, run: docker compose down -v
pause
