@echo off
chcp 65001 > nul
title Football SIM - Git Manager
cd /d "C:\Users\luczkab\Desktop\moje\GGGRA202608\GIT\football_sim"

REM Sprawdź czy Python jest zainstalowany
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python nie znaleziony! Zainstaluj Python z python.org
    pause
    exit /b 1
)

REM Uruchom aplikację
python "%~dp0git_manager.py"
pause