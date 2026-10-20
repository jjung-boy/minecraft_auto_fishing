@echo off
chcp 65001 >nul
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python 이 없습니다.
    echo https://www.python.org/downloads/ 에서 설치하세요.
    echo 설치할 때 첫 화면 아래 "Add python.exe to PATH" 를 꼭 체크하세요.
    pause
    exit /b 1
)
echo 필요한 패키지를 설치합니다...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [오류] 설치에 실패했습니다. 위 메시지를 확인하세요.
    pause
    exit /b 1
)
echo.
echo 설치 완료! 이제 실행.bat 을 더블클릭하세요.
pause
