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
