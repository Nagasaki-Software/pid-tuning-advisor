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
