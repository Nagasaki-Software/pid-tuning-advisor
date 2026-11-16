from dataclasses import replace

import numpy as np

from app import diagnose as dg
from app.profile import BUILTIN, Pid
from tests import synth


def test_noise_sd_estimates_scatter_and_ignores_trend():
    rng = np.random.default_rng(0)
    x = np.linspace(0.0, 50.0, 5000) + rng.normal(0.0, 0.1, 5000)
    assert abs(dg.noise_sd(x) - 0.1) < 0.02
    assert dg.noise_sd(np.array([1.0])) == 0.0


def test_excursions_of_sine_wave():
    t = np.arange(0.0, 100.0, 0.1)
    ex = dg.excursions(t, np.sin(2 * np.pi * t / 20.0), 0.05)
    assert [e.side for e in ex[:4]] == [1, -1, 1, -1]
    assert abs(ex[0].t - 5.0) < 0.2 and abs(ex[0].value - 1.0) < 0.01
    assert abs(ex[2].t - ex[0].t - 20.0) < 0.3


def test_excursions_ignores_wiggle_inside_deadband():
    t = np.arange(10.0)
    assert dg.excursions(t, np.array([0.01, -0.01] * 5), 0.05) == []


def test_detect_scene():
    assert dg.detect_scene(*synth.sp_change(), synth.SPAN) == dg.SP_CHANGE
    assert dg.detect_scene(*_reorder(synth.manual_step()), synth.SPAN) == dg.MANUAL
    assert dg.detect_scene(*_reorder(synth.hunting()), synth.SPAN) == dg.HUNTING
    t = np.arange(300.0)
    flat = np.full(300, 60.0)
    assert dg.detect_scene(t, flat, flat, np.full(300, 40.0), synth.SPAN) == dg.UNKNOWN


def _reorder(rec):
    t, sp, pv, out = rec
    return t, sp, pv, out


def test_step_metrics_on_known_response():
    t, sp, pv, out = synth.sp_change()
    m = dg.step_metrics(t, sp, pv, synth.SPAN)
    assert (m.sp0, m.sp1, m.t_step) == (60.0, 65.0, 120.0)
    assert abs(m.overshoot - 2.3) < 0.15 and abs(m.overshoot_pct - 46.0) < 3.0
    assert abs(m.period - 98.0) < 10.0
    assert abs(m.settle - 209.0) < 15.0
    assert abs(m.offset) < 0.05 and not m.multi_step


def test_step_metrics_downward_step_and_not_settled():
    t = np.arange(0.0, 200.0)
    sp = np.where(t >= 20, 50.0, 60.0)
    pv = np.where(t >= 20, 50.0 + 10.0 * np.exp(-(t - 20) / 200.0), 60.0)   # ゆっくりで区間内に届かない
    m = dg.step_metrics(t, sp, pv, 100.0)
    assert m.overshoot == 0.0 and m.settle is None and m.period is None and not m.swinging
    assert m.offset > 3.0


def test_step_metrics_flags_repeated_setpoint_changes():
    t = np.arange(0.0, 300.0)
    sp = np.where(t < 100, 60.0, np.where(t < 200, 65.0, 62.0))
    m = dg.step_metrics(t, sp, sp.copy(), 100.0)
    assert m.multi_step and (m.sp0, m.sp1) == (60.0, 62.0)
    ramp = np.clip(60.0 + (t - 50) * 0.1, 60.0, 65.0)                      # 一方向の傾斜は 1 回の変更とみなす
    assert not dg.step_metrics(t, ramp, ramp.copy(), 100.0).multi_step


def test_hunt_metrics():
    t, sp, pv, out = synth.hunting()
    m = dg.hunt_metrics(t, sp, pv, out, synth.SPAN, 0.0, 100.0)
    assert m.swinging and m.trend == "続いている"
    assert 5.0 < m.pv_pp < 9.0 and m.out_pp > 99.0
    assert 50.0 < m.period < 110.0
    assert m.saturated > 0.4


def test_manual_metrics():
    t, sp, pv, out = synth.manual_step()
    m = dg.manual_metrics(t, pv, out)
    assert m.t_jump == 60.0 and abs(m.d_out - 10.0) < 1e-9
    assert abs(m.d_pv - 4.2) < 0.15
    assert abs(m.t63 - (18.0 + 85.0)) < 10.0


def _advise(**kw):
    args = dict(profile=BUILTIN, pid=Pid(kc=10.0, ti=45.0, td=0.0), span=100.0, swinging=False, period=None,
                overshoot_pct=0.0, offset=0.0, settle=100.0, proposed_settle=100.0)
    args.update(kw)
    return dg.advise(**args)


def test_advise_follows_the_table_in_order():
    assert "微分時間を短く" in _advise(swinging=True, period=30.0, pid=Pid(10.0, 45.0, 10.0))
    assert "積分時間を長く" in _advise(swinging=True, period=98.0)
    assert "比例帯を広げる" in _advise(swinging=True, period=30.0)
    assert "比例帯を広げる" in _advise(swinging=True, period=30.0, pid=Pid(10.0, None, 0.0))
    assert "積分時間を長く" in _advise(overshoot_pct=46.0)
    assert "積分時間を短く" in _advise(offset=-0.8)
    assert "積分動作を入れる" in _advise(offset=-0.8, pid=Pid(10.0, None, 0.0))
    assert "比例帯を狭める" in _advise(settle=400.0, proposed_settle=100.0)
    assert _advise() == "大きな問題は見当たりません。"
    assert _advise(settle=None, proposed_settle=None) == "大きな問題は見当たりません。"


def test_advise_wording_for_gain_and_rpm_controllers():
    g = replace(BUILTIN, name="x", p_mode="gain", i_unit="rpm")
    assert "比例ゲインを下げる" in _advise(profile=g, swinging=True, period=30.0)
    assert "積分（回/分）を小さく" in _advise(profile=g, swinging=True, period=98.0)
    assert "比例ゲインを上げる" in _advise(profile=g, settle=400.0, proposed_settle=100.0)


def test_small_setpoint_change_with_noise_has_no_overshoot():
    rng = np.random.default_rng(5)
    t = np.arange(0.0, 600.0)
    sp = np.where(t < 60, 60.0, 60.5)
    clean = np.where(t < 60, 60.0, 60.0 + 0.5 * (1.0 - np.exp(-(t - 60.0) / 40.0)))
    pv = clean + rng.normal(0.0, 0.02, len(t))
    m = dg.step_metrics(t, sp, pv, 100.0)
    assert m.overshoot == 0.0 and m.overshoot_pct == 0.0
    assert not m.swinging and m.settle is not None
    assert _advise(overshoot_pct=m.overshoot_pct, offset=m.offset, swinging=m.swinging, period=m.period,
                   settle=m.settle, proposed_settle=m.settle) == "大きな問題は見当たりません。"


def test_scene_boundary_three_and_four_excursions():
    t = np.arange(0.0, 400.0)
    sp = np.full(400, 60.0)
    out = np.full(400, 40.0)
    pv = 60.0 + np.sin(2 * np.pi * t / 100.0)
    s3 = t < 150
    s4 = t < 200
    assert dg.detect_scene(t[s3], sp[s3], pv[s3], out[s3], synth.SPAN) == dg.UNKNOWN
    assert dg.detect_scene(t[s4], sp[s4], pv[s4], out[s4], synth.SPAN) == dg.HUNTING


def test_saturated_hunting_is_not_manual():
    from app.controller import simulate_closed
    n = int(900 / synth.SIM_DT) + 1
    sp = np.full(n, 60.0)
    y, u = simulate_closed(synth.TRUE, Pid(kc=300.0, ti=20.0, td=0.0), BUILTIN, synth.SPAN, sp, synth.SIM_DT,
                           y0=60.5, u0=40.0)
    t, sp, pv, out = synth._sample(y, u, sp, 5, 0.02, 7)
    assert dg.detect_scene(t, sp, pv, out, synth.SPAN) == dg.HUNTING


def test_advise_without_integral_does_not_mention_integral_time():
    text = _advise(pid=Pid(10.0, None, 0.0), overshoot_pct=46.0)
    assert "比例帯を広げる" in text and "積分" not in text
