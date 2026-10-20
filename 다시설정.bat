@echo off
chcp 65001 >nul
cd /d "%~dp0"
python autofish.py --setup
pause
