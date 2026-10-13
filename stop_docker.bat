@echo off
title IoT DDoS Monitor - Docker Stop
echo ========================================================
echo   Stopping IoT DDoS Monitor Containers
echo ========================================================
echo.

cd /d "%~dp0"
docker compose down

echo.
echo Containers stopped successfully. (Database data preserved)
echo.
pause

