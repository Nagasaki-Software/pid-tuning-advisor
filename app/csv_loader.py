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
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        raise ValueError("ファイルを開けません。Excel などで開いている場合は閉じてから、もう一度選んでください。") from e
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
    base = rows[start - 1] if start >= 1 else None
    if base is not None and len(base) == ncol and not _is_data_row(base):
        names = list(base)
        upper = rows[start - 2] if start >= 2 else None
        if upper is not None and len(upper) == ncol and not _is_data_row(upper) \
                and sum(1 for c in upper if c) >= ncol - 1:
            names = [(a + " " + b).strip() for a, b in zip(upper, base)]
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
    """最初の値に合う読み方を選ぶ。(読み方, 時刻だけの形式か) を返す。合うものが無ければ None。"""
    if _is_number(sample):
        return float, False
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(sample, fmt)
            return (lambda s, f=fmt: (datetime.strptime(s, f) - _EPOCH).total_seconds()), False
        except ValueError:
            pass
    for fmt in _TIME_FORMATS:
        try:
            datetime.strptime(sample, fmt)

            def clock(s, f=fmt):
                d = datetime.strptime(s, f)
                return d.hour * 3600.0 + d.minute * 60.0 + d.second + d.microsecond / 1e6
            return clock, True
        except ValueError:
            pass
    return None


def build_series(table: RawTable, time_col: int | None, sp_col: int, out_col: int, pv_col: int,
                 dt_manual: float | None = None) -> Series:
    """選んだ列を数値にして、等間隔の記録にする。time_col が None のときは dt_manual 秒間隔とみなす。"""
    notes: list[str] = []
    parser, clock_only = None, False
    if time_col is not None:
        found = _time_parser(table.rows[0][time_col]) if table.rows else None
        if found is None:
            raise ValueError("時刻の列を読めません。日時（例 2026/11/14 10:00:00）か、秒の数値の列を選んでください。")
        parser, clock_only = found
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
        if clock_only:
            back = np.diff(t) < -43200.0                 # 時刻だけの列で日付をまたいだ
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
