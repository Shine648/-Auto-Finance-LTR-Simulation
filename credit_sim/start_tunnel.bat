@echo off
cd /d "%~dp0"
title Cloudflare Tunnel - Auto Finance LTR
color 0B

echo ============================================================
echo    Cloudflare Tunnel Launcher
echo    Start tunnel to expose localhost:8000 to the internet
echo ============================================================
echo.

:: Check if backend is running
echo Checking if backend is running on port 8000...
curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    echo ⚠ Backend not running! Start it first with:
    echo   start_local.bat
    echo.
    echo Or start both together with:
    echo   start_public.bat
    echo.
    set /p "choice=Start backend now? (Y/n): "
    if /i "!choice!" NEQ "n" (
        echo Starting FastAPI backend...
        start "FastAPI Backend" /min cmd /c "uvicorn main:app --host 127.0.0.1 --port 8000"
        echo Waiting for backend...
        :wait_server
        timeout /t 2 /nobreak >nul
        curl -s http://127.0.0.1:8000/health >nul 2>&1
        if errorlevel 1 goto wait_server
        echo ✅ Backend is running!
    ) else (
        echo Please start the backend first, then run this script again.
        pause
        exit /b 1
    )
)

:: Find cloudflared
set CLOUDFLARED=cloudflared
where cloudflared >nul 2>&1
if errorlevel 1 (
    if exist "%USERPROFILE%\.cloudflared\cloudflared.exe" (
        set "CLOUDFLARED=%USERPROFILE%\.cloudflared\cloudflared.exe"
    ) else if exist "C:\Program Files\cloudflared\cloudflared.exe" (
        set "CLOUDFLARED=C:\Program Files\cloudflared\cloudflared.exe"
    ) else if exist "cloudflared.exe" (
        set "CLOUDFLARED=cloudflared.exe"
    ) else (
        echo ⚠ cloudflared not found!
        echo.
        echo Download cloudflared.exe from:
        echo https://github.com/cloudflare/cloudflared/releases/latest
        echo.
        echo Place it in this directory or add to PATH.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║                                                        ║
echo ║  Tunnel starting...                                    ║
echo ║                                                        ║
echo ║  Your tunnel URL will appear above.                    ║
echo ║  Copy the "https://xxx.trycloudflare.com" URL!         ║
echo ║                                                        ║
echo ║  Then paste it into the Tunnel Config UI:              ║
echo ║  http://localhost:8000/tunnel-config                    ║
echo ║                                                        ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

"%CLOUDFLARED%" tunnel --url http://127.0.0.1:8000

echo.
echo Tunnel stopped.
pause