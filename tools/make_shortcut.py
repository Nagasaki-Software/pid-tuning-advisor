"""アイコン付きのショートカットを、プロジェクトのフォルダに作る。

使い方: ショートカット作成.bat をダブルクリック
"""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "PID調整アドバイザー"


def _q(path: Path | str) -> str:
    """PowerShell の文字列として安全に書く。"""
    return "'" + str(path).replace("'", "''") + "'"


def make_shortcut(root: Path = ROOT) -> Path:
    lnk = root / f"{NAME}.lnk"
    pythonw = root / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        raise FileNotFoundError(f"{pythonw} がありません。先に .venv を用意してください。")
    script = "\n".join([
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({_q(lnk)})",
        f"$s.TargetPath = {_q(pythonw)}",
        "$s.Arguments = '-m app.main'",
        f"$s.WorkingDirectory = {_q(root)}",
        f"$s.IconLocation = {_q(str(root / 'app' / 'assets' / 'app.ico') + ',0')}",
        f"$s.Description = {_q(NAME)}",
        "$s.Save()",
    ])
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded], check=True)
    return lnk


if __name__ == "__main__":
    path = make_shortcut()
    sys.stdout.buffer.write(f"{path} を作りました。\n".encode("utf-8"))
