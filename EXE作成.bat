@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 開発用：EXE 版を dist\PID調整アドバイザー に作る（先に セットアップ.bat と、pip install -r requirements-dev.txt が必要）
".venv\Scripts\python.exe" -m PyInstaller --onedir --windowed --noconfirm --clean ^
  --name "PID調整アドバイザー" --icon "app\assets\app.ico" --paths . ^
  --add-data "app\assets;app\assets" --add-data "app\ui\style.qss;app\ui" ^
  app\main.py
if errorlevel 1 (
  echo EXE の作成に失敗しました。
  pause
  exit /b 1
)
set "OUT=dist\PID調整アドバイザー"
copy /y "docs\exe\はじめにお読みください.txt" "%OUT%\" >nul
copy /y "docs\manual\取扱説明書.pdf" "%OUT%\" >nul
copy /y "LICENSE" "%OUT%\" >nul
copy /y "THIRD_PARTY_NOTICES.md" "%OUT%\" >nul
robocopy "samples" "%OUT%\samples" /e /njh /njs /nfl /ndl >nul
echo.
echo 完了しました。%OUT%\PID調整アドバイザー.exe を確かめてください。
pause
