import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")      # テスト中は窓を画面に出さない


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    from app.main import create_app
    return QApplication.instance() or create_app([])


@pytest.fixture
def no_dialogs(monkeypatch):
    """メッセージの窓を出さずに、出そうとした文面を記録する。"""
    from PyQt6.QtWidgets import QMessageBox
    shown: list[str] = []
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda parent, title, text, *a, **k: shown.append(text))
    return shown
