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
        w.writerow(["日時", "設定値", "出力", "温度"])
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
