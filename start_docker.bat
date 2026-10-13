@echo off
title IoT DDoS Monitor - Docker Launcher
echo ========================================================
echo   Launching IoT DDoS Monitor via Docker Compose
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Docker status...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop from the Start menu and try again.
    echo.
    pause
    exit /b 1
)

echo [2/3] Starting containers (backend, frontend, mosquitto)...
docker compose up -d

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start Docker containers.
    pause
    exit /b 1
)

echo.
echo [3/3] Opening dashboard in your browser...
timeout /t 2 >nul
start http://localhost:8080

echo.
echo ========================================================
echo   All services are running!
echo   Dashboard:  http://localhost:8080
echo   API Direct: http://localhost:5000/api/health
echo.
echo   To view logs:  docker compose logs -f
echo   To stop:       docker compose down
echo ========================================================
echo.
pause

