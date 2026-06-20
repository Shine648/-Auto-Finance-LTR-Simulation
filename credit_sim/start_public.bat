@echo off
cd /d "%~dp0"
title Credit Portfolio - PUBLIC MODE (Cloudflare Tunnel)
color 0A

echo ============================================================
echo    Auto Finance LTR - Public Mode
echo    Cloudflare Tunnel + Static/Dynamic Dual Routing
echo ============================================================
echo.
echo [1/5] Installing dependencies...
pip install fastapi uvicorn numpy pandas scipy joblib cloudflared -q

echo.
echo [2/5] Checking portfolio data...
if not exist data\portfolio.json (
    echo Generating sample portfolio (40,000 loans)...
    python generate_portfolio.py
)

echo.
echo [3/5] Starting FastAPI backend on http://127.0.0.1:8000
echo.
start "FastAPI Backend" /min cmd /c "uvicorn main:app --host 127.0.0.1 --port 8000"

:: Wait for server to start
echo Waiting for server to initialize...
:wait_server
timeout /t 2 /nobreak >nul
curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 goto wait_server
echo FastAPI backend is running!

echo.
echo [4/5] Starting Cloudflare Tunnel...
echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║                                                          ║
echo ║  IMPORTANT: Copy the tunnel URL below!                   ║
echo ║                                                          ║
echo ║  Looks like: https://random-words.trycloudflare.com      ║
echo ║                                                          ║
echo ║  Then go to: http://localhost:8000/tunnel-config         ║
echo ║  to generate your _redirects config for Cloudflare Pages ║
echo ║                                                          ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

:: Try to find cloudflared
set CLOUDFLARED=cloudflared
where cloudflared >nul 2>&1
if errorlevel 1 (
    :: Check common install locations
    if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts\cloudflared.exe" (
        set "CLOUDFLARED=%USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts\cloudflared.exe"
    ) else if exist "%USERPROFILE%\.cloudflared\cloudflared.exe" (
        set "CLOUDFLARED=%USERPROFILE%\.cloudflared\cloudflared.exe"
    ) else if exist "C:\Program Files\cloudflared\cloudflared.exe" (
        set "CLOUDFLARED=C:\Program Files\cloudflared\cloudflared.exe"
    ) else (
        echo.
        echo ⚠ cloudflared not found!
        echo.
        echo Please install from: https://developers.cloudflare.com/cloudflare-one/
        echo connections/connect-networks/downloads/
        echo.
        echo Or download cloudflared.exe and place it in this directory:
        echo https://github.com/cloudflare/cloudflared/releases/latest
        echo.
        echo After installing, manually run:
        echo   cloudflared tunnel --url http://localhost:8000
        echo.
        echo The backend is already running at http://localhost:8000
        echo.
        pause
        exit /b 1
    )
)

:: Start tunnel and capture URL
echo Starting tunnel (Ctrl+C to stop tunnel only)...
echo.
echo Press any key to stop all services...
echo.
start "Cloudflare Tunnel" /min cmd /c "title Cloudflare Tunnel && "%CLOUDFLARED%" tunnel --url http://localhost:8000"

echo.
echo [5/5] Opening services...
echo.
:: Open the dashboard locally
timeout /t 3 /nobreak >nul
start http://127.0.0.1:8000

:: Open tunnel config page
timeout /t 1 /nobreak >nul
start http://127.0.0.1:8000/tunnel-config

echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║  SERVICES RUNNING:                                       ║
echo ║                                                          ║
echo ║  Local Dashboard:  http://localhost:8000                 ║
echo ║  Tunnel Config:    http://localhost:8000/tunnel-config   ║
echo ║                                                          ║
echo ║  === DUAL ROUTING ARCHITECTURE ===                       ║
echo ║                                                          ║
echo ║  Cloudflare Pages CDN serves:                            ║
echo ║   ✓ /index.html (and all static assets)                  ║
echo ║   ✓ /tunnel-config UI                                    ║
echo ║                                                          ║
║  Tunnel proxies to your local server:                      ║
echo ║   ✓ /health, /simulate, /macro-cycle                     ║
echo ║   ✓ /simulate/* (batch, cycle, presets)                  ║
echo ║   ✓ /sensitivity/*, /cache/*                             ║
echo ║                                                          ║
echo ║  Static pages stay on Cloudflare CDN (fast!)             ║
echo ║  API calls go through tunnel (to your Python backend)    ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

:: Wait for any key to stop
echo Press Ctrl+C in any terminal window or close the windows to stop.
echo.
echo Alternatively, run: taskkill /f /im uvicorn.exe ^& taskkill /f /im cloudflared.exe
echo.

:: Keep the window open
pause

:: Cleanup on exit
echo Shutting down services...
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im cloudflared.exe >nul 2>&1
echo Done.
exit /b 0