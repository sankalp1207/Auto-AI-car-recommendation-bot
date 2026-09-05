@echo off
setlocal enabledelayedexpansion
title AutoAI Control Panel

echo ===================================================
echo             Starting AutoAI Platform
echo ===================================================
echo.

:: Detect Project Structure
if exist "%~dp0backend" (
    set "PROJECT_ROOT=%~dp0"
    set "BACKEND_DIR=%~dp0backend"
    set "FRONTEND_DIR=%~dp0frontend"
) else if exist "%~dp0AutoAI\backend" (
    set "PROJECT_ROOT=%~dp0AutoAI"
    set "BACKEND_DIR=%~dp0AutoAI\backend"
    set "FRONTEND_DIR=%~dp0AutoAI\frontend"
) else (
    echo [ERROR] Could not find backend directory. Please run this script from the AutoAI project root.
    pause
    exit /b 1
)

:: Pre-flight Check: Virtual Environment
if not exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    echo [ERROR] Backend virtual environment not found at:
    echo         %BACKEND_DIR%\venv
    echo Please create it and install requirements before running.
    pause
    exit /b 1
)

:: Pre-flight Check: Backend .env Configuration
if not exist "%BACKEND_DIR%\.env" (
    echo [ERROR] Backend .env file not found at:
    echo         %BACKEND_DIR%\.env
    echo Please copy .env.example to .env and configure your credentials.
    pause
    exit /b 1
)

:: Pre-flight Check: Required Environment Variable Names (names only, no secrets logged)
echo [CHECK] Verifying required backend environment variables...
findstr /b /i "DATABASE_URL=" "%BACKEND_DIR%\.env" >nul 2>&1
if errorlevel 1 echo [WARNING] DATABASE_URL is not set in backend\.env
findstr /b /i "SECRET_KEY=" "%BACKEND_DIR%\.env" >nul 2>&1
if errorlevel 1 echo [WARNING] SECRET_KEY is not set in backend\.env
findstr /b /i "GEMINI_API_KEY=" "%BACKEND_DIR%\.env" >nul 2>&1
if errorlevel 1 echo [WARNING] GEMINI_API_KEY is not set in backend\.env
findstr /b /i "TELEGRAM_BOT_TOKEN=" "%BACKEND_DIR%\.env" >nul 2>&1
if errorlevel 1 echo [INFO] TELEGRAM_BOT_TOKEN is not set in backend\.env (Telegram bot will be skipped if not configured)

:: Pre-flight Check: Frontend Dependencies
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [ERROR] Frontend node_modules not found at:
    echo         %FRONTEND_DIR%\node_modules
    echo Please run "npm install" inside the frontend directory before running.
    pause
    exit /b 1
)

echo [OK] All preliminary checks passed.
echo.

:: 1. Launch FastAPI Backend
echo [1/3] Launching Backend Server on http://127.0.0.1:8000 ...
start "AutoAI Backend" cmd /k "cd /d "%BACKEND_DIR%" && .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: 2. Launch Telegram Bot
findstr /b /i "TELEGRAM_BOT_TOKEN=" "%BACKEND_DIR%\.env" >nul 2>&1
if not errorlevel 1 (
    echo [2/3] Launching Telegram Bot ...
    start "AutoAI Telegram Bot" cmd /k "cd /d "%BACKEND_DIR%" && .\venv\Scripts\python.exe bot.py"
) else (
    echo [2/3] Skipping Telegram Bot (TELEGRAM_BOT_TOKEN not configured).
)

:: 3. Launch Frontend
echo [3/3] Launching Frontend Development Server ...
start "AutoAI Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo.
echo ===================================================
echo  Services launched successfully in separate windows!
echo  - Backend API:   http://127.0.0.1:8000
echo  - API Docs:      http://127.0.0.1:8000/docs
echo  - Telegram Bot:  Active via polling (bot.py)
echo  - Frontend:      http://localhost:8080 (or http://localhost:5173)
echo ===================================================
echo.
pause
