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
    if s == "" or s.upper() in ("OFF", "ＯＦＦ"):
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


def profile_file_name(name: str) -> str:
    """プロファイルの名前から、保存に使うファイル名を作る。"""
    return _file_name(name)


def save_profile(profile: ControllerProfile, base: Path | None = None) -> Path:
    if profile.name.strip() == "":
        raise ValueError("プロファイルの名前を入力してください。")
    if profile.name == BUILTIN.name:
        raise ValueError("同梱のプロファイルは上書きできません。「複製して新規」で別の名前を付けてください。")
    folder = data_dir(base) / "profiles"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _file_name(profile.name)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except (OSError, ValueError):
            existing = None
        if isinstance(existing, dict) and existing.get("name") != profile.name:
            raise ValueError(f"「{existing.get('name')}」と同じファイル名になるため保存できません。別の名前を付けてください。")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, ensure_ascii=False, indent=2)
    return path


def _check_profile(p: ControllerProfile) -> None:
    """読み込んだ値が画面や計算で使える範囲かを確かめる。外れていたら ValueError。"""
    ok = (
        p.name.strip() != ""
        and p.p_mode in ("pb", "gain")
        and p.i_unit in I_UNIT_LABELS
        and p.d_unit in D_UNIT_LABELS
        and p.sp_response in ("bump", "bumpless")
        and p.d_on in ("pv", "error")
        and 0 < p.p_min < p.p_max and p.p_step > 0
        and 0 < p.i_min < p.i_max and p.i_step > 0
        and 0 < p.d_min < p.d_max and p.d_step > 0
        and p.period_ms > 0
        and p.out_min < p.out_max
    )
    if not ok:
        raise ValueError(f"プロファイルの値が正しくありません: {p.name!r}")


def _from_dict(d: dict) -> ControllerProfile:
    if not isinstance(d, dict):
        raise ValueError("プロファイルの形式が正しくありません。")
    known = {f.name: f for f in fields(ControllerProfile)}
    kwargs = {}
    for key, value in d.items():
        if key not in known:
            continue
        default = getattr(BUILTIN, key)
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError(f"{key} は true か false で書いてください。")
            kwargs[key] = value
        elif isinstance(default, float):
            kwargs[key] = float(value)
        else:
            kwargs[key] = str(value)
    prof = ControllerProfile(**kwargs)
    _check_profile(prof)
    return prof


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
