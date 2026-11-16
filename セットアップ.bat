@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo PID調整アドバイザー のセットアップを始めます。
echo （インターネットから部品をダウンロードします。数分かかります）
echo.
py -3.14 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.14 が見つかりません。
  echo https://www.python.org/downloads/windows/ から Python 3.14 をインストールしてから、もう一度実行してください。
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.14 -m venv .venv
  if errorlevel 1 (
    echo Python の環境を作れませんでした。
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo 部品のインストールに失敗しました。インターネットにつながっているか確かめてください。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m tools.make_shortcut
echo.
echo セットアップが終わりました。「PID調整アドバイザー」のショートカット、または 起動.bat で起動できます。
pause
