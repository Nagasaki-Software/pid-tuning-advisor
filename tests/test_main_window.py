import pytest
from PyQt6.QtGui import QGuiApplication

from app import profile as prof
from app.ui.main_window import MainWindow
from tools.make_samples import make_samples


@pytest.fixture
def samples(tmp_path):
    return make_samples(tmp_path / "samples")


def _window(tmp_path, p="10.0", i="45", d="OFF"):
    w = MainWindow(data_dir=tmp_path / "appdata")
    for key, text in (("p", p), ("i", i), ("d", d)):
        w.pid_edits[key].setText(text)
    return w


def test_starts_empty_with_ut35a_labels(qapp, tmp_path):
    w = MainWindow(data_dir=tmp_path)
    assert w.windowTitle() == "PID調整アドバイザー" and not qapp.windowIcon().isNull()
    assert not w.btn_analyze.isEnabled() and not w.btn_copy.isEnabled()
    assert (w.pid_names["p"].text(), w.pid_units["p"].text()) == ("比例帯 P", "%")
    assert (w.pid_names["i"].text(), w.pid_units["i"].text()) == ("積分時間 I", "秒")
    assert (w.range_edits["lo"].text(), w.range_edits["hi"].text(), w.pid_edits["d"].text()) == ("0.0", "100.0", "OFF")
    assert qapp.font().family() in ("Meiryo UI", "Meiryo")


def test_load_sample_and_analyze(qapp, tmp_path, samples, no_dialogs):
    w = _window(tmp_path)
    w.load_csv(str(samples[0]))
    assert w.btn_analyze.isEnabled() and "901 行・1 秒間隔" in w.file_label.text()
    assert [w.col_combos[k].currentText() for k in ("time", "sp", "out", "pv")] == ["日時", "設定値", "出力", "水温"]
    assert len(w.curve_pv.getData()[0]) == 901 and "0 〜 900 秒" in w.region_label.text()
    w.btn_analyze.click()
    assert no_dialogs == []
    assert (w.res_cur["p"].text(), w.res_cur["i"].text(), w.res_cur["d"].text()) == ("10.0 %", "45 秒", "OFF")
    assert w.res_new["p"].text().endswith(" %") and w.res_new["i"].text().endswith(" 秒")
    assert dict(w.diag_rows.texts())["場面"] == "設定値の変更"
    assert "当てはまり具合" in dict(w.model_rows.texts())
    assert len(w.curve_pred_new.getData()[0]) > 100 and "行き過ぎ" in w.stat_new.text()
    assert "60 → 65" in w.pred_title.text()
    w.btn_copy.click()
    assert QGuiApplication.clipboard().text().startswith("比例帯 P = ")


@pytest.mark.parametrize("index,scene,p,i", [(1, "温度の揺れ（ハンチング）", "2.5", "20"), (2, "手動で出力を変更", "10.0", "45")])
def test_other_scenes(qapp, tmp_path, samples, no_dialogs, index, scene, p, i):
    w = _window(tmp_path, p=p, i=i)
    w.load_csv(str(samples[index]))
    w.btn_analyze.click()
    assert no_dialogs == [] and dict(w.diag_rows.texts())["場面"] == scene
    assert w.res_new["p"].text() != "—"


def test_region_limits_the_analysis(qapp, tmp_path, samples, no_dialogs):
    w = _window(tmp_path)
    w.load_csv(str(samples[0]))
    w.set_region(0, 100)                                    # 設定値を変える前だけ：出力が動いていない
    assert "0 〜 100 秒" in w.region_label.text()
    w.btn_analyze.click()
    assert w.res_new["p"].text() == "—" and "数値の提案は出せません" in w.reason_label.text()
    w.set_region(0, 10)
    w.btn_analyze.click()
    assert any("30 点未満" in m for m in no_dialogs)


def test_invalid_entries_are_marked_and_not_analyzed(qapp, tmp_path, samples, no_dialogs):
    w = _window(tmp_path, p="abc")
    w.load_csv(str(samples[0]))
    w.btn_analyze.click()
    assert w.result is None and w.pid_edits["p"].property("invalid") == "true" and len(no_dialogs) == 1
    w.pid_edits["p"].setText("5000")
    w.btn_analyze.click()
    assert w.result is None and "0.1〜999.9" in no_dialogs[1]
    assert w.pid_edits["p"].property("invalid") == "true"
    w.pid_edits["p"].setText("10")
    w.range_edits["hi"].setText("-5")
    w.btn_analyze.click()
    assert w.result is None and "入力レンジ" in no_dialogs[2]


def test_changing_columns_rebuilds_or_reports(qapp, tmp_path, samples, no_dialogs):
    w = _window(tmp_path)
    w.load_csv(str(samples[0]))
    w.col_combos["pv"].setCurrentIndex(0)                   # 測定値に日時の列を選ぶ
    assert not w.btn_analyze.isEnabled() and "2 行未満" in w.data_note.text()
    w.col_combos["pv"].setCurrentIndex(3)
    assert w.btn_analyze.isEnabled()
    w.col_combos["time"].setCurrentIndex(0)                 # 時刻なし → 記録の間隔を使う
    w.dt_edit.setText("2")
    w.dt_edit.editingFinished.emit()
    assert "2 秒間隔" in w.file_label.text()


def test_unreadable_file_shows_message(qapp, tmp_path, no_dialogs):
    bad = tmp_path / "bad.csv"
    bad.write_text("これは CSV ではありません\n", encoding="utf-8")
    w = _window(tmp_path)
    w.load_csv(str(bad))
    assert len(no_dialogs) == 1 and "CSV を読めませんでした" in no_dialogs[0] and w.table is None


def test_entries_are_remembered(qapp, tmp_path):
    w = _window(tmp_path, p="12.5", i="80", d="6")
    w.pref.set_value("stable")
    w.close()
    assert prof.load_settings(tmp_path / "appdata")["p"] == "12.5"
    again = MainWindow(data_dir=tmp_path / "appdata")
    assert (again.pid_edits["p"].text(), again.pid_edits["d"].text(), again.pref.value()) == ("12.5", "6", "stable")


def test_profile_changes_labels(qapp, tmp_path):
    from dataclasses import replace
    prof.save_profile(replace(prof.BUILTIN, name="ゲイン式", p_mode="gain", i_unit="min"), tmp_path / "appdata")
    w = MainWindow(data_dir=tmp_path / "appdata")
    w.profile_combo.setCurrentIndex(1)
    assert (w.pid_names["p"].text(), w.pid_units["p"].text(), w.pid_units["i"].text()) == ("比例ゲイン P", "", "分")
    assert w.res_names["p"].text() == "比例ゲイン P"


def test_blank_entry_is_not_off(qapp, tmp_path, samples, no_dialogs):
    w = _window(tmp_path, p="10.0", i="", d="OFF")
    w.load_csv(str(samples[0]))
    w.btn_analyze.click()
    assert w.result is None and w.pid_edits["i"].property("invalid") == "true" and len(no_dialogs) == 1
    w.pid_edits["i"].setText("off")
    w.btn_analyze.click()
    assert len(no_dialogs) == 1 and w.result is not None and w.res_cur["i"].text() == "OFF"


@pytest.mark.parametrize("bad", ["nan", "inf"])
def test_nan_and_inf_are_unreadable(qapp, tmp_path, samples, no_dialogs, bad):
    w = _window(tmp_path)
    w.load_csv(str(samples[0]))
    w.range_edits["hi"].setText(bad)
    w.btn_analyze.click()
    assert w.result is None and w.range_edits["hi"].property("invalid") == "true" and len(no_dialogs) == 1


def test_editing_clears_invalid_mark(qapp, tmp_path, samples, no_dialogs):
    w = _window(tmp_path, p="abc")
    w.load_csv(str(samples[0]))
    w.btn_analyze.click()
    assert w.pid_edits["p"].property("invalid") == "true"
    w.pid_edits["p"].setText("10")
    assert w.pid_edits["p"].property("invalid") == "false"


def test_unexpected_error_is_logged(qapp, tmp_path, samples, no_dialogs, monkeypatch):
    from PyQt6.QtWidgets import QApplication

    def boom(inp):
        raise RuntimeError("想定外")
    monkeypatch.setattr("app.ui.main_window.run_analysis", boom)
    w = _window(tmp_path)
    w.load_csv(str(samples[0]))
    w.btn_analyze.click()
    assert len(no_dialogs) == 1 and "解析の途中でエラーが起きました" in no_dialogs[0]
    log = (tmp_path / "appdata" / "error.log").read_text(encoding="utf-8")
    assert "RuntimeError" in log and "想定外" in log
    assert QApplication.overrideCursor() is None


def test_interval_field_hidden_until_no_time_column(qapp, tmp_path, samples):
    w = MainWindow(data_dir=tmp_path)
    assert w.dt_edit.isHidden()
    w.load_csv(str(samples[0]))
    assert w.dt_edit.isHidden()
    w.col_combos["time"].setCurrentIndex(0)
    assert not w.dt_edit.isHidden()


def test_copy_button_text_resets(qapp, tmp_path, samples, no_dialogs):
    w = _window(tmp_path)
    w.load_csv(str(samples[0]))
    w.btn_analyze.click()
    w.btn_copy.click()
    assert w.btn_copy.text() == "コピーしました"
    w.load_csv(str(samples[1]))
    assert w.btn_copy.text() == "提案値をコピー"


def test_error_is_reported_even_when_log_cannot_be_written(qapp, tmp_path, no_dialogs):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    w = MainWindow(data_dir=blocker)
    w._report_error("Traceback: 想定外")
    assert len(no_dialogs) == 1 and "記録できませんでした" in no_dialogs[0]


def test_rows_replacement_leaves_no_visible_old_labels(qapp):
    from PyQt6.QtWidgets import QLabel
    from app.ui.widgets import Rows
    rows = Rows()
    rows.set_rows([("a", "1"), ("b", "2"), ("c", "3"), ("d", "4")])
    rows.set_rows([("e", "5"), ("f", "6")])
    assert len([lab for lab in rows.findChildren(QLabel) if not lab.isHidden()]) == 4
