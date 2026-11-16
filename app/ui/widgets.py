"""画面の小さな部品（Mac風の枠、切り替えボタン、項目と値の行）。"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def load_style() -> str:
    text = (Path(__file__).resolve().parent / "style.qss").read_text(encoding="utf-8")
    return text.replace("{ASSETS}", ASSETS.as_posix())


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class Card(QFrame):
    """角の丸い白い枠。"""

    def __init__(self, title: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(14, 12, 14, 12)
        self.box.setSpacing(8)
        if title:
            self.box.addWidget(label(title, "cardTitle"))


class Segmented(QWidget):
    """横に並んだ切り替えボタン。"""

    changed = pyqtSignal(str)

    def __init__(self, options: list[tuple[str, str]], value: str):
        super().__init__()
        self.setObjectName("segment")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._buttons: dict[str, QPushButton] = {}
        for key, text in options:
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
            lay.addWidget(b, 1)
            self._group.addButton(b)
            self._buttons[key] = b
        self.set_value(value)

    def value(self) -> str:
        return next(k for k, b in self._buttons.items() if b.isChecked())

    def set_value(self, key: str) -> None:
        self._buttons.get(key, next(iter(self._buttons.values()))).setChecked(True)


class Rows(QWidget):
    """「項目名 … 値」の行を並べる。"""

    def __init__(self):
        super().__init__()
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setVerticalSpacing(7)
        self._grid.setColumnStretch(1, 1)

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        while self._grid.count():
            w = self._grid.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        for r, (name, value) in enumerate(rows):
            self._grid.addWidget(label(name, "muted"), r, 0, Qt.AlignmentFlag.AlignTop)
            v = label(value, wrap=True)
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            self._grid.addWidget(v, r, 1)

    def texts(self) -> list[tuple[str, str]]:
        items = [self._grid.itemAt(k).widget().text() for k in range(self._grid.count())]
        return list(zip(items[0::2], items[1::2]))
