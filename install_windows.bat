@echo off
echo === Installing Transcribe ===
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

REM Check project directory
if not exist "pyproject.toml" (
    echo ERROR: Run this script from the project directory
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
if not exist "venv" (
    python -m venv venv
)

echo [2/3] Activating environment...
call venv\Scripts\activate.bat

echo [3/3] Installing dependencies...
pip install --upgrade pip -q
pip install -e . -q

echo.
echo === Installation Complete ===
echo.
echo To use Transcribe:
echo   1. Activate: venv\Scripts\activate.bat
echo   2. Check:    transcribe check
echo   3. Devices:  transcribe devices
echo   4. Record:   transcribe start
echo.
pause
