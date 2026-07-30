@echo off
title AutoAI Control Panel
echo ===================================================
echo             Starting AutoAI Platform
echo ===================================================
echo.

:: 1. Launch FastAPI Backend
echo [1/2] Launching Backend Server on port 8000...
start "AutoAI Backend" cmd /k "cd AutoAI\backend && ..\..\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: 2. Launch Vite Frontend
echo [2/2] Launching React/Vite Frontend on port 5173...
start "AutoAI Frontend" cmd /k "cd AutoAI\frontend && npm run dev -- --port 5173 --host 127.0.0.1"

echo.
echo ===================================================
echo  Both services have been launched in separate windows!
echo  - Backend: http://127.0.0.1:8000
echo  - Frontend: http://127.0.0.1:5173
echo ===================================================
echo.
pause
