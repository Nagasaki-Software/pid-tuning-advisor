"""メイン画面。計算は app.analysis に任せ、ここは入力を集めて結果を表示するだけ。"""
from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

import math
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                             QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from app import APP_NAME, diagnose
from app import profile as prof
from app.analysis import AnalysisInput, AnalysisResult, run_analysis
from app.csv_loader import RawTable, Series, build_series, guess_columns, read_table
from app.tuning import PREF_LABELS
from app.ui.settings_dialog import SettingsDialog
from app.ui.widgets import Card, Rows, Segmented, label

pg.setConfigOptions(background="w", foreground="#5F5F66", antialias=True)

C_SP, C_PV, C_OUT, C_CUR, C_NEW = "#6E6E76", "#0A66D8", "#1B7F5C", "#C8641B", "#0A4FB0"
MIN_POINTS = 30
SCENES = [("auto", "自動判定"), (diagnose.SP_CHANGE, "設定値の変更"),
          (diagnose.HUNTING, "温度の揺れ（ハンチング）"), (diagnose.MANUAL, "手動で出力を変更")]
FOOTNOTE = ("提案は目安です。設定を変えたあとの記録でもう一度解析して、確かめてください。"
            "水の流量やバルブ開度が大きく違う運転では、その条件の記録で解析し直してください。")


def _plot(title_left: str) -> pg.PlotWidget:
    w = pg.PlotWidget()
    w.setMenuEnabled(False)
    w.showGrid(x=False, y=True, alpha=0.25)
    w.setLabel("left", title_left)
    w.getPlotItem().hideButtons()
    w.setMinimumHeight(150)
    return w


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path | None = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self._data_dir = data_dir
        self._path = ""
        self.table: RawTable | None = None
        self.series: Series | None = None
        self.result: AnalysisResult | None = None
        self.profiles = prof.list_profiles(data_dir)
        self.profile = self.profiles[0]
        self._syncing = False

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_toolbar())
        body = QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_center(), 1)
        body.addWidget(self._build_inspector())

        self._restore_settings()
        self._apply_profile_labels()
        self._clear_result()

    # ---- 画面の組み立て ----

    def _build_toolbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("toolbar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(10)
        self.btn_open = QPushButton("CSVを開く")
        self.file_label = label("CSV を開いてください", "muted")
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(180)
        self.btn_settings = QPushButton("設定…")
        self.btn_analyze = QPushButton("解析する")
        self.btn_analyze.setObjectName("primary")
        self.btn_analyze.setEnabled(False)
        lay.addWidget(self.btn_open)
        lay.addWidget(self.file_label, 1)
        lay.addWidget(label("調節計", "muted"))
        lay.addWidget(self.profile_combo)
        lay.addWidget(self.btn_settings)
        lay.addWidget(self.btn_analyze)
        self._fill_profile_combo()
        self.btn_open.clicked.connect(self.open_csv)
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_analyze.clicked.connect(self.analyze)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        return bar

    def _scroll(self, name: str, width: int) -> tuple[QScrollArea, QVBoxLayout]:
        area = QScrollArea()
        area.setObjectName(name)
        area.setWidgetResizable(True)
        area.setFixedWidth(width)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName(name + "Body")
        box = QVBoxLayout(inner)
        box.setContentsMargins(16, 16, 16, 16)
        box.setSpacing(8)
        area.setWidget(inner)
        return area, box

    def _field(self, grid: QGridLayout, row: int, text: str, widget: QWidget, unit: str = "") -> tuple:
        name = label(text)
        unit_label = label(unit, "muted")
        unit_label.setFixedWidth(34)
        grid.addWidget(name, row, 0)
        grid.addWidget(widget, row, 1)
        grid.addWidget(unit_label, row, 2)
        return name, unit_label

    def _build_sidebar(self) -> QWidget:
        area, box = self._scroll("sidebar", 310)

        box.addWidget(label("データの列", "sectionTitle"))
        card = Card()
        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        self.col_combos: dict[str, QComboBox] = {}
        for r, (key, text) in enumerate((("time", "時刻"), ("sp", "設定値"), ("out", "出力（%）"), ("pv", "測定値"))):
            c = QComboBox()
            c.setFixedWidth(150)
            self.col_combos[key] = c
            grid.addWidget(label(text), r, 0)
            grid.addWidget(c, r, 1, 1, 2)
            c.currentIndexChanged.connect(self._columns_changed)
        self.dt_edit = QLineEdit("1.0")
        self.dt_edit.setFixedWidth(96)
        self.dt_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.dt_name, self.dt_unit = self._field(grid, 4, "記録の間隔", self.dt_edit, "秒")
        self.dt_edit.editingFinished.connect(self._columns_changed)
        for w in (self.dt_name, self.dt_edit, self.dt_unit):
            w.setVisible(False)
        card.box.addLayout(grid)
        box.addWidget(card)
        self.data_note = label("", "muted", wrap=True)
        box.addWidget(self.data_note)

        box.addSpacing(8)
        box.addWidget(label("現在のPID設定", "sectionTitle"))
        card = Card()
        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        self.pid_edits: dict[str, QLineEdit] = {}
        self.pid_names, self.pid_units = {}, {}
        for r, key in enumerate(("p", "i", "d")):
            e = QLineEdit()
            e.setFixedWidth(96)
            e.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.pid_edits[key] = e
            e.textChanged.connect(lambda _t, e=e: self._mark(e, False))
            self.pid_names[key], self.pid_units[key] = self._field(grid, r, "", e)
        card.box.addLayout(grid)
        box.addWidget(card)
        box.addWidget(label("使っていない動作は「OFF」と入力します。", "muted", wrap=True))

        box.addSpacing(8)
        box.addWidget(label("入力レンジ", "sectionTitle"))
        card = Card()
        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        self.range_edits: dict[str, QLineEdit] = {}
        for r, (key, text) in enumerate((("lo", "下限"), ("hi", "上限"))):
            e = QLineEdit()
            e.setFixedWidth(96)
            e.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.range_edits[key] = e
            e.textChanged.connect(lambda _t, e=e: self._mark(e, False))
            self._field(grid, r, text, e)
        card.box.addLayout(grid)
        box.addWidget(card)
        box.addWidget(label("比例帯は、この幅に対する % です。調節計の入力レンジと同じ値を入れます。", "muted", wrap=True))

        box.addSpacing(8)
        box.addWidget(label("場面", "sectionTitle"))
        self.scene_combo = QComboBox()
        for key, text in SCENES:
            self.scene_combo.addItem(text, key)
        box.addWidget(self.scene_combo)

        box.addSpacing(8)
        box.addWidget(label("調整の好み", "sectionTitle"))
        self.pref = Segmented([(k, PREF_LABELS[k]) for k in ("stable", "normal", "fast")], "normal")
        box.addWidget(self.pref)

        box.addSpacing(8)
        self.aux_check = QCheckBox("補助機能を使用中の記録\n（オーバーシュート抑制など）")
        box.addWidget(self.aux_check)
        box.addStretch(1)
        return area

    def _build_center(self) -> QWidget:
        center = QWidget()
        center.setObjectName("center")
        box = QVBoxLayout(center)
        box.setContentsMargins(16, 16, 16, 16)
        box.setSpacing(12)

        card = Card()
        head = QHBoxLayout()
        head.addWidget(label("トレンド", "cardTitle"))
        head.addWidget(label("┄ 設定値　━ 測定値（青）　━ 出力（緑）", "muted"))
        head.addStretch(1)
        self.region_label = label("", "chip")
        head.addWidget(self.region_label)
        card.box.addLayout(head)
        self.plot_pv = _plot("測定値")
        self.plot_out = _plot("出力 %")
        self.plot_out.setXLink(self.plot_pv)
        self.plot_out.setLabel("bottom", "経過時間（秒）")
        self.curve_sp = self.plot_pv.plot(pen=pg.mkPen(C_SP, width=1.5, style=Qt.PenStyle.DashLine))
        self.curve_pv = self.plot_pv.plot(pen=pg.mkPen(C_PV, width=2))
        self.curve_out = self.plot_out.plot(pen=pg.mkPen(C_OUT, width=2))
        self.regions = []
        for w in (self.plot_pv, self.plot_out):
            region = pg.LinearRegionItem(brush=pg.mkBrush(10, 102, 216, 20), pen=pg.mkPen(C_PV, width=1.2))
            region.setZValue(-10)
            region.sigRegionChanged.connect(self._region_changed)
            w.addItem(region)
            self.regions.append(region)
        card.box.addWidget(self.plot_pv, 3)
        card.box.addWidget(self.plot_out, 2)
        box.addWidget(card, 3)

        card = Card()
        head = QHBoxLayout()
        self.pred_title = label("予想グラフ", "cardTitle")
        head.addWidget(self.pred_title)
        head.addWidget(label("┄ 現在の設定（橙）　━ 提案の設定（青）", "muted"))
        head.addStretch(1)
        card.box.addLayout(head)
        self.plot_pred = _plot("測定値")
        self.plot_pred.setLabel("bottom", "経過時間（秒）")
        self.curve_pred_sp = self.plot_pred.plot(pen=pg.mkPen(C_SP, width=1.5, style=Qt.PenStyle.DashLine))
        self.curve_pred_cur = self.plot_pred.plot(pen=pg.mkPen(C_CUR, width=1.8, style=Qt.PenStyle.DashLine))
        self.curve_pred_new = self.plot_pred.plot(pen=pg.mkPen(C_NEW, width=2.4))
        card.box.addWidget(self.plot_pred, 1)
        stats = QHBoxLayout()
        self.stat_cur = label("", "statBox")
        self.stat_new = label("", "statBoxNew")
        stats.addWidget(self.stat_cur, 1)
        stats.addWidget(self.stat_new, 1)
        card.box.addLayout(stats)
        box.addWidget(card, 2)
        return center

    def _build_inspector(self) -> QWidget:
        area, box = self._scroll("inspector", 360)
        box.setSpacing(12)

        card = Card()
        head = QHBoxLayout()
        head.addWidget(label("PIDの修正案", "cardTitle"))
        head.addStretch(1)
        self.pref_chip = label("", "chip")
        head.addWidget(self.pref_chip)
        card.box.addLayout(head)
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for col, text in ((1, "現在"), (3, "提案")):
            grid.addWidget(label(text, "muted"), 0, col, right)
        self.res_names, self.res_cur, self.res_new = {}, {}, {}
        for r, key in enumerate(("p", "i", "d"), start=1):
            self.res_names[key] = label("")
            self.res_cur[key] = label("—")
            self.res_new[key] = label("—", "proposed")
            grid.addWidget(self.res_names[key], r, 0)
            grid.addWidget(self.res_cur[key], r, 1, right)
            grid.addWidget(label("→", "muted"), r, 2)
            grid.addWidget(self.res_new[key], r, 3, right)
        card.box.addLayout(grid)
        self.reason_label = label("", wrap=True)
        card.box.addWidget(self.reason_label)
        self.btn_copy = QPushButton("提案値をコピー")
        self.btn_copy.clicked.connect(self.copy_proposal)
        card.box.addWidget(self.btn_copy)
        box.addWidget(card)

        card = Card("波形の診断")
        self.diag_rows = Rows()
        card.box.addWidget(self.diag_rows)
        self.direction_label = label("", wrap=True)
        card.box.addWidget(self.direction_label)
        box.addWidget(card)

        card = Card("推定した設備のくせ")
        self.model_rows = Rows()
        card.box.addWidget(self.model_rows)
        box.addWidget(card)

        self.warning_label = label("", "warning", wrap=True)
        box.addWidget(self.warning_label)
        box.addWidget(label(FOOTNOTE, "muted", wrap=True))
        box.addStretch(1)
        return area

    # ---- 調節計プロファイル ----

    def _fill_profile_combo(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for p in self.profiles:
            self.profile_combo.addItem(p.name)
        self.profile_combo.setCurrentIndex(max(self.profile_combo.findText(self.profile.name), 0))
        self.profile_combo.blockSignals(False)

    def _profile_changed(self) -> None:
        self.profile = self.profiles[max(self.profile_combo.currentIndex(), 0)]
        self._apply_profile_labels()
        self._clear_result()

    def _apply_profile_labels(self) -> None:
        p = self.profile
        texts = {"p": (prof.p_label(p), prof.p_unit(p)), "i": (prof.i_label(p), prof.I_UNIT_LABELS[p.i_unit]),
                 "d": (prof.d_label(p), prof.D_UNIT_LABELS[p.d_unit])}
        for key, (name, unit) in texts.items():
            self.pid_names[key].setText(name)
            self.pid_units[key].setText(unit)
            self.res_names[key].setText(name)

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.profiles, self.profile, self._data_dir, self)
        if dlg.exec():
            self.profiles = prof.list_profiles(self._data_dir)
            self.profile = next((p for p in self.profiles if p.name == dlg.selected_name), self.profiles[0])
            self._fill_profile_combo()
            self._apply_profile_labels()
            self._clear_result()

    # ---- CSV ----

    def open_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "CSVを開く", "", "CSV ファイル (*.csv *.txt);;すべてのファイル (*)")
        if path:
            self.load_csv(path)

    def load_csv(self, path: str) -> None:
        try:
            table = read_table(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, APP_NAME, f"CSV を読めませんでした。\n{e}")
            return
        self.table = table
        self._path = path
        guess = guess_columns(table.headers)
        fallback = {"time": None, "sp": 1, "out": 2, "pv": 3}
        self._syncing = True
        for key, combo in self.col_combos.items():
            combo.clear()
            if key == "time":
                combo.addItem("（なし）", None)
            for k, h in enumerate(table.headers):
                combo.addItem(h, k)
            want = guess[key] if guess[key] is not None else fallback[key]
            index = combo.findData(want) if want is not None and want < len(table.headers) else -1
            combo.setCurrentIndex(index if index >= 0 else 0)
        self._syncing = False
        self._columns_changed()

    def _columns_changed(self) -> None:
        if self._syncing or self.table is None:
            return
        no_time = self.col_combos["time"].currentData() is None
        for w in (self.dt_name, self.dt_edit, self.dt_unit):
            w.setVisible(no_time)
        self.series = None
        self._clear_result()
        dt_manual = None
        if no_time:
            try:
                dt_manual = float(self.dt_edit.text())
            except ValueError:
                dt_manual = 0.0             # build_series が「記録の間隔を入力してください」と知らせる
        try:
            self.series = build_series(self.table, self.col_combos["time"].currentData(), self.col_combos["sp"].currentData(),
                                       self.col_combos["out"].currentData(), self.col_combos["pv"].currentData(), dt_manual)
        except ValueError as e:
            self.data_note.setText(str(e))
        self._show_series()

    def _show_series(self) -> None:
        s = self.series
        self.btn_analyze.setEnabled(s is not None)
        if s is None:
            for c in (self.curve_sp, self.curve_pv, self.curve_out):
                c.setData([], [])
            self.file_label.setText(Path(self._path).name)
            self.region_label.setText("")
            return
        self.curve_sp.setData(s.t, s.sp)
        self.curve_pv.setData(s.t, s.pv)
        self.curve_out.setData(s.t, s.out)
        self.plot_pv.enableAutoRange()
        self.plot_out.enableAutoRange()
        for region in self.regions:
            region.setBounds((float(s.t[0]), float(s.t[-1])))
        self._set_region(float(s.t[0]), float(s.t[-1]))
        self.file_label.setText(f"{Path(self._path).name}（{len(s.t):,} 行・{s.dt:g} 秒間隔）")
        notes = list(s.notes)
        skipped = s.dropped + self.table.skipped
        if skipped:
            notes.insert(0, f"数値として読めない行を {skipped} 行捨てました。")
        self.data_note.setText(" ".join(notes))

    def _set_region(self, a: float, b: float) -> None:
        self._syncing = True
        for region in self.regions:
            region.setRegion((a, b))
        self._syncing = False
        self.region_label.setText(f"解析する区間　{a:.0f} 〜 {b:.0f} 秒")

    def _region_changed(self, region) -> None:
        if not self._syncing:
            self._set_region(*region.getRegion())

    def set_region(self, a: float, b: float) -> None:
        self._set_region(a, b)

    # ---- 解析 ----

    def _read_number(self, edit: QLineEdit, allow_off: bool) -> tuple[float | None, bool]:
        """入力欄を読む。戻り値は (値, 正しく読めたか)。"""
        try:
            if edit.text().strip() == "":
                raise ValueError("空欄")          # 空欄は OFF ではなく未入力
            value = prof.parse_entry(edit.text())
            ok = (value is not None and math.isfinite(value)) or (value is None and allow_off)
        except ValueError:
            value, ok = None, False
        self._mark(edit, not ok)
        return value, ok

    def _mark(self, edit: QLineEdit, invalid: bool) -> None:
        edit.setProperty("invalid", "true" if invalid else "false")
        edit.style().unpolish(edit)
        edit.style().polish(edit)

    def analyze(self) -> None:
        if self.series is None:
            return
        p, ok_p = self._read_number(self.pid_edits["p"], False)
        i, ok_i = self._read_number(self.pid_edits["i"], True)
        d, ok_d = self._read_number(self.pid_edits["d"], True)
        lo, ok_lo = self._read_number(self.range_edits["lo"], False)
        hi, ok_hi = self._read_number(self.range_edits["hi"], False)
        if not all((ok_p, ok_i, ok_d, ok_lo, ok_hi)):
            QMessageBox.warning(self, APP_NAME, "赤い欄に、数値（使っていない動作は OFF）を入力してください。")
            return
        errors = prof.check_entry(self.profile, p, i, d)
        pr = self.profile
        for key, v, lo_, hi_, off in (("p", p, pr.p_min, pr.p_max, False), ("i", i, pr.i_min, pr.i_max, pr.i_off),
                                      ("d", d, pr.d_min, pr.d_max, pr.d_off)):
            if (v is None and not off) or (v is not None and not lo_ <= v <= hi_):
                self._mark(self.pid_edits[key], True)
        if hi <= lo:
            errors.append("入力レンジは、上限が下限より大きくなるように入力してください。")
            self._mark(self.range_edits["hi"], True)
        if errors:
            QMessageBox.warning(self, APP_NAME, "\n".join(errors))
            return

        s = self.series
        a, b = self.regions[0].getRegion()
        sel = (s.t >= a) & (s.t <= b)
        if int(sel.sum()) < MIN_POINTS:
            QMessageBox.warning(self, APP_NAME, f"解析する区間のデータが {MIN_POINTS} 点未満です。区間を広げてください。")
            return
        inp = AnalysisInput(t=s.t[sel], sp=s.sp[sel], pv=s.pv[sel], out=s.out[sel], profile=self.profile, p=p, i=i, d=d,
                            range_lo=lo, range_hi=hi, scene=self.scene_combo.currentData(), pref=self.pref.value(),
                            aux_in_use=self.aux_check.isChecked())
        warn = crash = None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._show_result(run_analysis(inp))
        except ValueError as e:
            warn = str(e)
        except Exception:
            crash = traceback.format_exc()
        finally:
            QApplication.restoreOverrideCursor()
        if warn is not None:
            QMessageBox.warning(self, APP_NAME, warn)
        elif crash is not None:
            self._report_error(crash)

    def _report_error(self, text: str) -> None:
        folder = prof.data_dir(self._data_dir)
        note = f"記録先: {folder / 'error.log'}"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / "error.log", "a", encoding="utf-8") as f:
                f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{text}\n")
        except OSError:
            note = "（error.log に記録できませんでした）"
        QMessageBox.critical(self, APP_NAME, f"解析の途中でエラーが起きました。\n{note}\n\n{text[-600:]}")

    def _clear_result(self) -> None:
        self.result = None
        for key in ("p", "i", "d"):
            self.res_cur[key].setText("—")
            self.res_new[key].setText("—")
        self.pref_chip.setVisible(False)
        self.reason_label.setText("CSV を開いて［解析する］を押すと、ここに修正案が出ます。")
        self.btn_copy.setEnabled(False)
        self.btn_copy.setText("提案値をコピー")
        self.diag_rows.set_rows([])
        self.model_rows.set_rows([])
        self.direction_label.setText("")
        self.warning_label.setVisible(False)
        for c in (self.curve_pred_sp, self.curve_pred_cur, self.curve_pred_new):
            c.setData([], [])
        self.pred_title.setText("予想グラフ")
        self.stat_cur.setText("現在の設定\n—")
        self.stat_new.setText("提案の設定\n—")

    def _show_result(self, r: AnalysisResult) -> None:
        self.result = r
        for key, text in zip(("p", "i", "d"), r.current_text):
            self.res_cur[key].setText(text)
        for key, text in zip(("p", "i", "d"), r.proposed_text or ("—", "—", "—")):
            self.res_new[key].setText(text)
        self.pref_chip.setText(PREF_LABELS[self.pref.value()])
        self.pref_chip.setVisible(r.proposed_text is not None)
        self.reason_label.setText(r.reason or "推定した設備のくせから計算した値です。")
        self.btn_copy.setEnabled(r.proposed_text is not None)
        self.btn_copy.setText("提案値をコピー")
        self.diag_rows.set_rows(r.diag_rows)
        self.direction_label.setText(r.direction)
        rows = list(r.model_rows)
        if r.reproduce_fit is not None:
            rows.append(("現在の設定での再現", f"{max(r.reproduce_fit, 0):.0f} %"))
        self.model_rows.set_rows(rows)
        self.warning_label.setText("\n".join("・" + w for w in r.warnings))
        self.warning_label.setVisible(bool(r.warnings))

        pr = r.prediction
        if pr is None:
            for c in (self.curve_pred_sp, self.curve_pred_cur, self.curve_pred_new):
                c.setData([], [])
            self.pred_title.setText("予想グラフ（数値の提案が無いため表示できません）")
            self.stat_cur.setText("現在の設定\n—")
            self.stat_new.setText("提案の設定\n—")
            return
        self.curve_pred_sp.setData(pr.t, pr.sp)
        self.curve_pred_cur.setData(pr.t, pr.y_cur)
        self.curve_pred_new.setData(pr.t, pr.y_new)
        self.plot_pred.enableAutoRange()
        self.pred_title.setText(f"予想：設定値を {pr.sp[0]:g} → {pr.sp[-1]:g} に変えたとき")

        def stat(m) -> str:
            settle = "落ち着きません" if m.settle is None else f"{m.settle:.0f} 秒"
            return f"行き過ぎ {m.overshoot:.1f}　落ち着くまで {settle}"
        self.stat_cur.setText("現在の設定\n" + stat(pr.cur))
        self.stat_new.setText("提案の設定\n" + stat(pr.new))

    def copy_proposal(self) -> None:
        if self.result is None or self.result.proposed_text is None:
            return
        p = self.profile
        names = (prof.p_label(p), prof.i_label(p), prof.d_label(p))
        text = " / ".join(f"{n} = {v}" for n, v in zip(names, self.result.proposed_text))
        QGuiApplication.clipboard().setText(text)
        self.btn_copy.setText("コピーしました")

    # ---- 入力値の記憶 ----

    def _restore_settings(self) -> None:
        s = prof.load_settings(self._data_dir)
        self.profile = next((p for p in self.profiles if p.name == s.get("profile")), self.profiles[0])
        self._fill_profile_combo()
        defaults = {"p": "", "i": "", "d": "OFF", "lo": "0.0", "hi": "100.0"}
        for key, edit in {**self.pid_edits, **self.range_edits}.items():
            edit.setText(str(s.get(key, defaults[key])))
        self.pref.set_value(str(s.get("pref", "normal")))

    def closeEvent(self, event) -> None:
        s = {"profile": self.profile.name, "pref": self.pref.value()}
        for key, edit in {**self.pid_edits, **self.range_edits}.items():
            s[key] = edit.text()
        try:
            prof.save_settings(s, self._data_dir)
        except OSError:
            pass                    # 設定を覚えられないだけなので、閉じる動作は止めない
        super().closeEvent(event)
