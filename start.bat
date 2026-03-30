@echo off
chcp 65001 >nul
cd /d %~dp0
title Power News DJ

echo [1/3] Checking Ollama...
curl -s http://localhost:11434 >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama server...
    start /min "" "C:\Users\syyty\AppData\Local\Programs\Ollama\ollama.exe" serve
    timeout /t 4 /nobreak >nul
)

echo [2/3] Freeing port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [3/3] Starting Power News DJ...
echo   http://localhost:8000
echo   Stop: Ctrl+C
echo.
start "" http://localhost:8000
"C:\Users\syyty\anaconda3\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
