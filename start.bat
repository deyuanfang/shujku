@echo off
chcp 65001 >nul 2>&1
title PersonalKB
cd /d "%~dp0"
set BACKEND_PORT=18765
set FRONTEND_PORT=5173

echo.
echo   ======================================
echo     PersonalKB - 个人知识库管理系统
echo   ======================================
echo.

:: ── Check Python ──────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [错误] 未找到 Python
    echo   请安装 Python 3.10+ 并勾选"Add to PATH"
    echo   下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   Python: %%v

:: ── Check Node ────────────────────────────
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [错误] 未找到 Node.js
    echo   请安装 Node.js 18+
    echo   下载: https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=1" %%v in ('node --version 2^>^&1') do echo   Node:   %%v
echo.

:: ── Backend deps ──────────────────────────
echo   [1/4] 检查后端依赖...
cd /d "%~dp0backend"
python -c "import fastapi,uvicorn,sqlalchemy,jieba,sklearn" >nul 2>&1
if %errorlevel% neq 0 (
    echo   正在安装后端依赖 (约1-2分钟)...
    pip install fastapi "uvicorn[standard]" sqlalchemy aiosqlite jieba scikit-learn numpy python-multipart aiofiles pydantic pydantic-settings python-dotenv -q 2>nul
    python -c "import fastapi,uvicorn,sqlalchemy,jieba" >nul 2>&1
    if %errorlevel% neq 0 (
        echo   [失败] 请手动安装: cd backend ^&^& pip install -r requirements.txt
        pause
        exit /b 1
    )
)
echo   后端依赖: OK

:: ── Frontend deps ─────────────────────────
echo   [2/4] 检查前端依赖...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo   首次运行，安装前端依赖 (约2-5分钟，仅需一次)...
    call npm install --silent 2>nul
    if not exist "node_modules" (
        echo   [失败] npm install 出错
        echo   请手动运行: cd frontend ^&^& npm install
        pause
        exit /b 1
    )
)
if not exist "dist\index.html" (
    echo   编译前端 (约30秒，仅需一次)...
    call node node_modules\vite\bin\vite.js build 2>nul
)
echo   前端依赖: OK

:: ── Kill old processes ────────────────────
echo   [3/4] 清理旧进程...
python -c "import subprocess,re;out=subprocess.run(['netstat','-ano'],capture_output=True,text=True).stdout;[subprocess.run(['taskkill','/PID',l.split()[-1],'/F'],capture_output=True) for l in out.split('\n') if '127.0.0.1:%BACKEND_PORT%' in l and 'LISTENING' in l]" 2>nul
python -c "import subprocess,re;out=subprocess.run(['netstat','-ano'],capture_output=True,text=True).stdout;[subprocess.run(['taskkill','/PID',l.split()[-1],'/F'],capture_output=True) for l in out.split('\n') if '127.0.0.1:%FRONTEND_PORT%' in l and 'LISTENING' in l]" 2>nul
timeout /t 1 /nobreak >nul

:: ── Start backend ─────────────────────────
echo   [4/4] 启动服务...
cd /d "%~dp0backend"
start "" /MIN python -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT% --log-level warning
echo   后端启动中 (端口 %BACKEND_PORT%)...

:: Wait for backend (Python health check)
set /a RETRY=0
:wait_backend
timeout /t 1 /nobreak >nul
python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:%BACKEND_PORT%/health',timeout=2)" >nul 2>&1
if %errorlevel% equ 0 goto backend_ok
set /a RETRY+=1
if %RETRY% lss 12 goto wait_backend
echo   [警告] 后端启动超时
goto start_frontend

:backend_ok
echo   后端: http://127.0.0.1:%BACKEND_PORT% [OK]

:: ── Start frontend ────────────────────────
:start_frontend
cd /d "%~dp0frontend"
start "" /MIN node node_modules\vite\bin\vite.js --host 127.0.0.1 --port %FRONTEND_PORT% --strictPort
echo   前端启动中 (端口 %FRONTEND_PORT%)...

set /a RETRY=0
:wait_frontend
timeout /t 1 /nobreak >nul
python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:%FRONTEND_PORT%',timeout=2)" >nul 2>&1
if %errorlevel% equ 0 goto frontend_ok
set /a RETRY+=1
if %RETRY% lss 12 goto wait_frontend
echo   [警告] 前端启动超时
goto done

:frontend_ok
echo   前端: http://127.0.0.1:%FRONTEND_PORT% [OK]

:: ── Open browser ──────────────────────────
start http://127.0.0.1:%FRONTEND_PORT%

:done
echo.
echo   ======================================
echo     PersonalKB 已启动!
echo     后端: http://127.0.0.1:%BACKEND_PORT%
echo     前端: http://127.0.0.1:%FRONTEND_PORT%
echo   ======================================
echo.
echo   [按任意键停止所有服务]
pause >nul

:: Cleanup
python -c "import subprocess,re;out=subprocess.run(['netstat','-ano'],capture_output=True,text=True).stdout;[subprocess.run(['taskkill','/PID',l.split()[-1],'/F'],capture_output=True) for l in out.split('\n') if f'127.0.0.1:%BACKEND_PORT%' in l and 'LISTENING' in l]" 2>nul
python -c "import subprocess,re;out=subprocess.run(['netstat','-ano'],capture_output=True,text=True).stdout;[subprocess.run(['taskkill','/PID',l.split()[-1],'/F'],capture_output=True) for l in out.split('\n') if f'127.0.0.1:%FRONTEND_PORT%' in l and 'LISTENING' in l]" 2>nul
echo   服务已停止
