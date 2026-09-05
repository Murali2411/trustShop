@echo off
cd /d "%~dp0"
start "RazorPay Backend" cmd /k "python -m pip install -r backend\requirements.txt && python -m uvicorn backend.server:app --host 127.0.0.1 --port 8003 --reload"
timeout /t 5 >nul
start "RazorPay Frontend" cmd /k "python -m http.server 8000 --bind 127.0.0.1"
timeout /t 2 >nul
start http://127.0.0.1:8000/
