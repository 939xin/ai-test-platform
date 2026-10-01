@echo off
chcp 65001 > nul
echo ========================================
echo   接口自动化测试工具 - 环境初始化
echo ========================================
echo.

cd /d "%~dp0\.."

REM 创建虚拟环境
if not exist "venv" (
    echo [1/3] 创建 Python 虚拟环境...
    python -m venv venv
) else (
    echo [1/3] 虚拟环境已存在，跳过
)

REM 激活
call venv\Scripts\activate.bat

REM 安装依赖
echo [2/3] 安装项目依赖...
pip install -r requirements.txt -q

REM 创建必要目录
echo [3/3] 创建运行时目录...
if not exist "data" mkdir data
if not exist "reports" mkdir reports
if not exist "scripts" mkdir scripts
if not exist "drivers" mkdir drivers

echo.
echo ========================================
echo   环境初始化完成！
echo   运行: python main.py
echo   打包: scripts\build.bat
echo ========================================
pause
