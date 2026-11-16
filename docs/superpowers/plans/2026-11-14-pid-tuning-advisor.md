# PID調整アドバイザー Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 温度調節計の記録（設定値・出力%・測定値）と現在の P・I・D から、P・I・D の修正案を示す Windows アプリ（初版 0.1.0）を作る。

**Architecture:** 計算の部品（プロファイル → 設備の型 → PID の再現 → 推定 → 診断 → 提案 → まとめ）は画面を知らない純粋な Python で、`app/analysis.py` の `run_analysis()` が 1 回の解析結果をまとめる。画面（PyQt6 ＋ pyqtgraph）は入力を集めて `run_analysis()` を呼び、結果を表示するだけにする。調節計ごとの違いは `ControllerProfile` にまとめ、初期値は UT35A / UT32A。

**Tech Stack:** Python 3.14、PyQt6、pyqtgraph、numpy、pytest（開発時のみ）。scipy・pandas・pytest-qt は使わない。

**Spec:** `docs/superpowers/specs/2026-11-14-pid-tuning-advisor-design.md`

**このコードの確かめ方について:** この計画に載せたコードは、作業用フォルダで試作して実行済み。計算の部品・CSV 読み込み・設定画面・アイコン・見本データのテスト 118 件は通過を確認した。メイン画面（Task 11）だけは pyqtgraph が未導入のため未実行で、文法の確認（py_compile）のみ済み。Task 11 で初めて動かすので、そこで出た不具合は原因を特定して直す。

## Global Constraints

- 作業フォルダはリポジトリの直下（`pid-tuning-advisor`）。コマンドはこのフォルダで実行する
- **コミットしない。** コミット・プッシュはユーザーが明示的に依頼したときだけ行う。各タスクはテスト結果の確認で終える
- **パッケージの導入は Task 1 の 1 回だけ。** 導入前に package-security-scan スキルでスキャンし、ユーザーの承認を得る。承認なしに `pip install` を実行しない
- 削除系コマンド（rm・del・rmdir）は使わない。必要になったら対象と理由を示して承認を得る
- 確認用の一時ファイルはプロジェクト内に作らない（セッションの scratchpad に作る）
- `open()` には必ず `encoding=` を付ける。Excel で開く CSV は `utf-8-sig`
- 画面の文字は Meiryo UI（無ければ Meiryo）
- 版番号の出どころは `app/__init__.py` の `__version__ = "0.1.0"` の 1 か所
- 窓の枠とタイトルバーは Windows 標準のまま（枠なしの窓にしない）
- 画面の文言は設計書・画面デザインの言葉を使う（「行き過ぎ」「落ち着くまで」「設備のくせ」など、平易な言葉）
- 「動くはず」で終えない。各タスクのテストを実際に実行し、Task 12 で実際に起動して確かめる
- 同じ系統の修正を 2 回失敗したら、3 回目はせずに状況を報告して止まる

## Review Focus

設計書が暗に求めているが見落としやすい入力。それぞれ、担当タスクのテストで確かめる。

1. **記録計が出した CSV（説明行・単位行つき、Shift-JIS、日本語や空白を含むパス）** → 見出しと数値の行を正しく見つけて読める（Task 8：`test_recorder_style_preamble_and_unit_row`、`test_path_with_japanese_and_space`）
2. **出力がほとんど動いていない区間を選んだ** → 数値の提案を出さず、理由を文章で示す。落ちない（Task 7：`test_no_numeric_proposal_when_output_did_not_move`、Task 11：`test_region_limits_the_analysis`）
3. **単調に揺れ続けるだけの記録（ハンチング）** → 時定数を一つに絞れないことを検出し、変化の速さとむだ時間から安全側の値を出す（Task 4：`test_hunting_gives_speed_and_dead_time_but_not_time_constant`、Task 6：`test_proposal_is_well_behaved_on_the_true_process`）
4. **現在の PID や入力レンジを実機と違う値で入力した** → 「記録と合いません」と注意を出す（Task 7：`test_wrong_pid_entry_lowers_reproduction_and_warns`）
5. **表示桁が粗い記録（0.1 刻み）、記録の間隔が長い・短い記録（5 秒、0.1 秒）** → 推定と診断が大きくずれない（Task 7：`test_coarse_resolution_record`、`test_slow_sampling_record`、Task 4：`test_long_record_is_thinned_and_still_recovered`）

## File Structure

| ファイル | 役割 | タスク |
|---|---|---|
| `.gitignore`、`requirements.txt`、`requirements-dev.txt` | 環境 | 1 |
| `app/__init__.py` | 版番号と名前 | 1 |
| `app/profile.py` | 調節計プロファイル、単位の変換、丸め、保存 | 2 |
| `app/process_model.py` | 1次遅れ＋むだ時間 | 3 |
| `app/controller.py` | PID の計算式の再現 | 3 |
| `tests/synth.py` | テスト・見本用の架空の記録 | 3 |
| `app/identify.py` | 設備の特性の推定 | 4 |
| `app/diagnose.py` | 場面の判定、診断、調整の方向 | 5 |
| `app/tuning.py` | 提案の計算 | 6 |
| `app/analysis.py` | 1 回の解析のまとめ | 7 |
| `app/csv_loader.py` | CSV の読み込み | 8 |
| `app/ui/widgets.py`、`app/ui/style.qss`、`app/assets/*.svg`、`app/main.py` | 見た目の部品、起動 | 9 |
| `tools/make_icon.py`、`tools/make_samples.py`、`app/assets/app.ico`、`samples/*.csv` | アイコンと見本 | 9 |
| `app/ui/settings_dialog.py` | 調節計の設定画面 | 10 |
| `app/ui/main_window.py` | メイン画面 | 11 |
| `起動.bat`、`ショートカット作成.bat`、`tools/make_shortcut.py`、`README.md` | 起動と説明 | 12 |

---

### Task 1: 環境の用意

**Files:**
- Create: `.gitignore`、`requirements.txt`、`requirements-dev.txt`、`app/__init__.py`、`tests/__init__.py`（空）、`tools/__init__.py`（空）

**Interfaces:**
- Produces: `.venv`（Python 3.14）、`app.__version__`、`app.APP_NAME`、`app.APP_DIR_NAME`

- [ ] **Step 1: ファイルを作る**

`.gitignore`

````text
.venv/
__pycache__/
*.pyc
.pytest_cache/
build/
dist/
*.lnk
````


`requirements.txt`

````text
PyQt6>=6.7
pyqtgraph>=0.13
numpy>=1.26
````


`requirements-dev.txt`

````text
pytest>=8.0
````


`app/__init__.py`

````python
__version__ = "0.1.0"
APP_NAME = "PID調整アドバイザー"
APP_DIR_NAME = "pid-tuning-advisor"
````


`tests/__init__.py` と `tools/__init__.py` は空のファイルとして作る。

- [ ] **Step 2: 仮想環境を作る**

Run: `py -3.14 -m venv .venv`
Expected: `.venv` フォルダができる。エラーなし。

- [ ] **Step 3: 導入するパッケージをスキャンし、ユーザーの承認を得る**

package-security-scan スキルで `requirements.txt` と `requirements-dev.txt` をスキャンする。結果とあわせて、次の 3 点をユーザーに説明して承認を待つ。

1. 入れるもの：PyQt6（画面）、pyqtgraph（グラフ）、numpy（数値計算）、pytest（テスト。開発時のみ）
2. 目的：設計書 9.1 節の構成で必要
3. 影響の範囲：このプロジェクトの `.venv` の中だけ（PC 全体には入らない）

承認が出るまで Step 4 に進まない。

- [ ] **Step 4: 導入する（承認後）**

Run: `.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt`
Expected: `Successfully installed ...` に PyQt6・pyqtgraph・numpy・pytest が含まれる。

- [ ] **Step 5: 導入を確かめる**

Run: `.venv/Scripts/python.exe -c "import numpy, pyqtgraph, pytest, PyQt6.QtSvg, PyQt6.QtCore as q, app; print(numpy.__version__, pyqtgraph.__version__, q.PYQT_VERSION_STR, pytest.__version__, app.__version__)"`
Expected: 版番号が 5 つ表示され、最後が `0.1.0`。

---

### Task 2: 調節計プロファイル

**Files:**
- Create: `app/profile.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Consumes: `app.APP_DIR_NAME`
- Produces:
  - `ControllerProfile`（frozen dataclass。フィールドは下のコードのとおり）、`BUILTIN`（UT35A / UT32A）
  - `Pid(kc: float, ti: float | None, td: float)`：計算用の共通の表し方（kc は単位なしのゲイン、ti・td は秒、ti=None と td=0 が OFF）
  - `to_pid(profile, p, i, d) -> Pid`、`from_pid(profile, pid) -> (p, i, d, notes)`
  - `parse_entry(text) -> float | None`、`check_entry(profile, p, i, d) -> list[str]`
  - `p_label / p_unit / i_label / d_label(profile) -> str`、`I_UNIT_LABELS`、`D_UNIT_LABELS`
  - `format_p / format_i / format_d(profile, value) -> str`
  - `data_dir(base=None) -> Path`、`save_profile(profile, base=None) -> Path`、`list_profiles(base=None) -> list[ControllerProfile]`、`load_settings(base=None) -> dict`、`save_settings(settings, base=None)`

- [ ] **Step 1: テストを書く**

`tests/test_profile.py`

````python
import json
from dataclasses import replace

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


@pytest.mark.parametrize("text,expected", [("OFF", None), (" off ", None), ("", None), ("12.5", 12.5), ("1,200", 1200.0)])
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
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_profile.py -q`
Expected: `ModuleNotFoundError: No module named 'app.profile'`（収集エラー）

- [ ] **Step 3: 実装する**

`app/profile.py`

````python
"""調節計プロファイル：調節計ごとに変わる値と、単位の変換・丸め・保存。"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from app import APP_DIR_NAME


@dataclass(frozen=True)
class ControllerProfile:
    """初期値は横河電機 UT35A / UT32A（IM 05P01D31-01EN 第7版）。"""

    name: str = "UT35A / UT32A"
    p_mode: str = "pb"          # "pb" 比例帯(%) / "gain" 比例ゲイン
    i_unit: str = "s"           # "s" 秒 / "min" 分 / "rpm" 回/分
    d_unit: str = "s"           # "s" 秒 / "min" 分
    p_min: float = 0.1
    p_max: float = 999.9
    p_step: float = 0.1
    i_min: float = 1.0
    i_max: float = 6000.0
    i_step: float = 1.0
    i_off: bool = True
    d_min: float = 1.0
    d_max: float = 6000.0
    d_step: float = 1.0
    d_off: bool = True
    sp_response: str = "bump"   # "bump" すぐに動く / "bumpless" 急には動かない
    d_on: str = "pv"            # "pv" 測定値の変化 / "error" 偏差の変化
    reverse: bool = True        # True 逆動作（加熱） / False 正動作（冷却）
    period_ms: float = 200.0
    out_min: float = 0.0
    out_max: float = 100.0


BUILTIN = ControllerProfile()

I_UNIT_LABELS = {"s": "秒", "min": "分", "rpm": "回/分"}
D_UNIT_LABELS = {"s": "秒", "min": "分"}


@dataclass(frozen=True)
class Pid:
    """計算の中で使う共通の表し方。"""

    kc: float           # 単位なしのゲイン（入力レンジ 1% の偏差で出力が何 % 動くか）
    ti: float | None    # 積分時間 秒（None = OFF）
    td: float           # 微分時間 秒（0 = OFF）


def p_label(profile: ControllerProfile) -> str:
    return "比例帯 P" if profile.p_mode == "pb" else "比例ゲイン P"


def p_unit(profile: ControllerProfile) -> str:
    return "%" if profile.p_mode == "pb" else ""


def i_label(profile: ControllerProfile) -> str:
    return "積分 I" if profile.i_unit == "rpm" else "積分時間 I"


def d_label(profile: ControllerProfile) -> str:
    return "微分時間 D"


def parse_entry(text: str) -> float | None:
    """入力欄の文字を数値にする。空欄と OFF は None。数値でなければ ValueError。"""
    s = text.strip().replace("，", ",").replace(",", "")
    if s == "" or s.upper() == "OFF" or s == "ＯＦＦ":
        return None
    return float(s)


def check_entry(profile: ControllerProfile, p: float | None, i: float | None, d: float | None) -> list[str]:
    """入力値の誤りを文章のリストで返す。空なら問題なし。"""
    errs = []
    if p is None:
        errs.append(f"{p_label(profile)} を入力してください。")
    elif not (profile.p_min <= p <= profile.p_max):
        errs.append(f"{p_label(profile)} は {_fmt(profile.p_min, profile.p_step)}〜{_fmt(profile.p_max, profile.p_step)} で入力してください。")
    if i is None:
        if not profile.i_off:
            errs.append(f"{i_label(profile)} を入力してください（この調節計では OFF にできません）。")
    elif not (profile.i_min <= i <= profile.i_max):
        errs.append(f"{i_label(profile)} は {_fmt(profile.i_min, profile.i_step)}〜{_fmt(profile.i_max, profile.i_step)} で入力してください。")
    if d is None:
        if not profile.d_off:
            errs.append(f"{d_label(profile)} を入力してください（この調節計では OFF にできません）。")
    elif not (profile.d_min <= d <= profile.d_max):
        errs.append(f"{d_label(profile)} は {_fmt(profile.d_min, profile.d_step)}〜{_fmt(profile.d_max, profile.d_step)} で入力してください。")
    return errs


def to_pid(profile: ControllerProfile, p: float, i: float | None, d: float | None) -> Pid:
    """調節計の単位の値を、計算用の共通の表し方に直す。"""
    kc = 100.0 / p if profile.p_mode == "pb" else p
    if i is None:
        ti = None
    elif profile.i_unit == "s":
        ti = i
    elif profile.i_unit == "min":
        ti = i * 60.0
    else:
        ti = 60.0 / i
    if d is None:
        td = 0.0
    elif profile.d_unit == "s":
        td = d
    else:
        td = d * 60.0
    return Pid(kc=kc, ti=ti, td=td)


def _decimals(step: float) -> int:
    s = f"{step:.6f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s else 0


def _fmt(value: float, step: float) -> str:
    return f"{value:.{_decimals(step)}f}"


def _snap(value: float, lo: float, hi: float, step: float) -> tuple[float, bool]:
    """刻みに丸めて範囲に収める。範囲に収めるために変えたら True。"""
    v = round(round(value / step) * step, _decimals(step))
    clipped = v < lo or v > hi
    return min(max(v, lo), hi), clipped


def from_pid(profile: ControllerProfile, pid: Pid) -> tuple[float, float | None, float | None, list[str]]:
    """計算結果を調節計の単位に直し、刻みに丸める。戻り値は (P, I, D, 注意書き)。"""
    notes = []
    p_raw = 100.0 / pid.kc if profile.p_mode == "pb" else pid.kc
    p, clipped = _snap(p_raw, profile.p_min, profile.p_max, profile.p_step)
    if clipped:
        notes.append(f"{p_label(profile)} の計算値 {p_raw:.4g} は設定できる範囲の外なので、{_fmt(p, profile.p_step)} にしています。")

    if pid.ti is None:
        i = None if profile.i_off else profile.i_max
    else:
        i_raw = {"s": pid.ti, "min": pid.ti / 60.0, "rpm": 60.0 / pid.ti}[profile.i_unit]
        i, clipped = _snap(i_raw, profile.i_min, profile.i_max, profile.i_step)
        if clipped:
            notes.append(f"{i_label(profile)} の計算値 {i_raw:.4g} は設定できる範囲の外なので、{_fmt(i, profile.i_step)} にしています。")

    d_raw = pid.td if profile.d_unit == "s" else pid.td / 60.0
    if pid.td <= 0 or (d_raw < profile.d_min / 2 and profile.d_off):
        d = None if profile.d_off else profile.d_min
        if pid.td > 0 and profile.d_off:
            notes.append("微分時間の計算値が設定できる最小値より短いので、OFF にしています。")
    else:
        d, clipped = _snap(d_raw, profile.d_min, profile.d_max, profile.d_step)
        if clipped:
            notes.append(f"{d_label(profile)} の計算値 {d_raw:.4g} は設定できる範囲の外なので、{_fmt(d, profile.d_step)} にしています。")
    return p, i, d, notes


def format_p(profile: ControllerProfile, p: float | None) -> str:
    return "OFF" if p is None else (_fmt(p, profile.p_step) + (" %" if profile.p_mode == "pb" else ""))


def format_i(profile: ControllerProfile, i: float | None) -> str:
    return "OFF" if i is None else f"{_fmt(i, profile.i_step)} {I_UNIT_LABELS[profile.i_unit]}"


def format_d(profile: ControllerProfile, d: float | None) -> str:
    return "OFF" if d is None else f"{_fmt(d, profile.d_step)} {D_UNIT_LABELS[profile.d_unit]}"


# ---- 保存と読み込み ----

def data_dir(base: Path | None = None) -> Path:
    if base is not None:
        return Path(base)
    root = os.environ.get("APPDATA") or str(Path.home())
    return Path(root) / APP_DIR_NAME


def _file_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() + ".json"


def save_profile(profile: ControllerProfile, base: Path | None = None) -> Path:
    if profile.name.strip() == "":
        raise ValueError("プロファイルの名前を入力してください。")
    if profile.name == BUILTIN.name:
        raise ValueError("同梱のプロファイルは上書きできません。「複製して新規」で別の名前を付けてください。")
    folder = data_dir(base) / "profiles"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _file_name(profile.name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, ensure_ascii=False, indent=2)
    return path


def _from_dict(d: dict) -> ControllerProfile:
    known = {f.name: f for f in fields(ControllerProfile)}
    kwargs = {}
    for key, value in d.items():
        if key not in known:
            continue
        default = getattr(BUILTIN, key)
        if isinstance(default, bool):
            kwargs[key] = bool(value)
        elif isinstance(default, float):
            kwargs[key] = float(value)
        else:
            kwargs[key] = str(value)
    return ControllerProfile(**kwargs)


def list_profiles(base: Path | None = None) -> list[ControllerProfile]:
    """同梱のプロファイルを先頭に、保存済みのプロファイルを名前順で返す。壊れたファイルは飛ばす。"""
    result = [BUILTIN]
    folder = data_dir(base) / "profiles"
    if folder.is_dir():
        saved = []
        for path in folder.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    prof = _from_dict(json.load(f))
            except (OSError, ValueError, TypeError):
                continue
            if prof.name != BUILTIN.name:
                saved.append(prof)
        result += sorted(saved, key=lambda x: x.name)
    return result


def load_settings(base: Path | None = None) -> dict:
    path = data_dir(base) / "settings.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict, base: Path | None = None) -> None:
    folder = data_dir(base)
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "settings.json", "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
````


- [ ] **Step 4: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_profile.py -q`
Expected: `19 passed`

---

### Task 3: 設備の型と PID の再現

**Files:**
- Create: `app/process_model.py`、`app/controller.py`、`tests/synth.py`
- Test: `tests/test_process_controller.py`

**Interfaces:**
- Consumes: `ControllerProfile`、`Pid`、`BUILTIN`（Task 2）
- Produces:
  - `Fopdt(k, t, l, b)`：k は出力 1% あたりの測定値の変化、t は時定数（秒）、l はむだ時間（秒）、b は出力 0% のときの測定値
  - `lag_filter(u, dt, tau) -> ndarray`、`delayed(x, dt, delay) -> ndarray`、`simulate_open(model, u, dt, y0=None) -> ndarray`
  - `simulate_closed(model, pid, profile, span, sp, dt, y0, u0=None) -> (y, u)`：`sp` は dt 秒間隔の設定値の配列
  - `tests.synth`：`TRUE`（正解の設備）、`SPAN`、`sp_change() / hunting() / manual_step()` → いずれも `(t, sp, pv, out)` を返す（1 秒間隔）

- [ ] **Step 1: テストを書く**

`tests/test_process_controller.py`

````python
from dataclasses import replace

import numpy as np

from app.controller import simulate_closed
from app.process_model import Fopdt, delayed, lag_filter, simulate_open
from app.profile import BUILTIN, Pid

MODEL = Fopdt(k=0.42, t=85.0, l=18.0, b=43.2)
DT = 0.2


def test_lag_filter_reaches_63_percent_at_time_constant():
    u = np.ones(2000)
    u[0] = 0.0
    x = lag_filter(u, 0.1, 20.0)
    assert x[0] == 0.0
    assert abs(x[200] - 0.632) < 0.01
    assert abs(x[-1] - 1.0) < 1e-3


def test_delayed_shifts_and_holds_first_value():
    x = np.arange(10.0)
    assert np.allclose(delayed(x, 1.0, 3.0), [0, 0, 0, 0, 1, 2, 3, 4, 5, 6])
    assert np.allclose(delayed(x, 1.0, 0.5)[1:], x[1:] - 0.5)


def test_open_loop_step_response():
    n = int(900 / DT)
    u = np.where(np.arange(n) * DT >= 60.0, 50.0, 40.0)
    y = simulate_open(MODEL, u, DT)
    assert abs(y[0] - 60.0) < 1e-9
    assert abs(y[int(77 / DT)] - 60.0) < 1e-6                 # むだ時間のあいだは動かない
    assert abs(y[int((60 + 18 + 85) / DT)] - (60.0 + 0.632 * 4.2)) < 0.05
    assert abs(y[-1] - 64.2) < 0.01


def test_open_loop_from_unsettled_start():
    y = simulate_open(MODEL, np.full(5000, 40.0), DT, y0=62.0)
    assert abs(y[0] - 62.0) < 1e-9 and abs(y[-1] - 60.0) < 0.01


def _run(pid, profile=BUILTIN, model=MODEL, sp0=60.0, sp1=65.0, seconds=900):
    n = int(seconds / DT)
    sp = np.where(np.arange(n) * DT >= 120.0, sp1, sp0)
    return sp, *simulate_closed(model, pid, profile, 100.0, sp, DT, y0=sp0)


def test_closed_loop_starts_settled_and_reaches_setpoint():
    sp, y, u = _run(Pid(kc=5.0, ti=94.0, td=8.0))
    assert np.allclose(y[: int(119 / DT)], 60.0, atol=1e-6)
    assert np.allclose(u[: int(119 / DT)], 40.0, atol=1e-6)
    assert abs(y[-1] - 65.0) < 0.05
    assert abs(u[-1] - (65.0 - 43.2) / 0.42) < 0.5


def test_output_stays_inside_limits():
    _, _, u = _run(Pid(kc=40.0, ti=20.0, td=0.0))
    assert u.min() >= 0.0 and u.max() <= 100.0 and u.max() == 100.0
    narrow = replace(BUILTIN, name="x", out_min=10.0, out_max=80.0)
    _, _, u = _run(Pid(kc=40.0, ti=20.0, td=0.0), profile=narrow)
    assert u.min() >= 10.0 and u.max() <= 80.0


def test_bump_mode_jumps_at_setpoint_change_and_bumpless_does_not():
    i = int(120 / DT)
    _, _, u = _run(Pid(kc=5.0, ti=94.0, td=0.0))
    assert abs((u[i] - u[i - 1]) - 5.0 * 5.0) < 0.5           # ゲイン 5 × 偏差 5%
    smooth = replace(BUILTIN, name="x", sp_response="bumpless")
    _, y, u = _run(Pid(kc=5.0, ti=94.0, td=0.0), profile=smooth)
    assert abs(u[i] - u[i - 1]) < 0.5
    assert abs(y[-1] - 65.0) < 0.1


def test_derivative_on_error_kicks_at_setpoint_change():
    i = int(120 / DT)
    on_error = replace(BUILTIN, name="x", d_on="error")
    _, _, u_pv = _run(Pid(kc=2.0, ti=94.0, td=2.0))
    _, _, u_err = _run(Pid(kc=2.0, ti=94.0, td=2.0), profile=on_error)
    assert u_err[i] > u_pv[i] + 20.0


def test_direct_action_with_cooling_process():
    cooling = Fopdt(k=-0.3, t=60.0, l=10.0, b=40.0)          # 出力を上げると下がる設備
    direct = replace(BUILTIN, name="x", reverse=False)
    _, y, u = _run(Pid(kc=3.0, ti=60.0, td=0.0), profile=direct, model=cooling, sp0=25.0, sp1=22.0)
    assert abs(y[-1] - 22.0) < 0.05 and u[-1] > u[0]


def test_p_only_leaves_offset():
    _, y, _ = _run(Pid(kc=5.0, ti=None, td=0.0))
    assert 0.5 < 65.0 - y[-1] < 3.0
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_process_controller.py -q`
Expected: `ModuleNotFoundError: No module named 'app.controller'`

- [ ] **Step 3: 実装する**

`app/process_model.py`

````python
"""設備の型：1次遅れ＋むだ時間。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Fopdt:
    k: float    # 出力 1% あたりの測定値の変化
    t: float    # 時定数 秒
    l: float    # むだ時間 秒
    b: float    # 出力 0% のときの測定値


def lag_filter(u: np.ndarray, dt: float, tau: float) -> np.ndarray:
    """1次遅れ。最初は u[0] で落ち着いているものとする。"""
    a = float(np.exp(-dt / tau))
    x = np.empty(len(u))
    acc = float(u[0])
    for n in range(len(u)):
        x[n] = acc
        acc = a * acc + (1.0 - a) * float(u[n])
    return x


def delayed(x: np.ndarray, dt: float, delay: float) -> np.ndarray:
    """delay 秒だけ遅らせる。記録より前は x[0] が続いていたものとする。"""
    t = np.arange(len(x)) * dt
    return np.interp(t - delay, t, x, left=x[0])


def simulate_open(model: Fopdt, u: np.ndarray, dt: float, y0: float | None = None) -> np.ndarray:
    """出力 u を与えたときの測定値を計算する。"""
    x = delayed(lag_filter(u, dt, model.t), dt, model.l)
    y = model.k * x + model.b
    if y0 is not None:
        t = np.arange(len(u)) * dt
        y = y + (y0 - y[0]) * np.exp(-t / model.t)
    return y
````


`app/controller.py`

````python
"""PID の計算式の再現と、設備と組み合わせた計算。"""
from __future__ import annotations

import math

import numpy as np

from app.process_model import Fopdt
from app.profile import ControllerProfile, Pid


def simulate_closed(
    model: Fopdt,
    pid: Pid,
    profile: ControllerProfile,
    span: float,
    sp: np.ndarray,
    dt: float,
    y0: float,
    u0: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """設定値の列 sp（dt 秒間隔）に対する測定値と出力を計算する。

    計算式（UT35A 取扱説明書 8.3 節の形）:
        出力 = ゲイン ×（比例の項 + 偏差の積分 ÷ 積分時間 + 微分時間 × 変化の速さ）
    偏差と測定値は、入力レンジの幅に対する % に直して計算する。
    積分は、出力が上下限に張り付いていて、さらに張り付く向きの偏差のときは止める。
    """
    n = len(sp)
    lo, hi = profile.out_min, profile.out_max
    sign = 1.0 if profile.reverse else -1.0
    if u0 is None:
        u0 = (y0 - model.b) / model.k
    u0 = min(max(u0, lo), hi)

    d_steps = model.l / dt
    n0 = int(math.floor(d_steps))
    frac = d_steps - n0
    hist = np.full(n + n0 + 2, u0)      # hist[i + n0 + 1] が時刻 i の出力
    a = math.exp(-dt / model.t)

    use_error = profile.sp_response == "bump" or pid.ti is None
    y = float(y0)
    e0 = sign * (sp[0] - y) / span * 100.0
    m0 = -sign * y / span * 100.0
    p0 = e0 if use_error else 0.0
    if pid.ti is not None:
        integ = (u0 / pid.kc - p0) * pid.ti
        bias = 0.0
    else:
        integ = 0.0
        bias = u0 - pid.kc * p0
    e_prev, m_prev = e0, m0

    ys = np.empty(n)
    us = np.empty(n)
    for i in range(n):
        e = sign * (sp[i] - y) / span * 100.0
        m = -sign * y / span * 100.0
        pterm = e if use_error else (m - m0)
        rate = (m - m_prev) if profile.d_on == "pv" else (e - e_prev)
        dterm = pid.td * rate / dt
        iterm = integ / pid.ti if pid.ti is not None else 0.0
        raw = pid.kc * (pterm + iterm + dterm) + bias
        u = min(max(raw, lo), hi)
        if pid.ti is not None and not ((raw > hi and e > 0) or (raw < lo and e < 0)):
            integ += e * dt
        e_prev, m_prev = e, m

        ys[i] = y
        us[i] = u
        k = i + n0 + 1
        hist[k] = u
        u_del = (1.0 - frac) * hist[k - n0] + frac * hist[k - n0 - 1]
        y = a * y + (1.0 - a) * (model.k * u_del + model.b)
    return ys, us
````


`tests/synth.py`

````python
"""テスト用：答えの分かっている架空の設備の記録を計算で作る。"""
from __future__ import annotations

import numpy as np

from app.controller import simulate_closed
from app.process_model import Fopdt, simulate_open
from app.profile import BUILTIN, Pid

TRUE = Fopdt(k=0.42, t=85.0, l=18.0, b=43.2)    # 出力 40% で 60℃ になる設備
SPAN = 100.0
SIM_DT = 0.2


def _sample(y, u, sp, every, noise, seed):
    rng = np.random.default_rng(seed)
    y, u, sp = y[::every], u[::every], sp[::every]
    t = np.arange(len(y)) * SIM_DT * every
    return t, sp, y + rng.normal(0.0, noise, len(y)), u


def sp_change(pid=Pid(kc=10.0, ti=45.0, td=0.0), noise=0.02, seed=1, profile=BUILTIN):
    """設定値を 120 秒で 60→65℃ に変える。900 秒、1 秒間隔。"""
    n = int(900 / SIM_DT) + 1
    sp = np.where(np.arange(n) * SIM_DT >= 120.0, 65.0, 60.0)
    y, u = simulate_closed(TRUE, pid, profile, SPAN, sp, SIM_DT, y0=60.0)
    return _sample(y, u, sp, 5, noise, seed)


def hunting(pid=Pid(kc=40.0, ti=20.0, td=0.0), noise=0.02, seed=2):
    """設定値 60℃ 一定。きつすぎる設定で揺れ続ける。900 秒、1 秒間隔。"""
    n = int(900 / SIM_DT) + 1
    sp = np.full(n, 60.0)
    y, u = simulate_closed(TRUE, pid, BUILTIN, SPAN, sp, SIM_DT, y0=60.5, u0=40.0)
    return _sample(y, u, sp, 5, noise, seed)


def manual_step(noise=0.02, seed=3):
    """手動で出力を 60 秒で 40→50% に変える。600 秒、1 秒間隔。"""
    n = int(600 / SIM_DT) + 1
    u = np.where(np.arange(n) * SIM_DT >= 60.0, 50.0, 40.0)
    y = simulate_open(TRUE, u, SIM_DT)
    return _sample(y, u, np.full(n, 60.0), 5, noise, seed)
````


- [ ] **Step 4: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_process_controller.py -q`
Expected: `10 passed`

---

### Task 4: 設備の特性の推定

**Files:**
- Create: `app/identify.py`
- Test: `tests/test_identify.py`

**Interfaces:**
- Consumes: `Fopdt`、`lag_filter`（Task 3）、`tests.synth`（Task 3）
- Produces:
  - `identify(t, u, y, span, reverse) -> IdentResult`：t は等間隔の経過秒、u は出力 %、y は測定値
  - `IdentResult(model: Fopdt | None, fit: float, ok: bool, reasons: list[str], t_uncertain: bool)`
    - `ok` が False のとき、`reasons` に理由の文章が入る。`model` は推定できたときだけ入る
    - `t_uncertain` が True のとき、時定数は一つに絞れていない（`model.k / model.t` と `model.l` は使える）

考え方：時定数 T とむだ時間 L を決めれば、残りの K・b・最初の状態の影響は一次式の最小二乗で求まる。T と L の候補を総当たりし、いちばん合う組の周りを 2 回細かく探し直す。むだ時間の候補は、短いところを記録の間隔ごとに細かく取る（粗いと時定数が大きくずれることを試作で確認した）。

- [ ] **Step 1: テストを書く**

`tests/test_identify.py`

````python
import numpy as np
import pytest

from app.identify import identify
from tests import synth

TRUE = synth.TRUE


def _close(value, target, tol=0.15):
    return abs(value - target) <= tol * abs(target)


@pytest.mark.parametrize("maker", [synth.sp_change, synth.manual_step])
def test_recovers_known_process(maker):
    t, sp, pv, out = maker()
    r = identify(t, out, pv, synth.SPAN, True)
    assert r.ok and r.reasons == [] and not r.t_uncertain
    assert _close(r.model.k, TRUE.k) and _close(r.model.t, TRUE.t) and _close(r.model.l, TRUE.l)
    assert _close(r.model.b, TRUE.b)
    assert r.fit > 90.0


def test_hunting_gives_speed_and_dead_time_but_not_time_constant():
    t, sp, pv, out = synth.hunting()
    r = identify(t, out, pv, synth.SPAN, True)
    assert r.ok and r.t_uncertain
    assert _close(r.model.k / r.model.t, TRUE.k / TRUE.t) and _close(r.model.l, TRUE.l)


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_robust_to_larger_noise(seed):
    t, sp, pv, out = synth.sp_change(noise=0.05, seed=seed)
    r = identify(t, out, pv, synth.SPAN, True)
    assert r.ok and _close(r.model.k, TRUE.k) and _close(r.model.t, TRUE.t) and _close(r.model.l, TRUE.l)


def test_long_record_is_thinned_and_still_recovered():
    t, sp, pv, out = synth.sp_change()
    tf = np.arange(0.0, t[-1], 0.1)                          # 0.1 秒間隔 = 約 9000 点
    r = identify(tf, np.interp(tf, t, out), np.interp(tf, t, pv), synth.SPAN, True)
    assert r.ok and _close(r.model.k, TRUE.k) and _close(r.model.t, TRUE.t) and _close(r.model.l, TRUE.l)


def test_time_offset_does_not_matter():
    t, sp, pv, out = synth.manual_step()
    r = identify(t + 5000.0, out, pv, synth.SPAN, True)
    assert r.ok and _close(r.model.t, TRUE.t)


def test_flat_output_is_refused():
    t, sp, pv, out = synth.sp_change()
    r = identify(t, np.full(len(t), 40.0), pv, synth.SPAN, True)
    assert not r.ok and r.model is None and "出力の変化幅" in r.reasons[0]


def test_flat_pv_is_refused():
    t, sp, pv, out = synth.sp_change()
    r = identify(t, out, np.full(len(t), 60.0), synth.SPAN, True)
    assert not r.ok and "測定値の変化幅" in r.reasons[0]


def test_too_few_points_is_refused():
    t, sp, pv, out = synth.sp_change()
    r = identify(t[:20], out[:20], pv[:20], synth.SPAN, True)
    assert not r.ok and "30 点未満" in r.reasons[0]


def test_wrong_action_direction_is_reported():
    t, sp, pv, out = synth.manual_step()
    r = identify(t, out, pv, synth.SPAN, False)
    assert not r.ok and any("動作の向き" in s for s in r.reasons)


def test_interval_too_short_for_slow_process_is_reported():
    t, sp, pv, out = synth.manual_step()
    sel = (t >= 55) & (t <= 100)                             # 動き出した直後だけ
    r = identify(t[sel], out[sel], pv[sel], synth.SPAN, True)
    assert not r.ok


def test_unrelated_signals_fit_poorly():
    rng = np.random.default_rng(5)
    t = np.arange(600.0)
    out = 50.0 + 10.0 * np.sign(np.sin(t / 30.0))
    pv = 60.0 + rng.normal(0.0, 1.0, len(t))
    r = identify(t, out, pv, synth.SPAN, True)
    assert not r.ok
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_identify.py -q`
Expected: `ModuleNotFoundError: No module named 'app.identify'`

- [ ] **Step 3: 実装する**

`app/identify.py`

````python
"""設備の特性（1次遅れ＋むだ時間）を、出力と測定値の記録から推定する。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.process_model import Fopdt, lag_filter

MIN_POINTS = 30
MIN_OUT_RANGE = 2.0         # 出力の変化幅 %
MIN_PV_RANGE_PCT = 0.5      # 測定値の変化幅（入力レンジに対する %）
MIN_FIT = 70.0              # 当てはまり具合 %
AMBIGUITY_FIT_DROP = 2.0    # 当てはまりがこの幅以内の候補を「同じくらい良い」とみなす
AMBIGUITY_T_RATIO = 3.0     # 同じくらい良い候補の時定数が、この倍率を超えて散らばれば「時定数を絞れない」
MAX_POINTS = 3000


@dataclass
class IdentResult:
    model: Fopdt | None
    fit: float                      # 当てはまり具合 %（推定していないときは 0）
    ok: bool                        # 数値の提案に使ってよいか
    reasons: list[str] = field(default_factory=list)   # ok でない理由
    t_uncertain: bool = False       # 時定数を一つに絞れない（変化の速さ K/T とむだ時間は使える）


def _decimate(x: np.ndarray, m: int) -> np.ndarray:
    n = (len(x) // m) * m
    return x[:n].reshape(-1, m).mean(axis=1)


def _sse(xf: np.ndarray, t: np.ndarray, y: np.ndarray, tau: float, delay: float):
    xd = np.interp(t - delay, t, xf, left=xf[0])
    a = np.column_stack([xd, np.ones_like(t), np.exp(-t / tau)])
    coef, *_ = np.linalg.lstsq(a, y, rcond=None)
    r = y - a @ coef
    return float(r @ r), coef


def identify(t: np.ndarray, u: np.ndarray, y: np.ndarray, span: float, reverse: bool) -> IdentResult:
    """t は等間隔の経過秒、u は出力 %、y は測定値。"""
    reasons = []
    if len(t) < MIN_POINTS:
        return IdentResult(None, 0.0, False, [f"区間内のデータが {MIN_POINTS} 点未満です。"])
    out_range = float(u.max() - u.min())
    pv_range = float(y.max() - y.min())
    if out_range < MIN_OUT_RANGE:
        reasons.append(f"区間内の出力の変化幅が {out_range:.1f}% で、{MIN_OUT_RANGE:.0f}% に足りません。")
    if pv_range < span * MIN_PV_RANGE_PCT / 100.0:
        reasons.append("区間内の測定値の変化幅が、入力レンジの 0.5% に足りません。")
    if reasons:
        return IdentResult(None, 0.0, False, reasons)

    m = max(1, math.ceil(len(t) / MAX_POINTS))
    if m > 1:
        t, u, y = _decimate(t, m), _decimate(u, m), _decimate(y, m)
    t = t - t[0]
    dt = float(t[1] - t[0])
    duration = float(t[-1])
    total = float(((y - y.mean()) ** 2).sum())

    taus = np.geomspace(2.0 * dt, duration, 40)
    l_max = duration / 4.0
    # むだ時間の候補：短いところは記録の間隔ごとに細かく、長いところは粗く
    fine = dt * np.arange(0, 31)
    coarse = np.geomspace(31 * dt, l_max, 20) if l_max > 31 * dt else np.empty(0)
    delays = np.concatenate([fine[fine <= l_max], coarse])
    grid = np.empty((len(taus), len(delays)))
    for i, tau in enumerate(taus):
        xf = lag_filter(u, dt, tau)
        for j, delay in enumerate(delays):
            grid[i, j] = _sse(xf, t, y, tau, delay)[0]
    i, j = np.unravel_index(int(np.argmin(grid)), grid.shape)
    best_tau, best_delay, best = float(taus[i]), float(delays[j]), float(grid[i, j])

    # 当てはまりが同じくらい良い候補の時定数が大きく散らばっていれば、一つに絞れていない
    fit_grid = 100.0 * (1.0 - np.sqrt(grid / total))
    near = fit_grid >= fit_grid[i, j] - AMBIGUITY_FIT_DROP
    near_taus = taus[near.any(axis=1)]
    t_uncertain = float(near_taus.max() / near_taus.min()) > AMBIGUITY_T_RATIO

    tau_ratio = float(taus[1] / taus[0])
    delay_step = float(max(np.diff(delays)[max(j - 1, 0):j + 1].max(), dt))
    for _ in range(2):
        tau_c = np.geomspace(best_tau / tau_ratio, best_tau * tau_ratio, 9)
        delay_c = np.clip(np.linspace(best_delay - delay_step, best_delay + delay_step, 9), 0.0, None)
        for tau in tau_c:
            xf = lag_filter(u, dt, float(tau))
            for delay in delay_c:
                s = _sse(xf, t, y, float(tau), float(delay))[0]
                if s < best:
                    best, best_tau, best_delay = s, float(tau), float(delay)
        tau_ratio = tau_ratio ** 0.25
        delay_step /= 4.0

    _, coef = _sse(lag_filter(u, dt, best_tau), t, y, best_tau, best_delay)
    model = Fopdt(k=float(coef[0]), t=best_tau, l=best_delay, b=float(coef[1]))
    fit = 100.0 * (1.0 - math.sqrt(best / total))

    if fit < MIN_FIT:
        reasons.append(f"当てはまり具合が {fit:.0f}% で、{MIN_FIT:.0f}% に足りません。")
    if (model.k > 0) != reverse:
        reasons.append("出力を上げたときの測定値の動きが、動作の向き（逆動作・正動作）の設定と合いません。")
    if best_tau >= 0.95 * duration or best_delay >= 0.95 * l_max:
        reasons.append("反応の遅れが区間の長さに対して長すぎて、推定できません。もっと長い区間を選んでください。")
    return IdentResult(model, fit, not reasons, reasons, t_uncertain)
````


- [ ] **Step 4: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_identify.py -q`
Expected: `14 passed`

---

### Task 5: 波形の診断

**Files:**
- Create: `app/diagnose.py`
- Test: `tests/test_diagnose.py`

**Interfaces:**
- Consumes: `ControllerProfile`、`Pid`（Task 2）、`tests.synth`（Task 3）
- Produces:
  - 場面の名前：`SP_CHANGE = "sp_change"`、`MANUAL = "manual"`、`HUNTING = "hunting"`、`UNKNOWN = "unknown"`、`SCENE_LABELS: dict[str, str]`
  - `noise_sd(x) -> float`、`excursions(t, dev, db) -> list[Excursion]`
  - `detect_scene(t, sp, pv, out, span) -> str`
  - `step_metrics(t, sp, pv, span) -> StepMetrics`（フィールド：`sp0, sp1, t_step, overshoot, overshoot_pct, period, decay, settle, swinging, offset, multi_step`）
  - `hunt_metrics(t, sp, pv, out, span, out_min, out_max) -> HuntMetrics`（`pv_pp, out_pp, period, trend, saturated, swinging, offset`）
  - `manual_metrics(t, pv, out) -> ManualMetrics`（`t_jump, d_out, d_pv, t63`）
  - `advise(profile, pid, span, swinging, period, overshoot_pct, offset, settle, proposed_settle) -> str`

- [ ] **Step 1: テストを書く**

`tests/test_diagnose.py`

````python
from dataclasses import replace

import numpy as np

from app import diagnose as dg
from app.profile import BUILTIN, Pid
from tests import synth


def test_noise_sd_estimates_scatter_and_ignores_trend():
    rng = np.random.default_rng(0)
    x = np.linspace(0.0, 50.0, 5000) + rng.normal(0.0, 0.1, 5000)
    assert abs(dg.noise_sd(x) - 0.1) < 0.02
    assert dg.noise_sd(np.array([1.0])) == 0.0


def test_excursions_of_sine_wave():
    t = np.arange(0.0, 100.0, 0.1)
    ex = dg.excursions(t, np.sin(2 * np.pi * t / 20.0), 0.05)
    assert [e.side for e in ex[:4]] == [1, -1, 1, -1]
    assert abs(ex[0].t - 5.0) < 0.2 and abs(ex[0].value - 1.0) < 0.01
    assert abs(ex[2].t - ex[0].t - 20.0) < 0.3


def test_excursions_ignores_wiggle_inside_deadband():
    t = np.arange(10.0)
    assert dg.excursions(t, np.array([0.01, -0.01] * 5), 0.05) == []


def test_detect_scene():
    assert dg.detect_scene(*synth.sp_change(), synth.SPAN) == dg.SP_CHANGE
    assert dg.detect_scene(*_reorder(synth.manual_step()), synth.SPAN) == dg.MANUAL
    assert dg.detect_scene(*_reorder(synth.hunting()), synth.SPAN) == dg.HUNTING
    t = np.arange(300.0)
    flat = np.full(300, 60.0)
    assert dg.detect_scene(t, flat, flat, np.full(300, 40.0), synth.SPAN) == dg.UNKNOWN


def _reorder(rec):
    t, sp, pv, out = rec
    return t, sp, pv, out


def test_step_metrics_on_known_response():
    t, sp, pv, out = synth.sp_change()
    m = dg.step_metrics(t, sp, pv, synth.SPAN)
    assert (m.sp0, m.sp1, m.t_step) == (60.0, 65.0, 120.0)
    assert abs(m.overshoot - 2.3) < 0.15 and abs(m.overshoot_pct - 46.0) < 3.0
    assert abs(m.period - 98.0) < 10.0
    assert abs(m.settle - 209.0) < 15.0
    assert abs(m.offset) < 0.05 and not m.multi_step


def test_step_metrics_downward_step_and_not_settled():
    t = np.arange(0.0, 200.0)
    sp = np.where(t >= 20, 50.0, 60.0)
    pv = np.where(t >= 20, 50.0 + 10.0 * np.exp(-(t - 20) / 200.0), 60.0)   # ゆっくりで区間内に届かない
    m = dg.step_metrics(t, sp, pv, 100.0)
    assert m.overshoot == 0.0 and m.settle is None and m.period is None and not m.swinging
    assert m.offset > 3.0


def test_step_metrics_flags_repeated_setpoint_changes():
    t = np.arange(0.0, 300.0)
    sp = np.where(t < 100, 60.0, np.where(t < 200, 65.0, 62.0))
    m = dg.step_metrics(t, sp, sp.copy(), 100.0)
    assert m.multi_step and (m.sp0, m.sp1) == (60.0, 62.0)
    ramp = np.clip(60.0 + (t - 50) * 0.1, 60.0, 65.0)                      # 一方向の傾斜は 1 回の変更とみなす
    assert not dg.step_metrics(t, ramp, ramp.copy(), 100.0).multi_step


def test_hunt_metrics():
    t, sp, pv, out = synth.hunting()
    m = dg.hunt_metrics(t, sp, pv, out, synth.SPAN, 0.0, 100.0)
    assert m.swinging and m.trend == "続いている"
    assert 5.0 < m.pv_pp < 9.0 and m.out_pp > 99.0
    assert 50.0 < m.period < 110.0
    assert m.saturated > 0.4


def test_manual_metrics():
    t, sp, pv, out = synth.manual_step()
    m = dg.manual_metrics(t, pv, out)
    assert m.t_jump == 60.0 and abs(m.d_out - 10.0) < 1e-9
    assert abs(m.d_pv - 4.2) < 0.15
    assert abs(m.t63 - (18.0 + 85.0)) < 10.0


def _advise(**kw):
    args = dict(profile=BUILTIN, pid=Pid(kc=10.0, ti=45.0, td=0.0), span=100.0, swinging=False, period=None,
                overshoot_pct=0.0, offset=0.0, settle=100.0, proposed_settle=100.0)
    args.update(kw)
    return dg.advise(**args)


def test_advise_follows_the_table_in_order():
    assert "微分時間を短く" in _advise(swinging=True, period=30.0, pid=Pid(10.0, 45.0, 10.0))
    assert "積分時間を長く" in _advise(swinging=True, period=98.0)
    assert "比例帯を広げる" in _advise(swinging=True, period=30.0)
    assert "比例帯を広げる" in _advise(swinging=True, period=30.0, pid=Pid(10.0, None, 0.0))
    assert "積分時間を長く" in _advise(overshoot_pct=46.0)
    assert "積分時間を短く" in _advise(offset=-0.8)
    assert "積分動作を入れる" in _advise(offset=-0.8, pid=Pid(10.0, None, 0.0))
    assert "比例帯を狭める" in _advise(settle=400.0, proposed_settle=100.0)
    assert _advise() == "大きな問題は見当たりません。"
    assert _advise(settle=None, proposed_settle=None) == "大きな問題は見当たりません。"


def test_advise_wording_for_gain_and_rpm_controllers():
    g = replace(BUILTIN, name="x", p_mode="gain", i_unit="rpm")
    assert "比例ゲインを下げる" in _advise(profile=g, swinging=True, period=30.0)
    assert "積分（回/分）を小さく" in _advise(profile=g, swinging=True, period=98.0)
    assert "比例ゲインを上げる" in _advise(profile=g, settle=400.0, proposed_settle=100.0)
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_diagnose.py -q`
Expected: `ImportError: cannot import name 'diagnose' from 'app'`

- [ ] **Step 3: 実装する**

`app/diagnose.py`

````python
"""場面の判定、波形の診断、調整の方向。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.profile import ControllerProfile, Pid

SP_CHANGE = "sp_change"
MANUAL = "manual"
HUNTING = "hunting"
UNKNOWN = "unknown"
SCENE_LABELS = {
    SP_CHANGE: "設定値の変更",
    MANUAL: "手動で出力を変更",
    HUNTING: "温度の揺れ（ハンチング）",
    UNKNOWN: "判定できません",
}

SP_CHANGE_PCT = 0.5     # 設定値がこれ以上（入力レンジ %）変われば「設定値の変更」
SETTLE_BAND = 0.05      # 落ち着いたとみなす幅（変化幅に対する割合）
SWING_DECAY = 0.25      # 2 つ目の山が 1 つ目のこの割合より大きければ「揺れがある」
BIG_OVERSHOOT = 10.0    # 行き過ぎが大きいとみなす %（変化幅に対して）
OFFSET_PCT = 0.5        # ずれが残っているとみなす偏差（入力レンジ %）


def noise_sd(x: np.ndarray) -> float:
    """細かいばらつきの大きさ（となり合う点の差から見積もる）。"""
    d = np.diff(x)
    if len(d) == 0:
        return 0.0
    return float(1.4826 * np.median(np.abs(d - np.median(d))) / np.sqrt(2.0))


def _deadband(pv: np.ndarray, span: float) -> float:
    return max(3.0 * noise_sd(pv), span * 0.0005)


@dataclass
class Excursion:
    side: int       # +1 上側 / -1 下側
    t: float        # いちばん離れた時刻
    value: float    # そのときの偏差（符号つき）


def excursions(t: np.ndarray, dev: np.ndarray, db: float) -> list[Excursion]:
    """偏差が基準を上下にまたぐごとに区切り、区切りごとのいちばん離れた点を返す。"""
    result: list[Excursion] = []
    side = 0
    best_i = 0
    for i, v in enumerate(dev):
        s = 1 if v > db else (-1 if v < -db else 0)
        if s == 0 or s == side:
            if s == side and side != 0 and abs(v) > abs(dev[best_i]):
                best_i = i
            continue
        if side != 0:
            result.append(Excursion(side, float(t[best_i]), float(dev[best_i])))
        side, best_i = s, i
    if side != 0:
        result.append(Excursion(side, float(t[best_i]), float(dev[best_i])))
    return result


def detect_scene(t: np.ndarray, sp: np.ndarray, pv: np.ndarray, out: np.ndarray, span: float) -> str:
    if float(sp.max() - sp.min()) >= span * SP_CHANGE_PCT / 100.0:
        return SP_CHANGE
    steps = np.abs(np.diff(out))
    if len(steps) and float(np.mean(steps < 0.05)) >= 0.9 and float(steps.max()) >= 1.0:
        return MANUAL
    ex = excursions(t, pv - float(np.mean(sp)), _deadband(pv, span))
    if len(ex) >= 4:
        return HUNTING
    return UNKNOWN


@dataclass
class StepMetrics:
    sp0: float
    sp1: float
    t_step: float               # 設定値が変わり始めた時刻
    overshoot: float            # 行き過ぎ量（測定値の単位）
    overshoot_pct: float        # 変化幅に対する %
    period: float | None        # 揺れの周期 秒
    decay: float | None         # 2 つ目の山 ÷ 1 つ目の山
    settle: float | None        # 落ち着くまでの時間 秒（区間内で落ち着かなければ None）
    swinging: bool              # 揺れがある
    offset: float               # 区間の終わりに残っている偏差（測定値 − 設定値）
    multi_step: bool            # 区間内で設定値が何度も変わっている


def step_metrics(t: np.ndarray, sp: np.ndarray, pv: np.ndarray, span: float) -> StepMetrics:
    sp0, sp1 = float(sp[0]), float(sp[-1])
    tol = span * 0.001
    changed = np.nonzero(np.abs(sp - sp0) > tol)[0]
    i_first = int(changed[0]) if len(changed) else 0
    not_final = np.nonzero(np.abs(sp - sp1) > tol)[0]
    i_last = int(not_final[-1]) + 1 if len(not_final) else 0
    levels = np.unique(np.round(sp / max(tol, 1e-12)))
    multi_step = len(levels) > 2 and not np.all(np.diff(sp) * np.sign(sp1 - sp0) >= -tol)
    step = sp1 - sp0
    sgn = 1.0 if step >= 0 else -1.0
    t_step = float(t[i_first])

    tt, dev = t[i_last:], (pv[i_last:] - sp1) * sgn
    overshoot = max(float(dev.max()), 0.0) if len(dev) else 0.0
    overshoot_pct = 100.0 * overshoot / abs(step) if step != 0 else 0.0
    ups = [e for e in excursions(tt, dev, _deadband(pv, span)) if e.side > 0]
    ups = [e for e in ups if e.value >= 0.1 * ups[0].value]     # 最初の山の 1 割に満たない山は数えない
    period = ups[1].t - ups[0].t if len(ups) >= 2 else None
    decay = ups[1].value / ups[0].value if len(ups) >= 2 else None
    swinging = decay is not None and decay > SWING_DECAY

    band = SETTLE_BAND * abs(step)
    outside = np.nonzero(np.abs(pv - sp1) > band)[0]
    if len(outside) == 0:
        settle = 0.0
    elif outside[-1] >= len(t) - 1:
        settle = None
    else:
        settle = max(float(t[outside[-1] + 1]) - t_step, 0.0)
    tail = max(1, len(pv) // 20)
    offset = float(np.mean(pv[-tail:]) - sp1)
    return StepMetrics(sp0, sp1, t_step, overshoot, overshoot_pct, period, decay, settle, swinging, offset, multi_step)


@dataclass
class HuntMetrics:
    pv_pp: float                # 測定値の揺れの幅
    out_pp: float               # 出力の揺れの幅 %
    period: float | None
    trend: str                  # "収まっていく" / "続いている" / "広がっている" / "判定できません"
    saturated: float            # 出力が上下限に張り付いている時間の割合
    swinging: bool
    offset: float


def hunt_metrics(t: np.ndarray, sp: np.ndarray, pv: np.ndarray, out: np.ndarray, span: float,
                 out_min: float, out_max: float) -> HuntMetrics:
    ref = float(np.mean(sp))
    ex = excursions(t, pv - ref, _deadband(pv, span))
    ups = [e for e in ex if e.side > 0]
    period = float(np.median(np.diff([e.t for e in ups]))) if len(ups) >= 2 else None
    trend = "判定できません"
    if len(ex) >= 4:
        half = len(ex) // 2
        first = float(np.mean([abs(e.value) for e in ex[:half]]))
        second = float(np.mean([abs(e.value) for e in ex[half:]]))
        ratio = second / first if first > 0 else 1.0
        trend = "広がっている" if ratio > 1.2 else ("収まっていく" if ratio < 0.8 else "続いている")
    saturated = float(np.mean((out <= out_min + 0.5) | (out >= out_max - 0.5)))
    tail = max(1, len(pv) // 20)
    return HuntMetrics(float(pv.max() - pv.min()), float(out.max() - out.min()), period, trend,
                       saturated, len(ex) >= 4, float(np.mean(pv[-tail:]) - ref))


@dataclass
class ManualMetrics:
    t_jump: float
    d_out: float                # 出力の変化量 %
    d_pv: float                 # 測定値の変化量
    t63: float | None           # 変化量の 63% に達するまでの時間 秒


def manual_metrics(t: np.ndarray, pv: np.ndarray, out: np.ndarray) -> ManualMetrics:
    i = int(np.argmax(np.abs(np.diff(out)))) + 1
    d_out = float(np.median(out[i:]) - np.median(out[:i]))
    before = float(np.mean(pv[:i]))
    tail = max(1, len(pv) // 10)
    d_pv = float(np.mean(pv[-tail:]) - before)
    t63 = None
    if d_pv != 0:
        reached = np.nonzero((pv[i:] - before) * np.sign(d_pv) >= 0.63 * abs(d_pv))[0]
        if len(reached):
            t63 = float(t[i + reached[0]] - t[i])
    return ManualMetrics(float(t[i]), d_out, d_pv, t63)


def advise(profile: ControllerProfile, pid: Pid, span: float, swinging: bool, period: float | None,
           overshoot_pct: float, offset: float, settle: float | None, proposed_settle: float | None) -> str:
    """調整の方向（設計書 6.8 の表を上から順に当てはめる）。"""
    pb = profile.p_mode == "pb"
    p_weaker = "比例帯を広げる" if pb else "比例ゲインを下げる"
    p_stronger = "比例帯を狭める" if pb else "比例ゲインを上げる"
    rpm = profile.i_unit == "rpm"
    i_weaker = "積分（回/分）を小さくする" if rpm else "積分時間を長くする"
    i_stronger = "積分（回/分）を大きくする" if rpm else "積分時間を短くする"

    if swinging and period is not None and pid.td > 0 and period < 4.0 * pid.td:
        return "短い周期の揺れが出ています。微分時間を短くする方向です。"
    if swinging and period is not None and pid.ti is not None and period > pid.ti:
        return f"積分時間より長い周期の揺れが出ています。{i_weaker}方向です。"
    if swinging:
        return f"揺れが出ています。{p_weaker}方向です。"
    if overshoot_pct > BIG_OVERSHOOT:
        return f"揺れはありませんが、行き過ぎが大きめです。{i_weaker}方向です。"
    if abs(offset) >= span * OFFSET_PCT / 100.0:
        if pid.ti is None:
            return "設定値からずれたまま戻っていません。積分動作を入れる方向です。"
        return f"設定値からずれたまま戻っていません。{i_stronger}方向です。"
    if settle is not None and proposed_settle is not None and proposed_settle > 0 and settle >= 2.0 * proposed_settle:
        return f"行き過ぎは小さいですが、落ち着くまでに時間がかかっています。{p_stronger}、または{i_stronger}方向です。"
    return "大きな問題は見当たりません。"
````


- [ ] **Step 4: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_diagnose.py -q`
Expected: `11 passed`

---

### Task 6: 提案の計算

**Files:**
- Create: `app/tuning.py`
- Test: `tests/test_tuning.py`

**Interfaces:**
- Consumes: `Fopdt`（Task 3）、`Pid`（Task 2）、`simulate_closed`（Task 3）、`step_metrics`（Task 5）
- Produces:
  - `propose(model, pref, span, dt_record, period_s, pv_noise, t_uncertain=False) -> Proposal`
  - `Proposal(pid: Pid, use_d: bool, ripple: float, l_used: float, slope_based: bool)`
  - `TAU_FACTOR = {"fast": 1.0, "normal": 2.0, "stable": 4.0}`、`PREF_LABELS = {"stable": "安定重視", "normal": "標準", "fast": "速さ重視"}`

- [ ] **Step 1: テストを書く**

`tests/test_tuning.py`

````python
import numpy as np
import pytest

from app import diagnose as dg
from app.controller import simulate_closed
from app.process_model import Fopdt
from app.profile import BUILTIN
from app.tuning import propose
from tests import synth

MODEL = Fopdt(k=0.42, t=85.0, l=18.0, b=43.2)


def test_pid_formula_matches_hand_calculation():
    r = propose(MODEL, "normal", 100.0, 1.0, 0.2, pv_noise=0.0)
    assert r.use_d and not r.slope_based and r.l_used == 18.0
    assert r.pid.kc == pytest.approx(94.0 / (0.42 * 45.0))       # (T + L/2) ÷ (K × (2L + L/2))
    assert r.pid.ti == pytest.approx(94.0)
    assert r.pid.td == pytest.approx(85.0 * 18.0 / 188.0)


def test_preference_changes_speed():
    kc = {pref: propose(MODEL, pref, 100.0, 1.0, 0.2, 0.0).pid.kc for pref in ("stable", "normal", "fast")}
    assert kc["stable"] < kc["normal"] < kc["fast"]
    assert kc["fast"] == pytest.approx(94.0 / (0.42 * 27.0))
    assert kc["stable"] == pytest.approx(94.0 / (0.42 * 81.0))


def test_gain_scales_with_input_range():
    wide = propose(MODEL, "normal", 200.0, 1.0, 0.2, 0.0)
    assert wide.pid.kc == pytest.approx(2.0 * 94.0 / (0.42 * 45.0))


def test_noisy_pv_drops_derivative_and_uses_pi_formula():
    r = propose(MODEL, "normal", 100.0, 1.0, 0.2, pv_noise=0.2)
    assert not r.use_d and r.ripple > 2.0
    assert r.pid.td == 0.0
    assert r.pid.kc == pytest.approx(85.0 / (0.42 * 54.0))       # T ÷ (K × (2L + L))
    assert r.pid.ti == pytest.approx(85.0)                       # T と 4 × (2L + L) の小さいほう


def test_pi_integral_time_is_capped_for_slow_process():
    slow = Fopdt(k=0.42, t=2000.0, l=18.0, b=43.2)
    r = propose(slow, "normal", 100.0, 1.0, 0.2, pv_noise=5.0)
    assert r.pid.ti == pytest.approx(4.0 * 54.0)


def test_dead_time_floor_avoids_infinite_gain():
    quick = Fopdt(k=0.42, t=85.0, l=0.0, b=43.2)
    r = propose(quick, "fast", 100.0, 2.0, 0.2, 0.0)
    assert r.l_used == 2.0 and np.isfinite(r.pid.kc)
    assert propose(quick, "fast", 100.0, 0.1, 0.2, 0.0).l_used == 0.4


def test_slope_based_formula_when_time_constant_is_uncertain():
    r = propose(MODEL, "normal", 100.0, 1.0, 0.2, 0.0, t_uncertain=True)
    ks = 0.42 / 85.0
    assert r.slope_based
    assert r.pid.kc == pytest.approx(1.0 / (ks * 45.0))
    assert r.pid.ti == pytest.approx(108.0)                     # T=85 と 2×(2L+L)=108 の大きいほう（上限 216）
    assert r.pid.td == pytest.approx(9.0)
    slow = Fopdt(k=4.2, t=850.0, l=18.0, b=0.0)
    assert propose(slow, "normal", 100.0, 1.0, 0.2, 0.0, t_uncertain=True).pid.ti == pytest.approx(216.0)


def test_cooling_process_uses_magnitude_of_gain():
    cooling = Fopdt(k=-0.42, t=85.0, l=18.0, b=80.0)
    assert propose(cooling, "normal", 100.0, 1.0, 0.2, 0.0).pid.kc > 0


@pytest.mark.parametrize("pref", ["stable", "normal", "fast"])
@pytest.mark.parametrize("uncertain", [False, True])
def test_proposal_is_well_behaved_on_the_true_process(pref, uncertain):
    r = propose(synth.TRUE, pref, synth.SPAN, 1.0, 0.2, 0.0, t_uncertain=uncertain)
    dt = 0.2
    t = np.arange(0.0, 1500.0, dt)
    sp = np.where(t >= 100.0, 65.0, 60.0)
    y, u = simulate_closed(synth.TRUE, r.pid, BUILTIN, synth.SPAN, sp, dt, y0=60.0)
    m = dg.step_metrics(t, sp, y, synth.SPAN)
    assert m.overshoot_pct < 25.0
    assert m.settle is not None and not m.swinging
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tuning.py -q`
Expected: `ModuleNotFoundError: No module named 'app.tuning'`

- [ ] **Step 3: 実装する**

`app/tuning.py`

````python
"""推定した設備の特性から、PID の提案値を計算する（IMC／SIMC 法）。"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.process_model import Fopdt
from app.profile import Pid

TAU_FACTOR = {"fast": 1.0, "normal": 2.0, "stable": 4.0}
PREF_LABELS = {"stable": "安定重視", "normal": "標準", "fast": "速さ重視"}
MAX_D_RIPPLE = 2.0      # 微分動作による出力のばたつきの上限 %


@dataclass
class Proposal:
    pid: Pid
    use_d: bool
    ripple: float           # PID にした場合の出力のばたつきの見積もり %
    l_used: float           # 計算に使ったむだ時間 秒
    slope_based: bool       # 時定数を絞れず、変化の速さ（K/T）から計算した


def propose(model: Fopdt, pref: str, span: float, dt_record: float, period_s: float,
            pv_noise: float, t_uncertain: bool = False) -> Proposal:
    """span は入力レンジの幅、dt_record は記録の間隔、period_s は制御周期（秒）。"""
    l = max(model.l, dt_record, 2.0 * period_s)
    t = model.t
    kn = abs(model.k) * 100.0 / span        # 単位なしの設備のゲイン
    tc = TAU_FACTOR[pref] * l

    if t_uncertain:
        # 時定数があてにならないので、変化の速さ（K/T）とむだ時間で決める。
        # 積分時間は、推定より設備がずっと遅くても揺れないよう 2 × (τc + L) を下限にする。
        ks = kn / t                         # 出力 1% あたりの変化の速さ（1 秒あたり）
        ti = min(max(t, 2.0 * (tc + l)), 4.0 * (tc + l))
        pi = Pid(kc=1.0 / (ks * (tc + l)), ti=ti, td=0.0)
        pid = Pid(kc=1.0 / (ks * (tc + l / 2.0)), ti=ti, td=l / 2.0)
    else:
        pi = Pid(kc=t / (kn * (tc + l)), ti=min(t, 4.0 * (tc + l)), td=0.0)
        pid = Pid(kc=(t + l / 2.0) / (kn * (tc + l / 2.0)), ti=t + l / 2.0, td=t * l / (2.0 * t + l))

    ripple = pid.kc * pid.td * (math.sqrt(2.0) * pv_noise / span * 100.0) / dt_record
    use_d = ripple < MAX_D_RIPPLE
    return Proposal(pid if use_d else pi, use_d, ripple, l, t_uncertain)
````


- [ ] **Step 4: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tuning.py -q`
Expected: `14 passed`

---

### Task 7: 解析のまとめ

**Files:**
- Create: `app/analysis.py`
- Test: `tests/test_analysis.py`

**Interfaces:**
- Consumes: Task 2〜6 のすべて
- Produces:
  - `AnalysisInput(t, sp, pv, out, profile, p, i, d, range_lo, range_hi, scene="auto", pref="normal", aux_in_use=False)`
  - `run_analysis(inp) -> AnalysisResult`（入力レンジが逆、データが 2 点未満のときは `ValueError`）
  - `AnalysisResult`：`scene`、`diag_rows: list[(項目, 値)]`、`ident`、`model_rows`、`current_text: (P, I, D の文字)`、`proposal`、`proposed_values: (p, i, d) | None`、`proposed_text | None`、`direction`、`reason`、`prediction: Prediction | None`、`reproduce_fit: float | None`、`warnings: list[str]`
  - `Prediction(t, sp, y_cur, y_new, cur: StepMetrics, new: StepMetrics)`

- [ ] **Step 1: テストを書く**

`tests/test_analysis.py`

````python
from dataclasses import replace

import numpy as np
import pytest

from app import diagnose as dg
from app.analysis import AnalysisInput, run_analysis
from app.profile import BUILTIN
from tests import synth


def _inp(rec, **kw):
    t, sp, pv, out = rec
    args = dict(t=t, sp=sp, pv=pv, out=out, profile=BUILTIN, p=10.0, i=45.0, d=None, range_lo=0.0, range_hi=100.0)
    args.update(kw)
    return AnalysisInput(**args)


def test_setpoint_change_gives_full_result():
    r = run_analysis(_inp(synth.sp_change()))
    assert r.scene == dg.SP_CHANGE
    assert r.current_text == ("10.0 %", "45 秒", "OFF")
    p, i, d = r.proposed_values
    assert 17.0 <= p <= 24.0 and 80.0 <= i <= 108.0 and 6.0 <= d <= 10.0      # 正解の設備なら 20.1 / 94 / 8
    assert r.proposed_text == (f"{p:.1f} %", f"{i:.0f} 秒", f"{d:.0f} 秒")
    assert [label for label, _ in r.diag_rows] == ["場面", "設定値", "行き過ぎ", "揺れの周期", "落ち着くまで"]
    assert dict(r.diag_rows)["設定値"] == "60 → 65"
    assert [label for label, _ in r.model_rows][1:] == ["反応の遅れ（時定数）", "動き出すまで（むだ時間）", "当てはまり具合"]
    assert "積分時間を長く" in r.direction
    assert r.reproduce_fit > 80.0 and r.warnings == []


def test_prediction_shows_improvement():
    r = run_analysis(_inp(synth.sp_change()))
    pr = r.prediction
    assert len(pr.t) == len(pr.sp) == len(pr.y_cur) == len(pr.y_new)
    assert (pr.sp[0], pr.sp[-1]) == (60.0, 65.0)
    assert abs(pr.cur.overshoot - 2.3) < 0.4
    assert pr.new.overshoot < 0.5 * pr.cur.overshoot
    assert pr.new.settle < pr.cur.settle


def test_preference_changes_proposal():
    p = {pref: run_analysis(_inp(synth.sp_change(), pref=pref)).proposed_values[0] for pref in ("stable", "normal", "fast")}
    assert p["stable"] > p["normal"] > p["fast"]                 # 安定重視ほど比例帯が広い


def test_manual_step_record():
    r = run_analysis(_inp(synth.manual_step()))
    assert r.scene == dg.MANUAL and r.proposed_values is not None
    assert 17.0 <= r.proposed_values[0] <= 24.0
    assert r.reproduce_fit is None and r.direction == ""
    assert r.prediction.sp[-1] == pytest.approx(r.prediction.sp[0] + 5.0)


def test_hunting_record_uses_slope_based_proposal():
    r = run_analysis(_inp(synth.hunting(), p=2.5, i=20.0))
    assert r.scene == dg.HUNTING and r.proposal.slope_based
    assert r.proposed_values[0] > 10.0                           # 比例帯を大きく広げる
    assert "時定数を一つに絞れなかった" in r.reason
    assert dict(r.model_rows)["反応の遅れ（時定数）"] == "一つに絞れません"
    assert not r.prediction.new.swinging


def test_no_numeric_proposal_when_output_did_not_move():
    t = np.arange(0.0, 600.0)
    rng = np.random.default_rng(0)
    rec = (t, np.full(600, 60.0), 60.0 + rng.normal(0, 0.02, 600), np.full(600, 40.0))
    r = run_analysis(_inp(rec))
    assert r.proposed_values is None and r.proposed_text is None and r.prediction is None
    assert r.reason.startswith("数値の提案は出せません。") and "出力の変化幅" in r.reason
    assert r.scene == dg.UNKNOWN and any("場面を自動で判定できません" in w for w in r.warnings)


def test_scene_can_be_forced():
    r = run_analysis(_inp(synth.sp_change(), scene=dg.HUNTING))
    assert r.scene == dg.HUNTING and r.diag_rows[1][0] == "揺れの幅"


def test_aux_function_flag_adds_warning():
    r = run_analysis(_inp(synth.sp_change(), aux_in_use=True))
    assert any("補助機能" in w for w in r.warnings)


def test_wrong_pid_entry_lowers_reproduction_and_warns():
    r = run_analysis(_inp(synth.sp_change(), p=100.0, i=600.0))
    assert r.reproduce_fit < 50.0 and any("記録と合いません" in w for w in r.warnings)


def test_gain_type_controller_profile():
    g = replace(BUILTIN, name="x", p_mode="gain", p_min=0.01, p_max=100.0, p_step=0.01,
                i_unit="min", i_min=0.01, i_max=100.0, i_step=0.01, d_unit="min", d_min=0.01, d_max=100.0, d_step=0.01)
    r = run_analysis(_inp(synth.sp_change(), profile=g, p=10.0, i=0.75, d=None))
    p, i, d = r.proposed_values
    assert 4.1 <= p <= 5.9 and 1.3 <= i <= 1.8 and 0.10 <= d <= 0.17
    assert r.current_text == ("10.00", "0.75 分", "OFF")


def test_narrow_range_changes_proportional_band_not_behavior():
    r = run_analysis(_inp(synth.sp_change(), p=20.0, range_lo=40.0, range_hi=90.0))   # 幅 50：同じ動きの比例帯は 2 倍
    assert 34.0 <= r.proposed_values[0] <= 48.0
    assert r.reproduce_fit > 80.0


def test_time_not_starting_at_zero():
    t, sp, pv, out = synth.sp_change()
    r = run_analysis(_inp((t + 3600.0, sp, pv, out)))
    assert r.proposed_values is not None and dict(r.diag_rows)["落ち着くまで"].endswith("秒")


def test_coarse_resolution_record():
    t, sp, pv, out = synth.sp_change()
    r = run_analysis(_inp((t, sp, np.round(pv, 1), np.round(out, 1))))      # 記録計の表示桁（0.1 刻み）
    assert 17.0 <= r.proposed_values[0] <= 24.0
    assert abs(float(dict(r.diag_rows)["行き過ぎ"].split("（")[0]) - 2.3) < 0.2


def test_slow_sampling_record():
    t, sp, pv, out = synth.sp_change()
    r = run_analysis(_inp((t[::5], sp[::5], pv[::5], out[::5])))            # 5 秒間隔の記録
    assert r.proposed_values is not None and 15.0 <= r.proposed_values[0] <= 27.0


def test_bad_range_is_rejected():
    with pytest.raises(ValueError):
        run_analysis(_inp(synth.sp_change(), range_lo=100.0, range_hi=0.0))
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_analysis.py -q`
Expected: `ModuleNotFoundError: No module named 'app.analysis'`

- [ ] **Step 3: 実装する**

`app/analysis.py`

````python
"""部品をつないで、1 回の解析結果をまとめる。画面はこの結果を表示するだけ。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app import diagnose, profile as prof
from app.controller import simulate_closed
from app.identify import IdentResult, identify
from app.process_model import Fopdt
from app.profile import ControllerProfile, Pid
from app.tuning import Proposal, propose

MAX_SIM_STEPS = 40000
LOW_REPRODUCE = 50.0


@dataclass
class AnalysisInput:
    t: np.ndarray               # 等間隔の経過秒（選んだ区間）
    sp: np.ndarray
    pv: np.ndarray
    out: np.ndarray
    profile: ControllerProfile
    p: float                    # 現在の設定（調節計の単位）
    i: float | None
    d: float | None
    range_lo: float
    range_hi: float
    scene: str = "auto"         # "auto" か diagnose の場面名
    pref: str = "normal"        # "stable" / "normal" / "fast"
    aux_in_use: bool = False


@dataclass
class Prediction:
    t: np.ndarray
    sp: np.ndarray
    y_cur: np.ndarray
    y_new: np.ndarray
    cur: diagnose.StepMetrics
    new: diagnose.StepMetrics


@dataclass
class AnalysisResult:
    scene: str
    diag_rows: list[tuple[str, str]]
    ident: IdentResult
    model_rows: list[tuple[str, str]]
    current_text: tuple[str, str, str]
    proposal: Proposal | None = None
    proposed_values: tuple[float, float | None, float | None] | None = None
    proposed_text: tuple[str, str, str] | None = None
    direction: str = ""
    reason: str = ""
    prediction: Prediction | None = None
    reproduce_fit: float | None = None
    warnings: list[str] = field(default_factory=list)


def _sec(x: float | None) -> str:
    return "区間内では落ち着いていません" if x is None else f"{x:.0f} 秒"


def _fit(a: np.ndarray, b: np.ndarray) -> float:
    total = float(np.linalg.norm(a - a.mean()))
    return 100.0 * (1.0 - float(np.linalg.norm(a - b)) / total) if total > 0 else 0.0


def _sim_dt(profile: ControllerProfile, horizon: float) -> float:
    return max(profile.period_ms / 1000.0, horizon / MAX_SIM_STEPS)


def _predict(model: Fopdt, profile: ControllerProfile, span: float, cur: Pid, new: Pid,
             sp0: float, sp1: float) -> Prediction:
    horizon = min(max(12.0 * (model.t + model.l), 60.0), 36000.0)
    dt = _sim_dt(profile, horizon)
    t = np.arange(0.0, horizon, dt)
    sp = np.where(t >= 0.08 * horizon, sp1, sp0)
    y_cur, _ = simulate_closed(model, cur, profile, span, sp, dt, y0=sp0)
    y_new, _ = simulate_closed(model, new, profile, span, sp, dt, y0=sp0)
    return Prediction(t, sp, y_cur, y_new,
                      diagnose.step_metrics(t, sp, y_cur, span), diagnose.step_metrics(t, sp, y_new, span))


def _reproduce(inp: AnalysisInput, model: Fopdt, span: float, cur: Pid) -> float:
    t = inp.t - inp.t[0]
    dt = _sim_dt(inp.profile, float(t[-1]))
    ts = np.arange(0.0, float(t[-1]) + dt, dt)
    sp = np.interp(ts, t, inp.sp)
    y, _ = simulate_closed(model, cur, inp.profile, span, sp, dt, y0=float(inp.pv[0]), u0=float(inp.out[0]))
    return _fit(inp.pv, np.interp(t, ts, y))


def run_analysis(inp: AnalysisInput) -> AnalysisResult:
    p = inp.profile
    span = inp.range_hi - inp.range_lo
    if span <= 0:
        raise ValueError("入力レンジは、上限が下限より大きくなるように入力してください。")
    if len(inp.t) < 2:
        raise ValueError("区間内のデータが足りません。")
    cur = prof.to_pid(p, inp.p, inp.i, inp.d)
    current_text = (prof.format_p(p, inp.p), prof.format_i(p, inp.i), prof.format_d(p, inp.d))
    t, sp, pv, out = inp.t - inp.t[0], inp.sp, inp.pv, inp.out
    dt_record = float(t[1] - t[0])
    warnings: list[str] = []

    scene = diagnose.detect_scene(t, sp, pv, out, span) if inp.scene == "auto" else inp.scene
    rows: list[tuple[str, str]] = [("場面", diagnose.SCENE_LABELS[scene])]
    swinging, period, overshoot_pct, offset, settle = False, None, 0.0, 0.0, None
    step = None
    if scene == diagnose.SP_CHANGE:
        step = diagnose.step_metrics(t, sp, pv, span)
        swinging, period, overshoot_pct, offset, settle = step.swinging, step.period, step.overshoot_pct, step.offset, step.settle
        rows += [
            ("設定値", f"{step.sp0:g} → {step.sp1:g}"),
            ("行き過ぎ", f"{step.overshoot:.1f}（変化幅の {step.overshoot_pct:.0f}%）"),
            ("揺れの周期", "揺れなし" if step.period is None else f"{step.period:.0f} 秒"),
            ("落ち着くまで", _sec(step.settle)),
        ]
        if step.multi_step:
            warnings.append("区間内で設定値が何度も変わっています。1 回分だけを選ぶと、診断が正確になります。")
    elif scene == diagnose.HUNTING:
        h = diagnose.hunt_metrics(t, sp, pv, out, span, p.out_min, p.out_max)
        swinging, period, offset = h.swinging, h.period, h.offset
        rows += [
            ("揺れの幅", f"測定値 {h.pv_pp:.1f}／出力 {h.out_pp:.0f}%"),
            ("揺れの周期", "判定できません" if h.period is None else f"{h.period:.0f} 秒"),
            ("揺れの傾向", h.trend),
            ("出力の張り付き", f"区間の {100 * h.saturated:.0f}%"),
        ]
    elif scene == diagnose.MANUAL:
        m = diagnose.manual_metrics(t, pv, out)
        rows += [
            ("出力の変化", f"{m.d_out:+.1f}%"),
            ("測定値の変化", f"{m.d_pv:+.1f}"),
            ("63% に達するまで", "判定できません" if m.t63 is None else f"{m.t63:.0f} 秒"),
        ]
    else:
        warnings.append("場面を自動で判定できませんでした。「場面」を手で選ぶと、診断の項目が出ます。")

    ident = identify(t, out, pv, span, p.reverse)
    model_rows: list[tuple[str, str]] = []
    if ident.model is not None:
        m_ = ident.model
        if ident.t_uncertain:
            model_rows = [
                ("出力 1% あたりの変化の速さ", f"{m_.k / m_.t * 60:.2f} /分"),
                ("反応の遅れ（時定数）", "一つに絞れません"),
            ]
        else:
            model_rows = [
                ("出力 1% あたりの測定値の変化", f"{m_.k:.2f}"),
                ("反応の遅れ（時定数）", f"{m_.t:.0f} 秒"),
            ]
        model_rows += [("動き出すまで（むだ時間）", f"{m_.l:.0f} 秒"), ("当てはまり具合", f"{ident.fit:.0f} %")]

    result = AnalysisResult(scene, rows, ident, model_rows, current_text, warnings=warnings)
    proposed_settle = None
    if ident.ok:
        proposal = propose(ident.model, inp.pref, span, dt_record, p.period_ms / 1000.0,
                           diagnose.noise_sd(pv), ident.t_uncertain)
        values = prof.from_pid(p, proposal.pid)
        new = prof.to_pid(p, values[0], values[1], values[2])
        result.proposal = proposal
        result.proposed_values = values[:3]
        result.proposed_text = (prof.format_p(p, values[0]), prof.format_i(p, values[1]), prof.format_d(p, values[2]))

        if step is not None and step.sp1 != step.sp0:
            sp0, sp1 = step.sp0, step.sp1
        else:
            sp0 = float(np.mean(pv))
            sp1 = sp0 + 0.05 * span if sp0 + 0.05 * span <= inp.range_hi else sp0 - 0.05 * span
        pred = _predict(ident.model, p, span, cur, new, sp0, sp1)
        result.prediction = pred
        proposed_settle = pred.new.settle
        worse_over = pred.new.overshoot > pred.cur.overshoot + 1e-9
        worse_settle = pred.cur.settle is not None and (pred.new.settle is None or pred.new.settle > pred.cur.settle)
        if worse_over and worse_settle:
            warnings.append("予想では、提案の設定のほうが行き過ぎ・落ち着くまでの時間とも悪くなっています。現在の設定のままでよい可能性があります。")

        if scene == diagnose.SP_CHANGE:
            result.reproduce_fit = _reproduce(inp, ident.model, span, cur)
            if result.reproduce_fit < LOW_REPRODUCE:
                warnings.append("現在の設定で計算した波形が、記録と合いません。入力した PID・入力レンジ・計算のしかたが実機と違うか、記録に外乱が含まれている可能性があります。")

        notes = list(values[3])
        if proposal.slope_based:
            notes.append("時定数を一つに絞れなかったため、変化の速さとむだ時間から計算しました。積分は弱め（安全側）の値です。")
        if not proposal.use_d:
            notes.append("測定値のばらつきが大きく、微分動作を入れると出力がばたつく見込みのため、微分は OFF にしています。")
        result.reason = " ".join(notes)
    else:
        result.reason = "数値の提案は出せません。" + " ".join(ident.reasons)

    if scene in (diagnose.SP_CHANGE, diagnose.HUNTING):
        result.direction = diagnose.advise(p, cur, span, swinging, period, overshoot_pct, offset, settle, proposed_settle)
    if inp.aux_in_use:
        warnings.append("補助機能（オーバーシュート抑制など）を使用中の記録です。推定がずれている可能性があります。")
    return result
````


- [ ] **Step 4: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_analysis.py -q`
Expected: `15 passed`

- [ ] **Step 5: ここまでの全テストを実行する**

Run: `.venv/Scripts/python.exe -m pytest tests -q`
Expected: `83 passed`

---

### Task 8: CSV の読み込み

**Files:**
- Create: `app/csv_loader.py`
- Test: `tests/test_csv_loader.py`

**Interfaces:**
- Consumes: なし（標準ライブラリと numpy のみ）
- Produces:
  - `read_table(path) -> RawTable(headers, rows, encoding, skipped)`（読めないときは `ValueError`。文面はそのまま画面に出せる日本語）
  - `guess_columns(headers) -> {"time": int | None, "sp": ..., "out": ..., "pv": ...}`
  - `build_series(table, time_col, sp_col, out_col, pv_col, dt_manual=None) -> Series(t, sp, out, pv, dt, dropped, notes)`（`time_col=None` のとき `dt_manual` 秒間隔とみなす）

- [ ] **Step 1: テストを書く**

`tests/test_csv_loader.py`

````python
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
    text = "記録計 GM10\n開始,2026/11/14\n\n時刻,CH1,CH2,CH3\n,℃,%,℃\n10:00:00,60,40,60.1\n10:00:01,60,41,60.2\n10:00:02,60,42,60.3\n"
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
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_csv_loader.py -q`
Expected: `ModuleNotFoundError: No module named 'app.csv_loader'`

- [ ] **Step 3: 実装する**

`app/csv_loader.py`

````python
"""CSV の読み込み。記録計や Excel から出した CSV を、そのまま読めるようにする。"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

_EPOCH = datetime(2000, 1, 1)
_DATE_FORMATS = [
    "%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
]
_TIME_FORMATS = ["%H:%M:%S.%f", "%H:%M:%S", "%H:%M"]
_KEYWORDS = {
    "time": ["時刻", "日時", "時間", "time", "date"],
    "sp": ["設定", "目標", "sp", "sv"],
    "out": ["出力", "開度", "操作", "out", "mv"],
    "pv": ["水温", "温度", "測定", "pv"],
}


@dataclass
class RawTable:
    headers: list[str]
    rows: list[list[str]]       # 数値の行（文字のまま）
    encoding: str
    skipped: int                # 列数が合わずに捨てた行数


@dataclass
class Series:
    t: np.ndarray               # 先頭を 0 とした経過秒（等間隔）
    sp: np.ndarray
    out: np.ndarray
    pv: np.ndarray
    dt: float
    dropped: int                # 数値に直せずに捨てた行数
    notes: list[str] = field(default_factory=list)


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def _is_data_row(row: list[str]) -> bool:
    return sum(_is_number(c.strip()) for c in row) >= 2


def read_table(path: str | Path) -> RawTable:
    data = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp932"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("文字コードを判定できません。UTF-8 か Shift-JIS の CSV で保存し直してください。")

    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    sample = lines[:30]
    delimiter = max([",", "\t", ";"], key=lambda d: sum(ln.count(d) for ln in sample))
    rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)]

    start = None
    for i in range(len(rows)):
        block = rows[i:i + 3]
        if len(block) >= 2 and all(_is_data_row(r) and len(r) == len(rows[i]) for r in block):
            start = i
            break
    if start is None:
        raise ValueError("数値の列が見つかりません。時刻・設定値・出力・測定値が列に並んだ CSV を選んでください。")
    ncol = len(rows[start])

    names = [""] * ncol
    for r in rows[max(start - 2, 0):start]:
        if len(r) == ncol and not _is_data_row(r):
            names = [(a + " " + b).strip() for a, b in zip(names, r)]
    headers = [n if n else f"列{k + 1}" for k, n in enumerate(names)]

    body = [r for r in rows[start:] if len(r) == ncol]
    return RawTable(headers, body, encoding, len(rows) - start - len(body))


def guess_columns(headers: list[str]) -> dict[str, int | None]:
    """見出しの名前から、時刻・設定値・出力・測定値の列を推測する。"""
    result: dict[str, int | None] = {}
    used: set[int] = set()
    for key in ("time", "sp", "out", "pv"):
        result[key] = None
        for k, h in enumerate(headers):
            if k not in used and any(w in h.lower() for w in _KEYWORDS[key]):
                result[key] = k
                used.add(k)
                break
    return result


def _time_parser(sample: str):
    """最初の値に合う読み方を選ぶ。合うものが無ければ None。"""
    if _is_number(sample):
        return float
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(sample, fmt)
            return lambda s, f=fmt: (datetime.strptime(s, f) - _EPOCH).total_seconds()
        except ValueError:
            pass
    for fmt in _TIME_FORMATS:
        try:
            datetime.strptime(sample, fmt)

            def clock(s, f=fmt):
                d = datetime.strptime(s, f)
                return d.hour * 3600.0 + d.minute * 60.0 + d.second + d.microsecond / 1e6
            return clock
        except ValueError:
            pass
    return None


def build_series(table: RawTable, time_col: int | None, sp_col: int, out_col: int, pv_col: int,
                 dt_manual: float | None = None) -> Series:
    """選んだ列を数値にして、等間隔の記録にする。time_col が None のときは dt_manual 秒間隔とみなす。"""
    notes: list[str] = []
    parser = None
    if time_col is not None:
        parser = _time_parser(table.rows[0][time_col]) if table.rows else None
        if parser is None:
            raise ValueError("時刻の列を読めません。日時（例 2026/11/14 10:00:00）か、秒の数値の列を選んでください。")
    elif dt_manual is None or dt_manual <= 0:
        raise ValueError("時刻の列が無いときは、記録の間隔（秒）を入力してください。")

    ts, sps, outs, pvs = [], [], [], []
    dropped = 0
    for row in table.rows:
        try:
            values = (float(row[sp_col]), float(row[out_col]), float(row[pv_col]))
            tv = parser(row[time_col]) if parser is not None else 0.0
        except ValueError:
            dropped += 1
            continue
        if not all(np.isfinite(values)):
            dropped += 1
            continue
        ts.append(tv)
        sps.append(values[0])
        outs.append(values[1])
        pvs.append(values[2])
    if len(ts) < 2:
        raise ValueError("数値として読める行が 2 行未満です。列の選び方を確認してください。")

    sp, out, pv = np.array(sps), np.array(outs), np.array(pvs)
    if parser is None:
        t = np.arange(len(ts)) * float(dt_manual)
    else:
        t = np.array(ts)
        back = np.diff(t) < -43200.0                     # 時刻だけの列で日付をまたいだ
        if back.any():
            t[1:] += 86400.0 * np.cumsum(back)
        if np.any(np.diff(t) < 0):
            order = np.argsort(t, kind="stable")
            t, sp, out, pv = t[order], sp[order], out[order], pv[order]
            notes.append("時刻が前後していたので、時刻の順に並べ直しました。")
        keep = np.concatenate([[True], np.diff(t) > 0])
        if not keep.all():
            notes.append(f"同じ時刻の行が {int((~keep).sum())} 行あったので、最初の 1 行だけ使いました。")
            t, sp, out, pv = t[keep], sp[keep], out[keep], pv[keep]
        if len(t) < 2:
            raise ValueError("時刻の違う行が 2 行未満です。時刻の列の選び方を確認してください。")
        t = t - t[0]

    dt = float(np.median(np.diff(t)))
    if np.max(np.abs(np.diff(t) - dt)) > 0.01 * dt:
        grid = np.arange(0.0, t[-1] + dt * 0.5, dt)
        sp, out, pv = np.interp(grid, t, sp), np.interp(grid, t, out), np.interp(grid, t, pv)
        t = grid
        notes.append("記録の間隔がばらついていたので、等間隔に直しました。")
    return Series(t, sp, out, pv, dt, dropped, notes)
````


- [ ] **Step 4: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_csv_loader.py -q`
Expected: `26 passed`

---

### Task 9: 見た目の部品・起動・アイコン・見本データ

**Files:**
- Create: `app/ui/__init__.py`（空）、`app/ui/widgets.py`、`app/ui/style.qss`、`app/main.py`
- Create: `app/assets/icon.svg`、`app/assets/icon_small.svg`、`app/assets/chevron.svg`
- Create: `tools/make_icon.py`、`tools/make_samples.py`、`tests/conftest.py`
- Create（道具で作る）: `app/assets/app.ico`、`samples/sp_change.csv`、`samples/hunting.csv`、`samples/manual_step.csv`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `tests.synth`（Task 3）、`read_table / guess_columns / build_series`（Task 8）、`app.profile`（Task 2）
- Produces:
  - `app.ui.widgets`：`ASSETS: Path`、`load_style() -> str`、`label(text, name="", wrap=False) -> QLabel`、`Card(title="")`（`.box` が中身の縦並び）、`Segmented(options, value)`（`.value()`、`.set_value(key)`、`changed` シグナル）、`Rows()`（`.set_rows(rows)`、`.texts()`）
  - `app.main`：`create_app(argv) -> QApplication`（文字・アイコン・見た目・タスクバー用の ID を設定）、`main()`
  - `tools.make_icon`：`SIZES`、`render_png(svg_path, size) -> bytes`、`build_ico(out_path, assets=ASSETS)`、`read_ico_sizes(path) -> list[int]`
  - `tools.make_samples`：`make_samples(folder=SAMPLES) -> list[Path]`
  - `tests/conftest.py`：フィクスチャ `qapp`（テスト用のアプリ）、`no_dialogs`（メッセージの窓を出さずに文面を記録する）

`app/main.py` は Task 11 で作る `app.ui.main_window` を `main()` の中で読み込む。このタスクの時点では `main()` を実行しない（`create_app` だけを使う）。

- [ ] **Step 1: テストを書く**

`tests/conftest.py`

````python
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
````


`tests/test_tools.py`

````python
import numpy as np

from app.csv_loader import build_series, guess_columns, read_table
from app.ui.widgets import ASSETS
from tools.make_icon import SIZES, build_ico, read_ico_sizes, render_png
from tools.make_samples import make_samples

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_icon_sources_exist():
    for name in ("icon.svg", "icon_small.svg", "chevron.svg"):
        assert (ASSETS / name).is_file()


def test_png_is_rendered_with_blue_background_and_white_curve(qapp):
    from PyQt6.QtGui import QImage
    png = render_png(ASSETS / "icon.svg", 256)
    assert png.startswith(PNG_MAGIC)
    image = QImage.fromData(png)
    assert (image.width(), image.height()) == (256, 256)
    assert image.pixelColor(128, 230).name() == "#0a66d8"       # 地の青
    assert image.pixelColor(126, 60).name() == "#ffffff"        # 波形の山
    assert image.pixelColor(1, 1).alpha() == 0                  # 角は透明


def test_ico_contains_seven_sizes(qapp, tmp_path):
    path = tmp_path / "app.ico"
    build_ico(path)
    assert read_ico_sizes(path) == SIZES == [16, 24, 32, 48, 64, 128, 256]
    assert path.read_bytes().count(PNG_MAGIC) == 7


def test_samples_are_readable_by_the_app(tmp_path):
    paths = make_samples(tmp_path / "見本 データ")
    assert [p.name for p in paths] == ["sp_change.csv", "hunting.csv", "manual_step.csv"]
    for path, rows in zip(paths, (901, 901, 601)):
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")     # Excel で文字化けしない UTF-8（BOM 付き）
        table = read_table(path)
        cols = guess_columns(table.headers)
        assert cols == {"time": 0, "sp": 1, "out": 2, "pv": 3}
        s = build_series(table, cols["time"], cols["sp"], cols["out"], cols["pv"])
        assert len(s.t) == rows and s.dt == 1.0 and s.dropped == 0 and s.notes == []
    s = build_series(read_table(paths[0]), 0, 1, 2, 3)
    assert np.isclose(s.sp[0], 60.0) and np.isclose(s.sp[-1], 65.0)
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tools.py -q`
Expected: `ModuleNotFoundError: No module named 'app.ui'`

- [ ] **Step 3: 絵と見た目のファイルを作る**

`app/assets/icon.svg`（通常版。設計書 4.6 節）

````xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect x="8" y="8" width="240" height="240" rx="56" fill="#0A66D8"/>
  <path d="M44,100 L212,100" stroke="#FFFFFF" stroke-opacity="0.6" stroke-width="8" stroke-dasharray="12 12" fill="none"/>
  <path d="M40,196 L62,196 C92,196 94,60 126,60 C150,60 152,114 176,110 C192,107 200,100 216,100" stroke="#FFFFFF" stroke-width="18" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
````


`app/assets/icon_small.svg`（32px 以下用の簡略版）

````xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect x="8" y="8" width="240" height="240" rx="56" fill="#0A66D8"/>
  <path d="M40,196 L62,196 C92,196 94,60 126,60 C150,60 152,114 176,110 C192,107 200,100 216,100" stroke="#FFFFFF" stroke-width="26" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
````


`app/assets/chevron.svg`（選択欄の下向き矢印）

````xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
  <path d="M1.5,3.5 L5,7 L8.5,3.5" stroke="#5F5F66" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
````


`app/ui/style.qss`

````css
/* Mac風の見た目。{ASSETS} は読み込み時にアイコン置き場のパスに置き換える。 */
QMainWindow, QDialog { background: #FFFFFF; }
QWidget { color: #1D1D1F; font-size: 13px; }
QToolTip { background: #FFFFFF; color: #1D1D1F; border: 1px solid #C9C9CE; }

#toolbar { background: #F6F6F7; border-bottom: 1px solid #DCDCE0; }
#sidebar, #sidebarBody { background: #F3F3F5; }
#sidebar { border: none; border-right: 1px solid #DEDEE2; }
#inspector, #inspectorBody { background: #FAFAFB; }
#inspector { border: none; border-left: 1px solid #DEDEE2; }
#center { background: #FFFFFF; }
#dialogBody { background: #F3F3F5; }

#card { background: #FFFFFF; border: 1px solid #E2E2E6; border-radius: 10px; }
#card QLabel { background: transparent; }

QLabel#sectionTitle { color: #5F5F66; font-size: 12px; font-weight: bold; padding-left: 4px; }
QLabel#cardTitle { font-size: 14px; font-weight: bold; }
QLabel#muted { color: #5F5F66; font-size: 12px; }
QLabel#proposed { color: #0A4FB0; font-size: 17px; font-weight: bold; }
QLabel#chip { background: #E8F0FC; color: #0A4FB0; border-radius: 9px; padding: 2px 10px; font-size: 12px; }
QLabel#warning { background: #FFF6E5; color: #7A4B00; border: 1px solid #F1D9A8; border-radius: 8px; padding: 8px 10px; font-size: 12px; }
QLabel#statBox { background: #F6F6F7; border-radius: 8px; padding: 8px 12px; }
QLabel#statBoxNew { background: #E8F0FC; border-radius: 8px; padding: 8px 12px; }

QPushButton { background: #FFFFFF; border: 1px solid #C9C9CE; border-radius: 7px; padding: 0 12px; min-height: 30px; }
QPushButton:hover { background: #F3F3F5; }
QPushButton:pressed { background: #E8E8EC; }
QPushButton:disabled { color: #A0A0A6; }
QPushButton#primary { background: #0A66D8; color: #FFFFFF; border: none; font-weight: bold; padding: 0 18px; }
QPushButton#primary:hover { background: #0958BC; }
QPushButton#primary:pressed { background: #084CA3; }
QPushButton#primary:disabled { background: #9DBFEA; color: #FFFFFF; }

#segment { background: #E2E2E7; border-radius: 8px; }
QPushButton#seg { background: transparent; border: none; border-radius: 6px; min-height: 26px; padding: 0 6px; }
QPushButton#seg:hover { background: #D6D6DC; }
QPushButton#seg:checked { background: #FFFFFF; font-weight: bold; }

QLineEdit, QComboBox { background: #FFFFFF; border: 1px solid #D0D0D5; border-radius: 6px; min-height: 26px; padding: 0 8px; selection-background-color: #0A66D8; selection-color: #FFFFFF; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #0A66D8; }
QLineEdit:disabled, QComboBox:disabled { background: #F3F3F5; color: #8A8A90; }
QLineEdit[invalid="true"] { border: 1px solid #D92D20; background: #FEF3F2; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: url({ASSETS}/chevron.svg); width: 10px; height: 10px; }
QComboBox QAbstractItemView { background: #FFFFFF; border: 1px solid #C9C9CE; selection-background-color: #0A66D8; selection-color: #FFFFFF; outline: none; }

QScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #C4C4CA; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
````


- [ ] **Step 4: 部品と起動部分を実装する**

`app/ui/__init__.py` は空のファイルとして作る。

`app/ui/widgets.py`

````python
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
                w.deleteLater()
        for r, (name, value) in enumerate(rows):
            self._grid.addWidget(label(name, "muted"), r, 0, Qt.AlignmentFlag.AlignTop)
            v = label(value, wrap=True)
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            self._grid.addWidget(v, r, 1)

    def texts(self) -> list[tuple[str, str]]:
        items = [self._grid.itemAt(k).widget().text() for k in range(self._grid.count())]
        return list(zip(items[0::2], items[1::2]))
````


`app/main.py`

````python
"""起動。"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime

from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from app import APP_NAME
from app import profile as prof
from app.ui.widgets import ASSETS, load_style

APP_USER_MODEL_ID = "PidTuningAdvisor.App"


def _set_taskbar_identity() -> None:
    """Python で動かしても、タスクバーに自分のアイコンが出るようにする（Windows のみ）。"""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)


def _excepthook(exc_type, exc, tb) -> None:
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    folder = prof.data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "error.log", "a", encoding="utf-8") as f:
        f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{text}\n")
    QMessageBox.critical(None, APP_NAME, f"エラーが起きました。\n記録先: {folder / 'error.log'}\n\n{text[-600:]}")


def create_app(argv: list[str]) -> QApplication:
    _set_taskbar_identity()
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    family = "Meiryo UI" if "Meiryo UI" in QFontDatabase.families() else "Meiryo"
    app.setFont(QFont(family))
    app.setWindowIcon(QIcon(str(ASSETS / "app.ico")))
    app.setStyleSheet(load_style())
    return app


def main() -> None:
    app = create_app(sys.argv)
    sys.excepthook = _excepthook
    from app.ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````


- [ ] **Step 5: 道具を実装する**

`tools/make_icon.py`

````python
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
````


`tools/make_samples.py`

````python
"""見本の CSV を samples フォルダに作る（計算で作った架空のデータ）。

使い方（プロジェクトのフォルダで）:  .venv\\Scripts\\python.exe -m tools.make_samples
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

from tests import synth

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
START = datetime(2026, 11, 14, 10, 0, 0)


def write_sample(path: Path, record) -> None:
    t, sp, pv, out = record
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["日時", "設定値", "出力", "水温"])
        for k in range(len(t)):
            stamp = (START + timedelta(seconds=float(t[k]))).strftime("%Y/%m/%d %H:%M:%S")
            w.writerow([stamp, f"{sp[k]:.1f}", f"{out[k]:.1f}", f"{pv[k]:.2f}"])


def make_samples(folder: Path = SAMPLES) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    items = [("sp_change.csv", synth.sp_change()), ("hunting.csv", synth.hunting()), ("manual_step.csv", synth.manual_step())]
    for name, record in items:
        write_sample(folder / name, record)
    return [folder / name for name, _ in items]


if __name__ == "__main__":
    for p in make_samples():
        sys.stdout.buffer.write(f"{p}\n".encode("utf-8"))
````


- [ ] **Step 6: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tools.py -q`
Expected: `4 passed`

- [ ] **Step 7: アイコンファイルと見本データを作る**

Run: `.venv/Scripts/python.exe -m tools.make_icon`
Expected: `...app\assets\app.ico を作りました: [16, 24, 32, 48, 64, 128, 256]`

Run: `.venv/Scripts/python.exe -m tools.make_samples`
Expected: `samples` フォルダの 3 つの CSV のパスが表示される。

- [ ] **Step 8: アイコンを目で確かめる**

`tools.make_icon.render_png` で 256px と 16px の PNG を scratchpad に書き出し、Read ツールで開いて確かめる（青い角丸の四角に白い波形。16px でも波形が見える）。

---

### Task 10: 調節計の設定画面

**Files:**
- Create: `app/ui/settings_dialog.py`
- Test: `tests/test_settings_dialog.py`

**Interfaces:**
- Consumes: `app.profile`（Task 2）、`Card / Segmented / label`（Task 9）、フィクスチャ `qapp`・`no_dialogs`（Task 9）
- Produces:
  - `SettingsDialog(profiles, current, data_dir=None, parent=None)`
  - 保存して閉じると `exec()` が 1 を返し、`selected_name` に保存したプロファイルの名前が入る
  - テストから使う部品：`edits: dict[str, QLineEdit]`（キーは `p_min` … `out_max`）、`p_mode / i_unit / d_unit / reverse`（`Segmented`）、`i_off / d_off`（チェック）、`combo`、`btn_copy / btn_reset / btn_save / btn_cancel`、`duplicate_as(name) -> bool`、`read_form() -> ControllerProfile`

同梱のプロファイル（UT35A / UT32A）を選んでいる間は、入力欄と［保存］を使えなくする。「複製して新規」で作ったプロファイルは、［保存］を押すまでファイルに書かない。

- [ ] **Step 1: テストを書く**

`tests/test_settings_dialog.py`

````python
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
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_settings_dialog.py -q`
Expected: `ModuleNotFoundError: No module named 'app.ui.settings_dialog'`

- [ ] **Step 3: 実装する**

`app/ui/settings_dialog.py`

````python
"""調節計の設定画面：プロファイルを選び、値を変えて保存する。"""
from __future__ import annotations

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
        if name == "" or any(p.name == name for p in self._profiles):
            QMessageBox.warning(self, "調節計の設定", "名前が空か、同じ名前のプロファイルがすでにあります。")
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
        self.selected_name = p.name
        self.accept()
````


- [ ] **Step 4: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_settings_dialog.py -q`
Expected: `5 passed`

---

### Task 11: メイン画面

**Files:**
- Create: `app/ui/main_window.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `run_analysis / AnalysisInput / AnalysisResult`（Task 7）、`read_table / guess_columns / build_series`（Task 8）、`app.ui.widgets`・`create_app`・`make_samples`（Task 9）、`SettingsDialog`（Task 10）
- Produces:
  - `MainWindow(data_dir=None)`：`load_csv(path)`、`set_region(a, b)`、`analyze()`、`copy_proposal()`、`open_settings()`
  - テストから使う部品：`btn_open / btn_analyze / btn_copy / btn_settings`、`file_label`、`profile_combo`、`col_combos["time" | "sp" | "out" | "pv"]`、`dt_edit`、`data_note`、`pid_edits["p" | "i" | "d"]`、`pid_names`、`pid_units`、`range_edits["lo" | "hi"]`、`scene_combo`、`pref`、`aux_check`、`region_label`、`curve_pv`、`curve_pred_new`、`pred_title`、`stat_cur / stat_new`、`res_names / res_cur / res_new`、`reason_label`、`diag_rows`、`model_rows`、`direction_label`、`warning_label`、`result`、`table`

画面の配置・色・文言は、設計書 4 章と画面デザイン（開発時に Claude Design で作成。非公開）に合わせる。

- [ ] **Step 1: テストを書く**

`tests/test_main_window.py`

````python
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
````


- [ ] **Step 2: 実行して、失敗することを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_main_window.py -q`
Expected: `ModuleNotFoundError: No module named 'app.ui.main_window'`

- [ ] **Step 3: 実装する**

`app/ui/main_window.py`

````python
"""メイン画面。計算は app.analysis に任せ、ここは入力を集めて結果を表示するだけ。"""
from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
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
            value = prof.parse_entry(edit.text())
            ok = value is not None or allow_off
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
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = run_analysis(inp)
        except ValueError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        except Exception:
            self._report_error(traceback.format_exc())
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._show_result(result)

    def _report_error(self, text: str) -> None:
        folder = prof.data_dir(self._data_dir)
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "error.log", "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{text}\n")
        QMessageBox.critical(self, APP_NAME, f"解析の途中でエラーが起きました。\n記録先: {folder / 'error.log'}\n\n{text[-600:]}")

    def _clear_result(self) -> None:
        self.result = None
        for key in ("p", "i", "d"):
            self.res_cur[key].setText("—")
            self.res_new[key].setText("—")
        self.pref_chip.setVisible(False)
        self.reason_label.setText("CSV を開いて［解析する］を押すと、ここに修正案が出ます。")
        self.btn_copy.setEnabled(False)
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
````


- [ ] **Step 4: 実行して、通ることを確かめる**

Run: `.venv/Scripts/python.exe -m pytest tests/test_main_window.py -q`
Expected: `10 passed`

このファイルは試作の段階で動かせていない。失敗したら、エラーの文面から原因を特定して直す（テストの期待値を先に疑わず、画面のコードを確かめる）。窓を画面に出さない設定（offscreen）でクリップボードが使えずに `test_load_sample_and_analyze` の最後の行だけが落ちる場合は、原因を確かめたうえで、その 1 行を `w.result.proposed_text` と文面の組み立ての確認に置き換える。

- [ ] **Step 5: 全テストを実行する**

Run: `.venv/Scripts/python.exe -m pytest tests -q`
Expected: `128 passed`

---

### Task 12: 起動用のファイル・説明・実機での確認

**Files:**
- Create: `起動.bat`、`ショートカット作成.bat`、`tools/make_shortcut.py`、`README.md`

**Interfaces:**
- Consumes: `app.main.main`（Task 9、11）、`app/assets/app.ico`（Task 9）
- Produces: `tools.make_shortcut.make_shortcut(root=ROOT) -> Path`（`PID調整アドバイザー.lnk` を作る）

- [ ] **Step 1: ファイルを作る**

`起動.bat`（文字コードは UTF-8、BOM なし。1 行目の `chcp 65001` で日本語の表示を合わせる）

````bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo .venv フォルダがありません。README.md の「開発者向け」の手順で用意してください。
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m app.main
````


`ショートカット作成.bat`

````bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" -m tools.make_shortcut
pause
````


`tools/make_shortcut.py`

````python
"""アイコン付きのショートカットを、プロジェクトのフォルダに作る。

使い方: ショートカット作成.bat をダブルクリック
"""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "PID調整アドバイザー"


def _q(path: Path | str) -> str:
    """PowerShell の文字列として安全に書く。"""
    return "'" + str(path).replace("'", "''") + "'"


def make_shortcut(root: Path = ROOT) -> Path:
    lnk = root / f"{NAME}.lnk"
    pythonw = root / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        raise FileNotFoundError(f"{pythonw} がありません。先に .venv を用意してください。")
    script = "\n".join([
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({_q(lnk)})",
        f"$s.TargetPath = {_q(pythonw)}",
        "$s.Arguments = '-m app.main'",
        f"$s.WorkingDirectory = {_q(root)}",
        f"$s.IconLocation = {_q(str(root / 'app' / 'assets' / 'app.ico') + ',0')}",
        f"$s.Description = {_q(NAME)}",
        "$s.Save()",
    ])
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded], check=True)
    return lnk


if __name__ == "__main__":
    path = make_shortcut()
    sys.stdout.buffer.write(f"{path} を作りました。\n".encode("utf-8"))
````


`README.md`

````markdown
# PID調整アドバイザー

温度調節計の記録（設定値・出力%・測定値）と、今の P・I・D の設定から、
P・I・D をどう直せばよいかを示す Windows アプリです。

初期設定は横河電機 UT35A / UT32A に合わせてあります。ほかの調節計で使うときは、
［設定…］から「複製して新規」で値を変えて保存します。

## 起動

1. `起動.bat` をダブルクリックします。
2. アイコン付きのショートカットが欲しいときは、`ショートカット作成.bat` を 1 回実行します。
   フォルダの中に「PID調整アドバイザー」のショートカットができます。

## 使い方

1. ［CSVを開く］で記録ファイルを選びます（`samples` フォルダに見本があります）。
2. 「データの列」で、時刻・設定値・出力・測定値の列を選びます。
3. 「現在のPID設定」と「入力レンジ」を入力します。使っていない動作は `OFF` と入力します。
4. グラフの青い帯の両端をドラッグして、解析する区間を選びます。
5. ［解析する］を押すと、右側に修正案、中央下に予想グラフが出ます。

## 見本データ

`samples` フォルダの CSV は、計算で作った架空の設備のデータです。

| ファイル | 場面 | 入力する現在の設定 |
|---|---|---|
| `sp_change.csv` | 設定値を 60→65℃ に変更 | P 10.0 / I 45 / D OFF |
| `hunting.csv` | 設定値一定で温度が揺れ続ける | P 2.5 / I 20 / D OFF |
| `manual_step.csv` | 手動で出力を 40→50% に変更 | （何でもよい。例：P 10.0 / I 45 / D OFF） |

入力レンジは 0〜100 です。

## 注意

- 提案は目安です。設定を変えたあとの記録でもう一度解析して、確かめてください。
- 水の流量やバルブ開度が大きく違う運転では設備のくせが変わるので、その条件の記録で解析し直してください。
- 本ソフトウェアの利用によって生じた損害について、作者は責任を負いません。

## 開発者向け

```
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest tests -q
```

設計書は `docs/superpowers/specs/`、実装計画は `docs/superpowers/plans/` にあります。
````


- [ ] **Step 2: ショートカットを作って確かめる**

Run: `.venv/Scripts/python.exe -m tools.make_shortcut`
Expected: `...PID調整アドバイザー.lnk を作りました。`

エクスプローラーでフォルダを開いたときに、ショートカットに自作のアイコンが付いていることを画面写真で確かめる。

- [ ] **Step 3: bat を実行して確かめる**

`cmd /c ショートカット作成.bat` を実行し、日本語が文字化けせずに表示されること、エラーなく終わることを確かめる。`起動.bat` でアプリの窓が開くことを確かめる。

- [ ] **Step 4: 実際に起動して、見本 3 つで確かめる**

アプリを起動し、次を 1 つずつ確かめて画面写真を残す（写真は scratchpad に保存する）。

| 確かめること | 期待する結果 |
|---|---|
| 窓の左上・タスクバー | 自作のアイコン（青地に白い波形）が出ている。Python のアイコンではない |
| 見た目 | 画面デザインと同じ配置。文字は Meiryo UI。文字の切れ・重なりがない |
| `samples/sp_change.csv`、P 10.0 / I 45 / D OFF、レンジ 0〜100 | 修正案が P 20 前後・I 94 前後・D 8 前後。予想グラフで提案のほうが行き過ぎが小さい |
| `samples/hunting.csv`、P 2.5 / I 20 / D OFF | 場面が「温度の揺れ（ハンチング）」。時定数は「一つに絞れません」。修正案が出る |
| `samples/manual_step.csv`、P 10.0 / I 45 / D OFF | 場面が「手動で出力を変更」。修正案が出る |
| 青い帯を 0〜100 秒に狭めて解析 | 「数値の提案は出せません」と理由が出る。落ちない |
| P に `abc` と入れて解析 | 欄が赤くなり、メッセージが出る |
| ［設定…］→「複製して新規」→ 比例ゲインに変えて保存 | メイン画面の「比例帯 P」が「比例ゲイン P」に変わる |
| ［提案値をコピー］ | メモ帳などに貼り付けられる |
| 窓を閉じて開き直す | P・I・D・入力レンジの入力が残っている |

確認用に作ったプロファイルと設定ファイル（`%APPDATA%\pid-tuning-advisor`）は、確認後に残っていることをユーザーに報告する（消す場合は承認を得る）。

- [ ] **Step 5: 日本語 Windows の確認**

- `open(` を検索し、すべてに `encoding=` が付いていることを確かめる（Grep で `open\(` を探す）
- 日本語と空白を含むフォルダ（scratchpad に作る）に見本 CSV を写し、そこから開いて読めることを確かめる
- `samples/sp_change.csv` を Excel 相当の読み方（先頭 3 バイトが BOM）で確かめる（Task 9 のテストで確認済みであることを再実行で示す）

- [ ] **Step 6: 最終確認と報告**

Run: `.venv/Scripts/python.exe -m pytest tests -q`
Expected: `128 passed`

Run: `git status --short`
Expected: 作ったファイルが未追跡（`??`）で並ぶ。`.venv` と `*.lnk` は出ない。

1 ファイルが 1000 行を超えていないかを確かめる（超えていれば、分割を提案する。勝手に分割しない）。
完了・未完了・要確認を分けてユーザーに報告する。コミットはしない。
