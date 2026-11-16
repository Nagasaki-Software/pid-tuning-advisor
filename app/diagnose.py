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
    if len(steps) and float(np.mean(steps < 0.05)) >= 0.9 and float(steps.max()) >= 1.0 and int((steps >= 1.0).sum()) <= 4:
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

    db = _deadband(pv, span)
    tt, dev = t[i_last:], (pv[i_last:] - sp1) * sgn
    overshoot = max(float(dev.max()), 0.0) if len(dev) else 0.0
    if overshoot <= 2.0 * db:                                   # ノイズに埋もれた行き過ぎは数えない
        overshoot = 0.0
    overshoot_pct = 100.0 * overshoot / abs(step) if step != 0 else 0.0
    ups = [e for e in excursions(tt, dev, db) if e.side > 0]
    ups = [e for e in ups if e.value >= 0.1 * ups[0].value]     # 最初の山の 1 割に満たない山は数えない
    period = ups[1].t - ups[0].t if len(ups) >= 2 else None
    decay = ups[1].value / ups[0].value if len(ups) >= 2 else None
    swinging = decay is not None and decay > SWING_DECAY

    band = max(SETTLE_BAND * abs(step), 2.0 * db)
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
    if overshoot_pct > BIG_OVERSHOOT and pid.ti is None:
        return f"揺れはありませんが、行き過ぎが大きめです。{p_weaker}方向です。"
    if overshoot_pct > BIG_OVERSHOOT:
        return f"揺れはありませんが、行き過ぎが大きめです。{i_weaker}方向です。"
    if abs(offset) >= span * OFFSET_PCT / 100.0:
        if pid.ti is None:
            return "設定値からずれたまま戻っていません。積分動作を入れる方向です。"
        return f"設定値からずれたまま戻っていません。{i_stronger}方向です。"
    if settle is not None and proposed_settle is not None and proposed_settle > 0 and settle >= 2.0 * proposed_settle:
        return f"行き過ぎは小さいですが、落ち着くまでに時間がかかっています。{p_stronger}、または{i_stronger}方向です。"
    return "大きな問題は見当たりません。"
