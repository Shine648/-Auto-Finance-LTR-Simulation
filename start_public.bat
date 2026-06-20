@echo off
cd /d "%~dp0"
echo Credit Portfolio - Public Mode (0.0.0.0)
echo WARNING: Accessible from all network interfaces.
echo Make sure firewall allows port 8000.
echo.
pip install fastapi uvicorn numpy pandas scipy joblib
if not exist data\portfolio.json python generate_portfolio.py

REM Get local IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4.*[0-9]\.[0-9]"') do (
    set "local_ip=%%a"
    goto :got_ip
)
:got_ip
set "local_ip=%local_ip: =%"
echo Opening browser at http://%local_ip%:8000
start http://%local_ip%:8000

uvicorn main:app --host 0.0.0.0 --port 8000
pause