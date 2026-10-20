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
echo Installing required packages...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Install failed. Check the messages above.
    pause
    exit /b 1
)
echo.
echo Done! Now double-click the run file.
pause
