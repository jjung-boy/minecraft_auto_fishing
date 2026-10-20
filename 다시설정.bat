@echo off
rem Keep this file ASCII-only: cmd misreads non-ASCII batch files saved with LF line endings.
cd /d "%~dp0"
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    echo [ERROR] Python not found.
    echo Install it from https://www.python.org/downloads/
    echo and CHECK "Add python.exe to PATH" on the first install screen.
    pause
    exit /b 1
)
%PY% -c "import cv2, mss, keyboard, pyautogui" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Required packages are not installed.
    echo Double-click the install file first.
    pause
    exit /b 1
)
%PY% autofish.py --setup
pause
