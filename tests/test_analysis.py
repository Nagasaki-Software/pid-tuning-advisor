from dataclasses import replace

import numpy as np
import pytest

from app import diagnose as dg
from app.analysis import AnalysisInput, run_analysis
from app.profile import BUILTIN
from tests import synth


def _inp(rec, **kw):
    t, sp, pv, out = rec
    args = dict(t=t, sp=sp, pv=pv, out=out, profile=BUILTIN, p=10.0, i=45.0, d=None, range_lo=0.0, range_hi=100.0)
    args.update(kw)
    return AnalysisInput(**args)


def test_setpoint_change_gives_full_result():
    r = run_analysis(_inp(synth.sp_change()))
    assert r.scene == dg.SP_CHANGE
    assert r.current_text == ("10.0 %", "45 秒", "OFF")
    p, i, d = r.proposed_values
    assert 17.0 <= p <= 24.0 and 80.0 <= i <= 108.0 and 6.0 <= d <= 10.0      # 正解の設備なら 20.1 / 94 / 8
    assert r.proposed_text == (f"{p:.1f} %", f"{i:.0f} 秒", f"{d:.0f} 秒")
    assert [label for label, _ in r.diag_rows] == ["場面", "設定値", "行き過ぎ", "揺れの周期", "落ち着くまで"]
    assert dict(r.diag_rows)["設定値"] == "60 → 65"
    assert [label for label, _ in r.model_rows][1:] == ["反応の遅れ（時定数）", "動き出すまで（むだ時間）", "当てはまり具合"]
    assert "積分時間を長く" in r.direction
    assert r.reproduce_fit > 80.0 and r.warnings == []


def test_prediction_shows_improvement():
    r = run_analysis(_inp(synth.sp_change()))
    pr = r.prediction
    assert len(pr.t) == len(pr.sp) == len(pr.y_cur) == len(pr.y_new)
    assert (pr.sp[0], pr.sp[-1]) == (60.0, 65.0)
    assert abs(pr.cur.overshoot - 2.3) < 0.4
    assert pr.new.overshoot < 0.5 * pr.cur.overshoot
    assert pr.new.settle < pr.cur.settle


def test_preference_changes_proposal():
    p = {pref: run_analysis(_inp(synth.sp_change(), pref=pref)).proposed_values[0] for pref in ("stable", "normal", "fast")}
    assert p["stable"] > p["normal"] > p["fast"]                 # 安定重視ほど比例帯が広い


def test_manual_step_record():
    r = run_analysis(_inp(synth.manual_step()))
    assert r.scene == dg.MANUAL and r.proposed_values is not None
    assert 17.0 <= r.proposed_values[0] <= 24.0
    assert r.reproduce_fit is None and r.direction == ""
    assert r.prediction.sp[-1] == pytest.approx(r.prediction.sp[0] + 5.0)


def test_hunting_record_uses_slope_based_proposal():
    r = run_analysis(_inp(synth.hunting(), p=2.5, i=20.0))
    assert r.scene == dg.HUNTING and r.proposal.slope_based
    assert r.proposed_values[0] > 10.0                           # 比例帯を大きく広げる
    assert "時定数を一つに絞れなかった" in r.reason
    assert dict(r.model_rows)["反応の遅れ（時定数）"] == "一つに絞れません"
    assert not r.prediction.new.swinging


def test_no_numeric_proposal_when_output_did_not_move():
    t = np.arange(0.0, 600.0)
    rng = np.random.default_rng(0)
    rec = (t, np.full(600, 60.0), 60.0 + rng.normal(0, 0.02, 600), np.full(600, 40.0))
    r = run_analysis(_inp(rec))
    assert r.proposed_values is None and r.proposed_text is None and r.prediction is None
    assert r.reason.startswith("数値の提案は出せません。") and "出力の変化幅" in r.reason
    assert r.scene == dg.UNKNOWN and any("場面を自動で判定できません" in w for w in r.warnings)


def test_scene_can_be_forced():
    r = run_analysis(_inp(synth.sp_change(), scene=dg.HUNTING))
    assert r.scene == dg.HUNTING and r.diag_rows[1][0] == "揺れの幅"


def test_aux_function_flag_adds_warning():
    r = run_analysis(_inp(synth.sp_change(), aux_in_use=True))
    assert any("補助機能" in w for w in r.warnings)


def test_wrong_pid_entry_lowers_reproduction_and_warns():
    r = run_analysis(_inp(synth.sp_change(), p=100.0, i=600.0))
    assert r.reproduce_fit < 50.0 and any("記録と合いません" in w for w in r.warnings)


def test_gain_type_controller_profile():
    g = replace(BUILTIN, name="x", p_mode="gain", p_min=0.01, p_max=100.0, p_step=0.01,
                i_unit="min", i_min=0.01, i_max=100.0, i_step=0.01, d_unit="min", d_min=0.01, d_max=100.0, d_step=0.01)
    r = run_analysis(_inp(synth.sp_change(), profile=g, p=10.0, i=0.75, d=None))
    p, i, d = r.proposed_values
    assert 4.1 <= p <= 5.9 and 1.3 <= i <= 1.8 and 0.10 <= d <= 0.17
    assert r.current_text == ("10.00", "0.75 分", "OFF")


def test_narrow_range_changes_proportional_band_not_behavior():
    r = run_analysis(_inp(synth.sp_change(), p=20.0, range_lo=40.0, range_hi=90.0))   # 幅 50：同じ動きの比例帯は 2 倍
    assert 34.0 <= r.proposed_values[0] <= 48.0
    assert r.reproduce_fit > 80.0


def test_time_not_starting_at_zero():
    t, sp, pv, out = synth.sp_change()
    r = run_analysis(_inp((t + 3600.0, sp, pv, out)))
    assert r.proposed_values is not None and dict(r.diag_rows)["落ち着くまで"].endswith("秒")


def test_coarse_resolution_record():
    t, sp, pv, out = synth.sp_change()
    r = run_analysis(_inp((t, sp, np.round(pv, 1), np.round(out, 1))))      # 記録計の表示桁（0.1 刻み）
    assert 17.0 <= r.proposed_values[0] <= 24.0
    assert abs(float(dict(r.diag_rows)["行き過ぎ"].split("（")[0]) - 2.3) < 0.2


def test_slow_sampling_record():
    t, sp, pv, out = synth.sp_change()
    r = run_analysis(_inp((t[::5], sp[::5], pv[::5], out[::5])))            # 5 秒間隔の記録
    assert r.proposed_values is not None and 15.0 <= r.proposed_values[0] <= 27.0


def test_bad_range_is_rejected():
    with pytest.raises(ValueError):
        run_analysis(_inp(synth.sp_change(), range_lo=100.0, range_hi=0.0))


def _long_record(n=86400, noise=0.02, seed=5):
    """1 日分（1 秒間隔）。途中で設定値を 1 回変える。"""
    from app.controller import simulate_closed
    from app.profile import Pid
    t = np.arange(n, dtype=float)
    sp = np.where(t >= n // 2, 65.0, 60.0)
    y, u = simulate_closed(synth.TRUE, Pid(kc=10.0, ti=45.0, td=0.0), BUILTIN, synth.SPAN, sp, 1.0, y0=60.0)
    rng = np.random.default_rng(seed)
    return t, sp, y + rng.normal(0.0, noise, n), u


def test_long_record_does_not_underestimate_dead_time():
    r = run_analysis(_inp(_long_record()))
    assert r.ident.dt_used > 1.5
    assert any("区間が長いため" in w for w in r.warnings)
    assert r.proposal is not None and r.proposed_values[0] >= 15.0       # 正しい提案は約 19.7%


def test_prediction_setpoint_is_rounded_to_range_digits():
    r = run_analysis(_inp(synth.hunting(), i=20.0, p=40.0))
    assert r.prediction is not None
    x = float(r.prediction.sp[0])
    assert round(x, 1) == x and round(float(r.prediction.sp[-1]), 1) == float(r.prediction.sp[-1])
