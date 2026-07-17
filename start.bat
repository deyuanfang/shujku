@echo off
chcp 65001 >nul
title PersonalKB - 个人知识库

echo ========================================
echo   PersonalKB - 个人知识库管理系统
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: Check Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    pause
    exit /b 1
)

echo [1/3] 检查后端依赖...
cd /d "%~dp0backend"
if not exist "venv" (
    echo   创建虚拟环境...
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -q fastapi uvicorn sqlalchemy aiosqlite jieba scikit-learn numpy python-multipart aiofiles pydantic pydantic-settings python-dotenv 2>nul
echo   后端依赖就绪

echo [2/3] 安装前端依赖...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo   首次运行，安装前端依赖 (可能需要几分钟)...
    call npm install
)
echo   前端依赖就绪

echo [3/3] 启动服务...

:: Start backend
cd /d "%~dp0backend"
start "PersonalKB-Backend" /MIN venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765

:: Wait for backend
echo   等待后端启动...
timeout /t 3 /nobreak >nul

:: Start frontend
cd /d "%~dp0frontend"
start "PersonalKB-Frontend" /MIN cmd /c "npx vite --host 127.0.0.1 --port 5173"

:: Wait and open browser
timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo ========================================
echo   启动完成！浏览器已打开
echo   后端: http://localhost:8765
echo   前端: http://localhost:5173
echo ========================================
echo.
echo 按任意键停止所有服务...
pause >nul

taskkill /FI "WINDOWTITLE eq PersonalKB-Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq PersonalKB-Frontend*" /T /F >nul 2>&1
echo 服务已停止
