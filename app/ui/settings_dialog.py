"""調節計の設定画面：プロファイルを選び、値を変えて保存する。"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QInputDialog, QLineEdit,
                             QMessageBox, QPushButton, QVBoxLayout, QWidget)

from app import profile as prof
from app.profile import BUILTIN, ControllerProfile
from app.ui.widgets import Card, Segmented, label

_NUMBER_FIELDS = ["p_min", "p_max", "p_step", "i_min", "i_max", "i_step", "d_min", "d_max", "d_step",
                  "period_ms", "out_min", "out_max"]


class SettingsDialog(QDialog):
    def __init__(self, profiles: list[ControllerProfile], current: ControllerProfile,
                 data_dir: Path | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("調節計の設定")
        self.setMinimumWidth(680)
        self._data_dir = data_dir
        self._profiles = list(profiles)
        self.selected_name = current.name

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        body.setObjectName("dialogBody")
        root.addWidget(body)
        box = QVBoxLayout(body)
        box.setContentsMargins(24, 20, 24, 20)
        box.setSpacing(14)

        top = QHBoxLayout()
        top.addWidget(label("プロファイル", "muted"))
        self.combo = QComboBox()
        top.addWidget(self.combo, 1)
        self.btn_copy = QPushButton("複製して新規")
        self.btn_reset = QPushButton("初期値に戻す")
        top.addWidget(self.btn_copy)
        top.addWidget(self.btn_reset)
        box.addLayout(top)

        box.addWidget(label("PIDの数値の表し方", "sectionTitle"))
        card = Card()
        self.p_mode = Segmented([("pb", "比例帯（%）"), ("gain", "比例ゲイン")], "pb")
        self.i_unit = Segmented([("s", "秒"), ("min", "分"), ("rpm", "回/分")], "s")
        self.d_unit = Segmented([("s", "秒"), ("min", "分")], "s")
        for text, seg in (("比例動作 P", self.p_mode), ("積分動作 I", self.i_unit), ("微分動作 D", self.d_unit)):
            row = QHBoxLayout()
            row.addWidget(label(text), 1)
            seg.setFixedWidth(300)
            row.addWidget(seg)
            card.box.addLayout(row)
        box.addWidget(card)

        box.addWidget(label("設定できる範囲", "sectionTitle"))
        card = Card()
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        for col, text in enumerate(("下限", "上限", "刻み"), start=1):
            grid.addWidget(label(text, "muted"), 0, col)
        self.edits: dict[str, QLineEdit] = {}
        self.i_off = QCheckBox("OFF を使える")
        self.d_off = QCheckBox("OFF を使える")
        for r, (key, text, off) in enumerate((("p", "P", None), ("i", "I", self.i_off), ("d", "D", self.d_off)), start=1):
            grid.addWidget(label(text), r, 0)
            for col, part in enumerate(("min", "max", "step"), start=1):
                e = QLineEdit()
                e.setFixedWidth(96)
                self.edits[f"{key}_{part}"] = e
                grid.addWidget(e, r, col)
            if off is not None:
                grid.addWidget(off, r, 4)
        grid.setColumnStretch(0, 1)
        card.box.addLayout(grid)
        box.addWidget(card)

        box.addWidget(label("計算のしかた", "sectionTitle"))
        card = Card()
        self.sp_response = QComboBox()
        self.sp_response.addItem("すぐに動く（標準PID制御モード）", "bump")
        self.sp_response.addItem("急には動かない（定値制御モード）", "bumpless")
        self.d_on = QComboBox()
        self.d_on.addItem("測定値の変化にかける（PV微分型）", "pv")
        self.d_on.addItem("偏差の変化にかける（偏差微分型）", "error")
        self.reverse = Segmented([("reverse", "逆動作（加熱）"), ("direct", "正動作（冷却）")], "reverse")
        self.reverse.setFixedWidth(300)
        for name in ("period_ms", "out_min", "out_max"):
            e = QLineEdit()
            e.setFixedWidth(96)
            self.edits[name] = e
        rows = [
            ("設定値を変えたときの出力", [self.sp_response]),
            ("微分動作のかけ方", [self.d_on]),
            ("動作の向き", [self.reverse]),
            ("制御周期", [self.edits["period_ms"], label("ミリ秒", "muted")]),
            ("出力の範囲", [self.edits["out_min"], label("〜", "muted"), self.edits["out_max"], label("%", "muted")]),
        ]
        for text, widgets in rows:
            row = QHBoxLayout()
            row.addWidget(label(text), 1)
            for w in widgets:
                if isinstance(w, QComboBox):
                    w.setFixedWidth(300)
                row.addWidget(w)
            card.box.addLayout(row)
        box.addWidget(card)

        self.note = label("", "muted", wrap=True)
        box.addWidget(self.note)
        box.addStretch(1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_cancel = QPushButton("キャンセル")
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("primary")
        self.btn_save.setDefault(True)
        for button in (self.btn_copy, self.btn_reset, self.btn_cancel):
            button.setAutoDefault(False)
        bottom.addWidget(self.btn_cancel)
        bottom.addWidget(self.btn_save)
        box.addLayout(bottom)

        self.combo.currentIndexChanged.connect(self._show_selected)
        self.btn_copy.clicked.connect(self._duplicate)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._save)
        self._fill_combo(current.name)

    def _fill_combo(self, select: str) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        for p in self._profiles:
            self.combo.addItem(p.name + ("（同梱・変更不可）" if p.name == BUILTIN.name else ""), p.name)
        index = max(self.combo.findData(select), 0)
        self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)
        self._show_selected()

    def _selected(self) -> ControllerProfile:
        name = self.combo.currentData()
        return next(p for p in self._profiles if p.name == name)

    def _show(self, p: ControllerProfile) -> None:
        self.p_mode.set_value(p.p_mode)
        self.i_unit.set_value(p.i_unit)
        self.d_unit.set_value(p.d_unit)
        for name in _NUMBER_FIELDS:
            self.edits[name].setText(f"{getattr(p, name):g}")
        self.i_off.setChecked(p.i_off)
        self.d_off.setChecked(p.d_off)
        self.sp_response.setCurrentIndex(self.sp_response.findData(p.sp_response))
        self.d_on.setCurrentIndex(self.d_on.findData(p.d_on))
        self.reverse.set_value("reverse" if p.reverse else "direct")

    def _show_selected(self) -> None:
        p = self._selected()
        self._show(p)
        editable = p.name != BUILTIN.name
        for w in (self.p_mode, self.i_unit, self.d_unit, self.i_off, self.d_off, self.sp_response, self.d_on,
                  self.reverse, self.btn_reset, self.btn_save, *self.edits.values()):
            w.setEnabled(editable)
        if editable:
            self.note.setText("値を変えて［保存］を押すと、このプロファイルに保存します。")
        else:
            self.note.setText("初期値は、横河電機 UT35A / UT32A の取扱説明書（IM 05P01D31-01EN）の記載に合わせています。"
                              "別の調節計で使うときは、「複製して新規」で値を変えて保存します。")

    def _duplicate(self) -> None:
        name, ok = QInputDialog.getText(self, "複製して新規", "新しいプロファイルの名前")
        if ok:
            self.duplicate_as(name)

    def duplicate_as(self, name: str) -> bool:
        name = name.strip()
        taken = {prof.profile_file_name(p.name) for p in [BUILTIN, *self._profiles]}
        if name == "" or prof.profile_file_name(name) in taken:
            QMessageBox.warning(self, "調節計の設定", "名前が空か、同じ名前（または同じファイル名になる名前）のプロファイルがすでにあります。")
            return False
        self._profiles.append(replace(self._selected(), name=name))
        self._fill_combo(name)
        return True

    def _reset(self) -> None:
        self._show(replace(BUILTIN, name=self._selected().name))

    def read_form(self) -> ControllerProfile:
        """画面の値からプロファイルを作る。誤りがあれば ValueError。"""
        values = {}
        for name in _NUMBER_FIELDS:
            try:
                values[name] = float(self.edits[name].text().replace(",", ""))
                if not math.isfinite(values[name]):
                    raise ValueError
            except ValueError:
                raise ValueError("数値の欄に、数値でない文字が入っています。") from None
        for key, text in (("p", "P"), ("i", "I"), ("d", "D")):
            if not (0 < values[f"{key}_min"] < values[f"{key}_max"]) or values[f"{key}_step"] <= 0:
                raise ValueError(f"{text} の範囲は「0 より大きい下限 ＜ 上限」、刻みは 0 より大きい値にしてください。")
        if values["period_ms"] <= 0:
            raise ValueError("制御周期は 0 より大きい値にしてください。")
        if not values["out_min"] < values["out_max"]:
            raise ValueError("出力の範囲は「下限 ＜ 上限」にしてください。")
        return ControllerProfile(
            name=self._selected().name, p_mode=self.p_mode.value(), i_unit=self.i_unit.value(), d_unit=self.d_unit.value(),
            i_off=self.i_off.isChecked(), d_off=self.d_off.isChecked(),
            sp_response=self.sp_response.currentData(), d_on=self.d_on.currentData(),
            reverse=self.reverse.value() == "reverse", **values)

    def _save(self) -> None:
        try:
            p = self.read_form()
            prof.save_profile(p, self._data_dir)
        except ValueError as e:
            QMessageBox.warning(self, "調節計の設定", str(e))
            return
        except OSError as e:
            QMessageBox.warning(self, "調節計の設定", f"保存できませんでした。\n{e}")
            return
        self.selected_name = p.name
        self.accept()
