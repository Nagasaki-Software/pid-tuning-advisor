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
