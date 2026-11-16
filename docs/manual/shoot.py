"""取扱説明書の画面写真を撮る。

アプリの窓を実際に開き、見本データ（samples）で操作して、窓の中を画像にする。
設定やプロファイルは一時フォルダに書くので、ふだんの設定（%APPDATA%）には触れない。

使い方（アプリのフォルダで）:
    .venv\\Scripts\\python.exe docs\\manual\\shoot.py
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QPainter, QPen  # noqa: E402
from PyQt6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from app.main import create_app  # noqa: E402

OUT = Path(__file__).resolve().parent / "images"
SAMPLES = ROOT / "samples"
MARK = QColor("#D92D20")


def wait(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def rect_in(widget, top):
    p = widget.mapTo(top, QPoint(0, 0))
    return QRect(p.x(), p.y(), widget.width(), widget.height())


def save(image, name):
    image.save(str(OUT / name))
    print("撮影:", name)


def annotate(image, marks):
    """枠の左上に番号の丸を描く。marks は [(番号, QRect)]。"""
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Meiryo UI", 12)
    font.setBold(True)
    painter.setFont(font)
    for number, r in marks:
        painter.setPen(QPen(MARK, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)
        circle = QRect(max(r.x() - 13, 0), max(r.y() - 13, 0), 26, 26)  # 枠の角の外側（見出しに重ねない）
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(MARK)
        painter.drawEllipse(circle)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(number))
    painter.end()
    return image


def crop(window, widget, margin=0):
    r = rect_in(widget, window).adjusted(-margin, -margin, margin, margin)
    return window.grab(r)


def set_pid(w, p, i, d):
    for key, text in (("p", p), ("i", i), ("d", d)):
        w.pid_edits[key].setText(text)


def close_modal_later(ms):
    def act():
        box = QApplication.activeModalWidget()
        if box is not None:
            box.close()
    QTimer.singleShot(ms, act)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    app = create_app(sys.argv[:1])  # 変数に残さないとすぐに片付けられ、窓を作るときに落ちる
    from app.ui.main_window import MainWindow

    with tempfile.TemporaryDirectory() as tmp:
        w = MainWindow(data_dir=Path(tmp))
        w.resize(1440, 900)
        w.show()
        wait(1200)

        # 1. 読み込んで解析した画面（全体と、番号つき）
        set_pid(w, "10.0", "45", "OFF")
        w.load_csv(str(SAMPLES / "sp_change.csv"))
        wait(500)
        save(crop(w, w.centralWidget()).toImage(), "01_loaded.png")
        w.btn_analyze.click()
        wait(800)
        full = w.centralWidget().grab().toImage()
        save(full, "02_result.png")
        top = w.centralWidget()
        marks = [
            (1, rect_in(w.btn_open.parentWidget(), top)),
            (2, rect_in(w.col_combos["time"].parentWidget(), top)),
            (3, rect_in(w.pid_edits["p"].parentWidget(), top)),
            (4, rect_in(w.range_edits["lo"].parentWidget(), top)),
            (5, rect_in(w.plot_pv.parentWidget(), top)),
            (6, rect_in(w.plot_pred.parentWidget(), top)),
            (7, rect_in(w.res_new["p"].parentWidget(), top)),
            (8, rect_in(w.diag_rows.parentWidget(), top)),
            (9, rect_in(w.model_rows.parentWidget(), top)),
        ]
        save(annotate(full.copy(), marks), "00_overview.png")

        # 2. 部分の拡大
        save(crop(w, w.plot_pv.parentWidget()).toImage(), "03_trend.png")
        save(crop(w, w.res_new["p"].parentWidget()).toImage(), "04_proposal.png")
        save(crop(w, w.diag_rows.parentWidget()).toImage(), "05_diagnosis.png")
        save(crop(w, w.model_rows.parentWidget()).toImage(), "06_model.png")
        save(crop(w, w.plot_pred.parentWidget()).toImage(), "07_prediction.png")
        save(crop(w, w.findChild(QScrollArea, "sidebar")).toImage(), "08_sidebar.png")

        # 3. 提案が出ないとき（出力が動いていない区間）
        w.set_region(0, 100)
        w.btn_analyze.click()
        wait(800)
        save(crop(w, w.res_new["p"].parentWidget()).toImage(), "09_no_proposal.png")
        w.set_region(0, 900)

        # 4. 入力の誤り（赤い欄）
        w.pid_edits["p"].setText("abc")
        close_modal_later(500)
        w.btn_analyze.click()
        wait(400)
        save(crop(w, w.pid_edits["p"].parentWidget(), 4).toImage(), "10_invalid.png")
        w.pid_edits["p"].setText("10.0")

        # 5. ハンチングの見本
        set_pid(w, "2.5", "20", "OFF")
        w.load_csv(str(SAMPLES / "hunting.csv"))
        wait(500)
        w.btn_analyze.click()
        wait(800)
        save(w.centralWidget().grab().toImage(), "11_hunting.png")

        # 6. 調節計の設定
        def shoot_settings():
            dlg = QApplication.activeModalWidget()
            if dlg is None:
                return
            wait(300)
            save(dlg.grab().toImage(), "12_settings.png")
            dlg.reject()
        QTimer.singleShot(800, shoot_settings)
        w.open_settings()
        wait(300)
        w.close()


if __name__ == "__main__":
    main()
