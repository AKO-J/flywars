@echo off
chcp 65001 >nul
title FlyWars - AI Demo
cd /d "%~dp0"
echo =======================================================
echo   FlyWars - AI Zi Dong Jia Shi Yan Shi
echo =======================================================
echo.
echo Qi dong zhong...
python main.py --ai
if %ERRORLEVEL% neq 0 (
    echo.
    echo [SHI BAI] Yun xing shi bai
    echo Qing xian yun xing setup.bat an zhuang huan jing
    pause
)
