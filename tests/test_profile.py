import json
from dataclasses import asdict, replace

import pytest

from app import profile as prof
from app.profile import BUILTIN, Pid


def test_ut35a_defaults_match_manual():
    assert (BUILTIN.p_min, BUILTIN.p_max, BUILTIN.p_step) == (0.1, 999.9, 0.1)
    assert (BUILTIN.i_min, BUILTIN.i_max, BUILTIN.i_off) == (1.0, 6000.0, True)
    assert (BUILTIN.d_min, BUILTIN.d_max, BUILTIN.d_off) == (1.0, 6000.0, True)
    assert BUILTIN.period_ms == 200.0 and BUILTIN.reverse is True
    assert (BUILTIN.out_min, BUILTIN.out_max) == (0.0, 100.0)


def test_to_pid_proportional_band_seconds():
    assert prof.to_pid(BUILTIN, 10.0, 45.0, None) == Pid(kc=10.0, ti=45.0, td=0.0)
    assert prof.to_pid(BUILTIN, 20.0, None, 8.0) == Pid(kc=5.0, ti=None, td=8.0)


def test_to_pid_gain_and_minutes():
    p = replace(BUILTIN, name="x", p_mode="gain", i_unit="min", d_unit="min")
    assert prof.to_pid(p, 2.0, 1.5, 0.25) == Pid(kc=2.0, ti=90.0, td=15.0)
    rpm = replace(BUILTIN, name="y", i_unit="rpm")
    assert prof.to_pid(rpm, 50.0, 2.0, None) == Pid(kc=2.0, ti=30.0, td=0.0)


def test_from_pid_rounds_to_step():
    p, i, d, notes = prof.from_pid(BUILTIN, Pid(kc=4.9751, ti=94.0, td=8.14))
    assert (p, i, d, notes) == (20.1, 94.0, 8.0, [])


def test_from_pid_converts_units():
    g = replace(BUILTIN, name="x", p_mode="gain", p_min=0.01, p_max=100.0, p_step=0.01,
                i_unit="min", i_min=0.01, i_max=100.0, i_step=0.01,
                d_unit="min", d_min=0.01, d_max=100.0, d_step=0.01)
    assert prof.from_pid(g, Pid(kc=4.9751, ti=94.0, td=8.14))[:3] == (4.98, 1.57, 0.14)
    rpm = replace(BUILTIN, name="y", i_unit="rpm", i_min=0.01, i_max=100.0, i_step=0.01)
    assert prof.from_pid(rpm, Pid(kc=5.0, ti=30.0, td=0.0))[:3] == (20.0, 2.0, None)


def test_from_pid_clamps_and_explains():
    p, i, d, notes = prof.from_pid(BUILTIN, Pid(kc=0.05, ti=9000.0, td=0.2))
    assert (p, i, d) == (999.9, 6000.0, None)
    assert len(notes) == 3 and "範囲の外" in notes[0] and "OFF" in notes[2]


def test_from_pid_when_off_not_allowed():
    p = replace(BUILTIN, name="x", i_off=False, d_off=False)
    assert prof.from_pid(p, Pid(kc=5.0, ti=None, td=0.0))[:3] == (20.0, 6000.0, 1.0)


@pytest.mark.parametrize("text,expected", [("OFF", None), (" off ", None), ("", None), ("12.5", 12.5), ("1,200", 1200.0), ("ｏｆｆ", None), ("Ｏｆｆ", None)])
def test_parse_entry(text, expected):
    assert prof.parse_entry(text) == expected


def test_parse_entry_rejects_text():
    with pytest.raises(ValueError):
        prof.parse_entry("abc")


def test_check_entry():
    assert prof.check_entry(BUILTIN, 10.0, None, None) == []
    errs = prof.check_entry(BUILTIN, 0.0, 7000.0, 0.5)
    assert len(errs) == 3 and "0.1〜999.9" in errs[0]
    assert len(prof.check_entry(BUILTIN, None, 10.0, 10.0)) == 1
    strict = replace(BUILTIN, name="x", i_off=False)
    assert "OFF にできません" in prof.check_entry(strict, 10.0, None, None)[0]


def test_formatting():
    assert prof.format_p(BUILTIN, 20.1) == "20.1 %"
    assert prof.format_i(BUILTIN, 94.0) == "94 秒"
    assert prof.format_d(BUILTIN, None) == "OFF"
    g = replace(BUILTIN, name="x", p_mode="gain", p_step=0.01, i_unit="rpm", i_step=0.01)
    assert prof.format_p(g, 4.98) == "4.98" and prof.format_i(g, 2.0) == "2.00 回/分"
    assert prof.p_label(g) == "比例ゲイン P" and prof.p_label(BUILTIN) == "比例帯 P"


def test_save_and_list_roundtrip(tmp_path):
    mine = replace(BUILTIN, name="別の調節計: A/B", p_mode="gain", period_ms=100.0)
    path = prof.save_profile(mine, tmp_path)
    assert path.name == "別の調節計_ A_B.json"
    assert json.loads(path.read_text(encoding="utf-8"))["name"] == "別の調節計: A/B"
    assert prof.list_profiles(tmp_path) == [BUILTIN, mine]


def test_builtin_cannot_be_overwritten(tmp_path):
    with pytest.raises(ValueError):
        prof.save_profile(BUILTIN, tmp_path)
    with pytest.raises(ValueError):
        prof.save_profile(replace(BUILTIN, name="  "), tmp_path)


def test_broken_profile_file_is_skipped(tmp_path):
    folder = tmp_path / "profiles"
    folder.mkdir()
    (folder / "bad.json").write_text("{not json", encoding="utf-8")
    (folder / "old.json").write_text('{"name": "古い形式", "unknown_key": 1, "period_ms": 100}', encoding="utf-8")
    names = [p.name for p in prof.list_profiles(tmp_path)]
    assert names == [BUILTIN.name, "古い形式"]
    assert prof.list_profiles(tmp_path)[1].period_ms == 100.0


def test_settings_roundtrip(tmp_path):
    assert prof.load_settings(tmp_path) == {}
    prof.save_settings({"profile": "UT35A / UT32A", "p": "10.0"}, tmp_path)
    assert prof.load_settings(tmp_path) == {"profile": "UT35A / UT32A", "p": "10.0"}
    (tmp_path / "settings.json").write_text("[1, 2]", encoding="utf-8")
    assert prof.load_settings(tmp_path) == {}


def test_non_dict_json_file_is_skipped(tmp_path):
    folder = tmp_path / "profiles"
    folder.mkdir()
    (folder / "list.json").write_text("[1, 2]", encoding="utf-8")
    (folder / "str.json").write_text('"x"', encoding="utf-8")
    assert prof.list_profiles(tmp_path) == [BUILTIN]


def test_same_file_name_is_not_overwritten(tmp_path):
    prof.save_profile(replace(BUILTIN, name="A:B"), tmp_path)
    with pytest.raises(ValueError):
        prof.save_profile(replace(BUILTIN, name="A/B", period_ms=100.0), tmp_path)
    saved = json.loads((tmp_path / "profiles" / "A_B.json").read_text(encoding="utf-8"))
    assert saved["name"] == "A:B"


def test_same_name_can_be_saved_again(tmp_path):
    prof.save_profile(replace(BUILTIN, name="A:B", period_ms=100.0), tmp_path)
    prof.save_profile(replace(BUILTIN, name="A:B", period_ms=50.0), tmp_path)
    assert prof.list_profiles(tmp_path)[1].period_ms == 50.0


def test_broken_existing_file_can_be_overwritten(tmp_path):
    folder = tmp_path / "profiles"
    folder.mkdir()
    (folder / "A_B.json").write_text("{not json", encoding="utf-8")
    path = prof.save_profile(replace(BUILTIN, name="A/B"), tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["name"] == "A/B"


@pytest.mark.parametrize("key,value", [
    ("p_step", 0.0),
    ("i_unit", "hour"),
    ("i_off", "false"),
    ("p_min", 1000.0),
    ("period_ms", 0.0),
    ("name", "  "),
])
def test_invalid_values_in_file_are_skipped(tmp_path, key, value):
    folder = tmp_path / "profiles"
    folder.mkdir()
    data = asdict(BUILTIN)
    data["name"] = "テスト"
    data[key] = value
    (folder / "x.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert prof.list_profiles(tmp_path) == [BUILTIN]


def test_profile_file_name_replaces_forbidden_characters():
    assert prof.profile_file_name("A:B") == prof.profile_file_name("A/B") == "A_B.json"
