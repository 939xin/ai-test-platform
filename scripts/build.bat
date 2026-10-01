@echo off
chcp 65001 > nul
echo ========================================
echo   接口自动化测试工具 - 打包构建脚本
echo ========================================
echo.

REM 激活虚拟环境
cd /d "%~dp0\.."
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [错误] 未找到虚拟环境，请先运行 setup.bat
    exit /b 1
)

REM 安装 PyInstaller
echo [1/3] 安装 PyInstaller...
pip install pyinstaller -q

REM 清理旧构建
echo [2/3] 清理旧构建...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM 构建
echo [3/3] 开始构建...
echo.
pyinstaller build.spec --clean --noconfirm

if exist "dist\接口自动化测试工具.exe" (
    echo.
    echo ========================================
    echo   构建成功！
    echo   输出: dist\接口自动化测试工具.exe
    echo ========================================
) else (
    echo.
    echo [错误] 构建失败，请检查上方日志
)

pause
