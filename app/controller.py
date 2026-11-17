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

    計算式（一般的な調節計の PID の形）:
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
