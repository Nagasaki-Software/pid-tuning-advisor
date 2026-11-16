"""部品をつないで、1 回の解析結果をまとめる。画面はこの結果を表示するだけ。"""
from __future__ import annotations

import math
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

    if ident.dt_used > dt_record * 1.5:
        warnings.append("区間が長いため、遅れの推定が粗くなっています。設定値を変えた前後だけを選ぶと精度が上がります。")
    result = AnalysisResult(scene, rows, ident, model_rows, current_text, warnings=warnings)
    proposed_settle = None
    if ident.ok:
        proposal = propose(ident.model, inp.pref, span, max(dt_record, ident.dt_used), p.period_ms / 1000.0,
                           diagnose.noise_sd(pv), ident.t_uncertain)
        values = prof.from_pid(p, proposal.pid)
        new = prof.to_pid(p, values[0], values[1], values[2])
        result.proposal = proposal
        result.proposed_values = values[:3]
        result.proposed_text = (prof.format_p(p, values[0]), prof.format_i(p, values[1]), prof.format_d(p, values[2]))

        if step is not None and step.sp1 != step.sp0:
            sp0, sp1 = step.sp0, step.sp1
        else:
            digits = max(0, 3 - math.ceil(math.log10(span)))
            sp0 = round(float(np.mean(pv)), digits)
            sp1 = sp0 + 0.05 * span if sp0 + 0.05 * span <= inp.range_hi else sp0 - 0.05 * span
            sp1 = round(sp1, digits)
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
