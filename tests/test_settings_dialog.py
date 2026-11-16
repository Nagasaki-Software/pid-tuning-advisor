from dataclasses import replace

import pytest

from app import profile as prof
from app.profile import BUILTIN
from app.ui.settings_dialog import SettingsDialog


def test_builtin_profile_is_shown_read_only(qapp, tmp_path):
    dlg = SettingsDialog([BUILTIN], BUILTIN, tmp_path)
    assert dlg.edits["p_max"].text() == "999.9" and dlg.edits["period_ms"].text() == "200"
    assert dlg.p_mode.value() == "pb" and dlg.reverse.value() == "reverse"
    assert not dlg.edits["p_max"].isEnabled() and not dlg.btn_save.isEnabled()
    assert dlg.btn_copy.isEnabled()


def test_duplicate_edit_and_save(qapp, tmp_path, no_dialogs):
    dlg = SettingsDialog([BUILTIN], BUILTIN, tmp_path)
    assert dlg.duplicate_as("別の調節計")
    assert dlg.edits["p_max"].isEnabled() and dlg.btn_save.isEnabled()
    dlg.p_mode.set_value("gain")
    dlg.i_unit.set_value("min")
    dlg.edits["period_ms"].setText("100")
    dlg.reverse.set_value("direct")
    dlg.d_off.setChecked(False)
    dlg.btn_save.click()
    assert dlg.result() == 1 and dlg.selected_name == "別の調節計" and no_dialogs == []
    saved = prof.list_profiles(tmp_path)[1]
    assert (saved.name, saved.p_mode, saved.i_unit, saved.period_ms, saved.reverse, saved.d_off) == \
        ("別の調節計", "gain", "min", 100.0, False, False)


def test_duplicate_rejects_empty_or_existing_name(qapp, tmp_path, no_dialogs):
    dlg = SettingsDialog([BUILTIN], BUILTIN, tmp_path)
    assert not dlg.duplicate_as("  ")
    assert not dlg.duplicate_as(BUILTIN.name)
    assert len(no_dialogs) == 2 and dlg.combo.count() == 1


def test_invalid_numbers_are_not_saved(qapp, tmp_path, no_dialogs):
    dlg = SettingsDialog([BUILTIN], BUILTIN, tmp_path)
    dlg.duplicate_as("X")
    for field, value in (("p_max", "abc"), ("p_max", "0.05"), ("i_step", "0"), ("period_ms", "-1"), ("out_max", "0")):
        original = dlg.edits[field].text()
        dlg.edits[field].setText(value)
        dlg.btn_save.click()
        dlg.edits[field].setText(original)
    assert len(no_dialogs) == 5 and dlg.result() == 0
    assert len(prof.list_profiles(tmp_path)) == 1


def test_reset_restores_builtin_values_but_keeps_name(qapp, tmp_path):
    dlg = SettingsDialog([BUILTIN], BUILTIN, tmp_path)
    dlg.duplicate_as("X")
    dlg.edits["p_max"].setText("50")
    dlg.p_mode.set_value("gain")
    dlg.btn_reset.click()
    assert dlg.edits["p_max"].text() == "999.9" and dlg.p_mode.value() == "pb"
    assert dlg.read_form().name == "X"


@pytest.mark.parametrize("field, value", [
    ("period_ms", "nan"), ("p_max", "inf"), ("out_max", "-inf"), ("i_max", "nan"),
])
def test_nan_and_inf_are_not_saved(qapp, tmp_path, no_dialogs, field, value):
    dlg = SettingsDialog([BUILTIN], BUILTIN, tmp_path)
    dlg.duplicate_as("X")
    dlg.edits[field].setText(value)
    dlg.btn_save.click()
    assert len(no_dialogs) == 1 and dlg.result() == 0
    assert [p.name for p in prof.list_profiles(tmp_path)] == [BUILTIN.name]


def test_duplicate_rejects_same_file_name(qapp, tmp_path, no_dialogs):
    dlg = SettingsDialog([BUILTIN, replace(BUILTIN, name="A:B")], BUILTIN, tmp_path)
    count = dlg.combo.count()
    assert not dlg.duplicate_as("A/B")
    assert len(no_dialogs) == 1 and "同じファイル名" in no_dialogs[0]
    assert dlg.combo.count() == count


def test_save_is_default_button_and_copy_is_not(qapp, tmp_path):
    dlg = SettingsDialog([BUILTIN], BUILTIN, tmp_path)
    assert dlg.btn_save.isDefault()
    assert not dlg.btn_copy.autoDefault()


def test_oserror_on_save_shows_warning(qapp, tmp_path, no_dialogs, monkeypatch):
    dlg = SettingsDialog([BUILTIN], BUILTIN, tmp_path)
    dlg.duplicate_as("X")

    def fail(profile, base=None):
        raise OSError("書けません")
    monkeypatch.setattr(prof, "save_profile", fail)
    dlg.btn_save.click()
    assert len(no_dialogs) == 1 and "保存できませんでした" in no_dialogs[0]
    assert dlg.result() == 0
