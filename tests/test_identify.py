import numpy as np
import pytest

from app.identify import identify
from tests import synth

TRUE = synth.TRUE


def _close(value, target, tol=0.15):
    return abs(value - target) <= tol * abs(target)


@pytest.mark.parametrize("maker", [synth.sp_change, synth.manual_step])
def test_recovers_known_process(maker):
    t, sp, pv, out = maker()
    r = identify(t, out, pv, synth.SPAN, True)
    assert r.ok and r.reasons == [] and not r.t_uncertain
    assert _close(r.model.k, TRUE.k) and _close(r.model.t, TRUE.t) and _close(r.model.l, TRUE.l)
    assert _close(r.model.b, TRUE.b)
    assert r.fit > 90.0


def test_hunting_gives_speed_and_dead_time_but_not_time_constant():
    t, sp, pv, out = synth.hunting()
    r = identify(t, out, pv, synth.SPAN, True)
    assert r.ok and r.t_uncertain
    assert _close(r.model.k / r.model.t, TRUE.k / TRUE.t) and _close(r.model.l, TRUE.l)


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_robust_to_larger_noise(seed):
    t, sp, pv, out = synth.sp_change(noise=0.05, seed=seed)
    r = identify(t, out, pv, synth.SPAN, True)
    assert r.ok and _close(r.model.k, TRUE.k) and _close(r.model.t, TRUE.t) and _close(r.model.l, TRUE.l)


def test_long_record_is_thinned_and_still_recovered():
    t, sp, pv, out = synth.sp_change()
    tf = np.arange(0.0, t[-1], 0.1)                          # 0.1 秒間隔 = 約 9000 点
    r = identify(tf, np.interp(tf, t, out), np.interp(tf, t, pv), synth.SPAN, True)
    assert r.ok and _close(r.model.k, TRUE.k) and _close(r.model.t, TRUE.t) and _close(r.model.l, TRUE.l)


def test_time_offset_does_not_matter():
    t, sp, pv, out = synth.manual_step()
    r = identify(t + 5000.0, out, pv, synth.SPAN, True)
    assert r.ok and _close(r.model.t, TRUE.t)


def test_flat_output_is_refused():
    t, sp, pv, out = synth.sp_change()
    r = identify(t, np.full(len(t), 40.0), pv, synth.SPAN, True)
    assert not r.ok and r.model is None and "出力の変化幅" in r.reasons[0]


def test_flat_pv_is_refused():
    t, sp, pv, out = synth.sp_change()
    r = identify(t, out, np.full(len(t), 60.0), synth.SPAN, True)
    assert not r.ok and "測定値の変化幅" in r.reasons[0]


def test_too_few_points_is_refused():
    t, sp, pv, out = synth.sp_change()
    r = identify(t[:20], out[:20], pv[:20], synth.SPAN, True)
    assert not r.ok and "30 点未満" in r.reasons[0]


def test_wrong_action_direction_is_reported():
    t, sp, pv, out = synth.manual_step()
    r = identify(t, out, pv, synth.SPAN, False)
    assert not r.ok and any("動作の向き" in s for s in r.reasons)


def test_interval_too_short_for_slow_process_is_reported():
    t, sp, pv, out = synth.manual_step()
    sel = (t >= 55) & (t <= 100)                             # 動き出した直後だけ
    r = identify(t[sel], out[sel], pv[sel], synth.SPAN, True)
    assert not r.ok


def test_unrelated_signals_fit_poorly():
    rng = np.random.default_rng(5)
    t = np.arange(600.0)
    out = 50.0 + 10.0 * np.sign(np.sin(t / 30.0))
    pv = 60.0 + rng.normal(0.0, 1.0, len(t))
    r = identify(t, out, pv, synth.SPAN, True)
    assert not r.ok


def test_too_fast_process_is_refused():
    rng = np.random.default_rng(6)
    t = np.arange(600.0)
    out = np.where((t // 100) % 2 == 0, 40.0, 50.0)          # 100 秒ごとに 40 と 50 を行き来
    pv = 43.2 + 0.42 * out + rng.normal(0.0, 0.02, len(t))   # 遅れなしで出力に比例
    r = identify(t, out, pv, synth.SPAN, True)
    assert not r.ok and any("速すぎて" in s for s in r.reasons)
