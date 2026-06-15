@echo off
title 多人测试
cd /d "%~dp0"

if not exist "main.py" (
    echo ERROR: main.py not found
    echo Please put this .bat in the project/ folder
    pause
    exit /b
)

:menu
cls
echo ============================================
echo   Plane War - Multiplayer Test Launcher
echo ============================================
echo.
echo   s - Start Server
echo   1 - Start Client 1
echo   2 - Start Client 2
echo   3 - Start Client 3
echo   4 - Start Client 4
echo   a - Start ALL (server + 4 clients)
echo   q - Quit
echo.
set /p choice=Choice: 

if "%choice%"=="s" start "Server" python server/server.py
if "%choice%"=="1" start "Player1" python main.py
if "%choice%"=="2" start "Player2" python main.py
if "%choice%"=="3" start "Player3" python main.py
if "%choice%"=="4" start "Player4" python main.py

if "%choice%"=="a" (
    start "Server" python server/server.py
    timeout /t 2 /nobreak >nul
    start "Player1" python main.py
    timeout /t 1 /nobreak >nul
    start "Player2" python main.py
    timeout /t 1 /nobreak >nul
    start "Player3" python main.py
    timeout /t 1 /nobreak >nul
    start "Player4" python main.py
)

if "%choice%"=="q" exit /b
goto menu
