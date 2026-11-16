"""SVG から Windows 用のアイコンファイル（.ico）を作る。

使い方（プロジェクトのフォルダで）:  .venv\\Scripts\\python.exe -m tools.make_icon
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent.parent / "app" / "assets"
SIZES = [16, 24, 32, 48, 64, 128, 256]
SMALL_MAX = 32          # この大きさ以下は簡略版の絵を使う


def render_png(svg_path: Path, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(str(svg_path)).render(painter)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def build_ico(out_path: Path, assets: Path = ASSETS) -> None:
    images = [(s, render_png(assets / ("icon_small.svg" if s <= SMALL_MAX else "icon.svg"), s)) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    out_path.write_bytes(header + entries + blobs)


def read_ico_sizes(path: Path) -> list[int]:
    data = path.read_bytes()
    _, kind, count = struct.unpack_from("<HHH", data, 0)
    if kind != 1:
        raise ValueError("アイコンファイルではありません。")
    return [struct.unpack_from("<B", data, 6 + 16 * k)[0] or 256 for k in range(count)]


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    target = ASSETS / "app.ico"
    build_ico(target)
    sys.stdout.buffer.write(f"{target} を作りました: {read_ico_sizes(target)}\n".encode("utf-8"))
