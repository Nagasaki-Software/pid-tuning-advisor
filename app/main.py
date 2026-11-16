"""起動。"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime

from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from app import APP_NAME
from app import profile as prof
from app.ui.widgets import ASSETS, load_style

APP_USER_MODEL_ID = "PidTuningAdvisor.App"


def _set_taskbar_identity() -> None:
    """Python で動かしても、タスクバーに自分のアイコンが出るようにする（Windows のみ）。"""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)


def _excepthook(exc_type, exc, tb) -> None:
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    folder = prof.data_dir()
    note = f"記録先: {folder / 'error.log'}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "error.log", "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{text}\n")
    except OSError:
        note = "（error.log に記録できませんでした）"
    QMessageBox.critical(None, APP_NAME, f"エラーが起きました。\n{note}\n\n{text[-600:]}")


def create_app(argv: list[str]) -> QApplication:
    _set_taskbar_identity()
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    family = "Meiryo UI" if "Meiryo UI" in QFontDatabase.families() else "Meiryo"
    app.setFont(QFont(family))
    app.setWindowIcon(QIcon(str(ASSETS / "app.ico")))
    app.setStyleSheet(load_style())
    return app


def main() -> None:
    app = create_app(sys.argv)
    sys.excepthook = _excepthook
    from app.ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
