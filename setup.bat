@echo off
chcp 65001 >nul
title FlyWars - Setup
echo =======================================================
echo   FlyWars - Huan Jing An Zhuang
echo =======================================================
echo.
echo 1. An zhuang pygame-ce (zhi chi ARM64)
pip install pygame-ce
if %ERRORLEVEL% neq 0 (
    echo.
    echo [SHI BAI] pip install shi bai, qing jian zha Python huo wang luo
    pause
    exit /b 1
)
echo.
echo 2. Yan zheng an zhuang
python -c "import pygame; print('pygame-ce', pygame.version.ver, 'OK')"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [SHI BAI] pygame-ce wu fa dao ru
    pause
    exit /b 1
)
echo.
echo =======================================================
echo   Wan cheng! Yun xing:  python main.py --ai
echo   huo zhe shuang ji run.bat
echo =======================================================
pause
