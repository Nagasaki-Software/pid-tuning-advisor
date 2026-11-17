import numpy as np
import pytest

from app.csv_loader import build_series, guess_columns, read_table

BASIC = "日時,SP,OUT,PV\n2026/11/14 10:00:00,60,40.0,60.1\n2026/11/14 10:00:01,60,40.5,60.2\n2026/11/14 10:00:02,65,41.0,60.3\n"


def _write(tmp_path, text, encoding="utf-8", name="a.csv"):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return path


@pytest.mark.parametrize("encoding,expected", [("utf-8", "utf-8-sig"), ("utf-8-sig", "utf-8-sig"), ("cp932", "cp932")])
def test_reads_japanese_headers_in_each_encoding(tmp_path, encoding, expected):
    table = read_table(_write(tmp_path, BASIC, encoding))
    assert table.headers == ["日時", "SP", "OUT", "PV"]
    assert table.encoding == expected and len(table.rows) == 3 and table.skipped == 0


def test_path_with_japanese_and_space(tmp_path):
    folder = tmp_path / "記録 データ"
    folder.mkdir()
    assert len(read_table(_write(folder, BASIC, name="温度 トレンド.csv")).rows) == 3


def test_basic_series(tmp_path):
    s = build_series(read_table(_write(tmp_path, BASIC)), 0, 1, 2, 3)
    assert np.allclose(s.t, [0, 1, 2]) and s.dt == 1.0
    assert np.allclose(s.sp, [60, 60, 65]) and np.allclose(s.out, [40.0, 40.5, 41.0]) and np.allclose(s.pv, [60.1, 60.2, 60.3])
    assert s.dropped == 0 and s.notes == []


def test_recorder_style_preamble_and_unit_row(tmp_path):
    text = "記録計 A\n開始,2026/11/14\n\n時刻,CH1,CH2,CH3\n,℃,%,℃\n10:00:00,60,40,60.1\n10:00:01,60,41,60.2\n10:00:02,60,42,60.3\n"
    table = read_table(_write(tmp_path, text, "cp932"))
    assert table.headers == ["時刻", "CH1 ℃", "CH2 %", "CH3 ℃"]
    assert len(table.rows) == 3


def test_no_header_gets_generated_names(tmp_path):
    table = read_table(_write(tmp_path, "0,60,40,60.1\n1,60,41,60.2\n2,60,42,60.3\n"))
    assert table.headers == ["列1", "列2", "列3", "列4"]


@pytest.mark.parametrize("sep", ["\t", ";"])
def test_other_delimiters(tmp_path, sep):
    table = read_table(_write(tmp_path, BASIC.replace(",", sep)))
    assert table.headers == ["日時", "SP", "OUT", "PV"]


def test_rows_with_wrong_column_count_are_skipped(tmp_path):
    table = read_table(_write(tmp_path, BASIC + "終わり\n"))
    assert len(table.rows) == 3 and table.skipped == 1


def test_no_numbers_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="数値の列が見つかりません"):
        read_table(_write(tmp_path, "これは\nCSV では\nありません\n"))


def test_unknown_encoding_is_an_error(tmp_path):
    path = tmp_path / "bin.csv"
    path.write_bytes(b"\xff\xfe\x00\x81\x00\xff" * 10)
    with pytest.raises(ValueError, match="文字コード"):
        read_table(path)


@pytest.mark.parametrize("stamp", [
    "2026/11/14 10:00:0{}", "2026-11-14 10:00:0{}", "2026-11-14T10:00:0{}", "2026/11/14 10:00:0{}.000", "10:00:0{}", "{}", "{}.0",
])
def test_time_formats(tmp_path, stamp):
    text = "t,SP,OUT,PV\n" + "".join(f"{stamp.format(k)},60,40,60.{k}\n" for k in range(4))
    s = build_series(read_table(_write(tmp_path, text)), 0, 1, 2, 3)
    assert np.allclose(s.t, [0, 1, 2, 3])


def test_clock_time_across_midnight(tmp_path):
    text = "t,SP,OUT,PV\n23:59:58,60,40,60\n23:59:59,60,40,60\n00:00:00,60,40,60\n00:00:01,60,40,60\n"
    s = build_series(read_table(_write(tmp_path, text)), 0, 1, 2, 3)
    assert np.allclose(s.t, [0, 1, 2, 3]) and s.notes == []


def test_no_time_column_uses_manual_interval(tmp_path):
    table = read_table(_write(tmp_path, "SP,OUT,PV\n60,40,60.1\n60,41,60.2\n60,42,60.3\n"))
    s = build_series(table, None, 0, 1, 2, dt_manual=0.5)
    assert np.allclose(s.t, [0, 0.5, 1.0]) and s.dt == 0.5
    with pytest.raises(ValueError, match="記録の間隔"):
        build_series(table, None, 0, 1, 2)


def test_bad_cells_are_dropped_and_counted(tmp_path):
    text = "t,SP,OUT,PV\n0,60,40,60\n1,60,40,****\n2,60,,60\n3,60,40,nan\n" + "".join(f"{k},60,40,6{k}\n" for k in range(4, 10))
    s = build_series(read_table(_write(tmp_path, text)), 0, 1, 2, 3)
    assert s.dropped == 3 and len(s.t) == 10 and s.dt == 1.0    # 抜けた時刻は等間隔に直して埋める
    assert np.allclose(s.pv[[0, 4, 9]], [60, 64, 69])
    assert any("等間隔" in n for n in s.notes)


def test_unsorted_and_duplicate_times(tmp_path):
    text = "t,SP,OUT,PV\n0,60,40,60\n2,60,40,62\n1,60,40,61\n2,60,40,99\n3,60,40,63\n"
    s = build_series(read_table(_write(tmp_path, text)), 0, 1, 2, 3)
    assert np.allclose(s.t, [0, 1, 2, 3]) and np.allclose(s.pv, [60, 61, 62, 63])
    assert len(s.notes) == 2 and "並べ直し" in s.notes[0] and "同じ時刻" in s.notes[1]


def test_uneven_interval_is_resampled(tmp_path):
    text = "t,SP,OUT,PV\n0,60,40,60\n1,60,40,61\n2,60,40,62\n3,60,40,63\n5,60,40,65\n6,60,40,66\n"
    s = build_series(read_table(_write(tmp_path, text)), 0, 1, 2, 3)
    assert np.allclose(s.t, [0, 1, 2, 3, 4, 5, 6]) and np.allclose(s.pv, [60, 61, 62, 63, 64, 65, 66])


def test_text_column_chosen_as_value_is_an_error(tmp_path):
    table = read_table(_write(tmp_path, BASIC))
    with pytest.raises(ValueError, match="2 行未満"):
        build_series(table, 0, 0, 2, 3)
    with pytest.raises(ValueError, match="時刻の列を読めません"):
        build_series(read_table(_write(tmp_path, "名前,SP,OUT,PV\nA,60,40,60\nB,60,40,61\nC,60,40,62\n")), 0, 1, 2, 3)


def test_guess_columns():
    assert guess_columns(["日時", "SP", "OUT", "PV"]) == {"time": 0, "sp": 1, "out": 2, "pv": 3}
    assert guess_columns(["Time", "設定値", "バルブ開度", "水温"]) == {"time": 0, "sp": 1, "out": 2, "pv": 3}
    assert guess_columns(["列1", "列2"]) == {"time": None, "sp": None, "out": None, "pv": None}


def test_description_rows_do_not_join_the_headers(tmp_path):
    text = "記録計 A,,,\n開始,2026/11/14,,\n時刻,SP,OUT,PV\n10:00:00,60,40,60.1\n10:00:01,60,41,60.2\n10:00:02,60,42,60.3\n"
    table = read_table(_write(tmp_path, text, "cp932"))
    assert table.headers == ["時刻", "SP", "OUT", "PV"]
    assert guess_columns(table.headers) == {"time": 0, "sp": 1, "out": 2, "pv": 3}


def test_unreadable_file_is_a_japanese_value_error(tmp_path):
    with pytest.raises(ValueError, match="ファイルを開けません"):
        read_table(tmp_path / "無い.csv")
    with pytest.raises(ValueError, match="ファイルを開けません"):
        read_table(tmp_path)


def test_time_jump_in_numeric_column_is_not_shifted(tmp_path):
    text = "t,SP,OUT,PV\n50000,60,40,62\n50001,60,40,63\n0,60,40,60\n1,60,40,61\n"
    s = build_series(read_table(_write(tmp_path, text)), 0, 1, 2, 3)
    assert s.t[0] == 0 and s.t[-1] == 50001
    assert np.allclose(s.pv[:2], [60, 61]) and s.pv[-1] == 63
    assert any("並べ直し" in n for n in s.notes)
