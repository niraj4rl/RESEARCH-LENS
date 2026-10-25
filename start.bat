@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ==========================================================
echo         Starting ResearchLens (One-Command Launcher)
echo ==========================================================
echo.

:: Detect Python executable
set "PY_EXE="
if exist "backend\venv\Scripts\python.exe" (
    set "PY_EXE=backend\venv\Scripts\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 set "PY_EXE=python"
)

if not defined PY_EXE (
    where py >nul 2>&1
    if !errorlevel! equ 0 set "PY_EXE=py"
)

if not defined PY_EXE (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

"%PY_EXE%" run.py
