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
    dt_used: float = 0.0            # 推定に使った（間引いたあとの）間隔 秒


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
    if best_tau <= 2.0 * dt * 1.02:
        reasons.append("反応が記録の間隔に比べて速すぎて、遅れを推定できません。もっと短い間隔の記録を使ってください。")
    return IdentResult(model, fit, not reasons, reasons, t_uncertain, dt)
