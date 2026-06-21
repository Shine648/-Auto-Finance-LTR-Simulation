@echo off
cd /d "%~dp0"
title Cloudflare Tunnel - Auto Finance LTR
color 0B

echo ============================================================
echo    Cloudflare Tunnel Launcher
echo    Expose localhost:8000 to the internet
echo ============================================================
echo.

:: Check if backend is running on port 8000
echo [1/2] Checking backend...
curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    echo [..] Backend not running. Starting FastAPI...
    start "FastAPI Backend" /min cmd /c "uvicorn main:app --host 127.0.0.1 --port 8000"
    echo [..] Waiting for backend...
    :wait_server
    timeout /t 2 /nobreak >nul
    curl -s http://127.0.0.1:8000/health >nul 2>&1
    if errorlevel 1 goto wait_server
)
echo [OK] Backend is running on http://127.0.0.1:8000
echo.

echo [2/2] Starting Cloudflare Tunnel...
echo.

:: Find cloudflared
set CLOUDFLARED=
if exist "%~dp0cloudflared.exe" set "CLOUDFLARED=%~dp0cloudflared.exe"
if not defined CLOUDFLARED if exist "%~dp0..\cloudflared.exe" set "CLOUDFLARED=%~dp0..\cloudflared.exe"
if not defined CLOUDFLARED where cloudflared >nul 2>&1 && set "CLOUDFLARED=cloudflared"
if not defined CLOUDFLARED if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts\cloudflared.exe" set "CLOUDFLARED=%USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts\cloudflared.exe"
if not defined CLOUDFLARED if exist "%USERPROFILE%\.cloudflared\cloudflared.exe" set "CLOUDFLARED=%USERPROFILE%\.cloudflared\cloudflared.exe"
if not defined CLOUDFLARED if exist "C:\Program Files\cloudflared\cloudflared.exe" set "CLOUDFLARED=C:\Program Files\cloudflared\cloudflared.exe"

if not defined CLOUDFLARED (
    echo [WARN] cloudflared not found!
    echo.
    echo Expected locations:
    echo   - %~dp0cloudflared.exe
    echo   - %~dp0..\cloudflared.exe
    echo   - PATH environment
    echo   - %%USERPROFILE%%\.cloudflared\
    echo.
    echo Download: https://github.com/cloudflare/cloudflared/releases/latest
    echo.
    echo Backend is running at http://127.0.0.1:8000
    echo.
    pause
    exit /b 1
)

echo Found cloudflared at: %CLOUDFLARED%
echo.
echo -----------------------------------------------------------
echo   Tunnel URL will appear above after a few seconds.
echo   Copy the https://xxx.trycloudflare.com URL.
echo.
echo   Then open http://127.0.0.1:8000/tunnel-config
echo   to generate your _redirects config.
echo -----------------------------------------------------------
echo.
echo Press Ctrl+C to stop tunnel.
echo.

"%CLOUDFLARED%" tunnel --url http://127.0.0.1:8000

echo.
echo Tunnel stopped.
pause