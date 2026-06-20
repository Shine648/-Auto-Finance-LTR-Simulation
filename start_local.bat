@echo off
cd /d "%~dp0"
echo Credit Portfolio - Local Mode (127.0.0.1)
pip install fastapi uvicorn numpy pandas scipy joblib
if not exist data\portfolio.json python generate_portfolio.py
start http://127.0.0.1:8000
uvicorn main:app --host 127.0.0.1 --port 8000
pause