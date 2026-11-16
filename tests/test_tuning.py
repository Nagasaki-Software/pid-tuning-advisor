import numpy as np
import pytest

from app import diagnose as dg
from app.controller import simulate_closed
from app.process_model import Fopdt
from app.profile import BUILTIN
from app.tuning import propose
from tests import synth

MODEL = Fopdt(k=0.42, t=85.0, l=18.0, b=43.2)


def test_pid_formula_matches_hand_calculation():
    r = propose(MODEL, "normal", 100.0, 1.0, 0.2, pv_noise=0.0)
    assert r.use_d and not r.slope_based and r.l_used == 18.0
    assert r.pid.kc == pytest.approx(94.0 / (0.42 * 45.0))       # (T + L/2) ÷ (K × (2L + L/2))
    assert r.pid.ti == pytest.approx(94.0)
    assert r.pid.td == pytest.approx(85.0 * 18.0 / 188.0)


def test_preference_changes_speed():
    kc = {pref: propose(MODEL, pref, 100.0, 1.0, 0.2, 0.0).pid.kc for pref in ("stable", "normal", "fast")}
    assert kc["stable"] < kc["normal"] < kc["fast"]
    assert kc["fast"] == pytest.approx(94.0 / (0.42 * 27.0))
    assert kc["stable"] == pytest.approx(94.0 / (0.42 * 81.0))


def test_gain_scales_with_input_range():
    wide = propose(MODEL, "normal", 200.0, 1.0, 0.2, 0.0)
    assert wide.pid.kc == pytest.approx(2.0 * 94.0 / (0.42 * 45.0))


def test_noisy_pv_drops_derivative_and_uses_pi_formula():
    r = propose(MODEL, "normal", 100.0, 1.0, 0.2, pv_noise=0.2)
    assert not r.use_d and r.ripple > 2.0
    assert r.pid.td == 0.0
    assert r.pid.kc == pytest.approx(85.0 / (0.42 * 54.0))       # T ÷ (K × (2L + L))
    assert r.pid.ti == pytest.approx(85.0)                       # T と 4 × (2L + L) の小さいほう


def test_pi_integral_time_is_capped_for_slow_process():
    slow = Fopdt(k=0.42, t=2000.0, l=18.0, b=43.2)
    r = propose(slow, "normal", 100.0, 1.0, 0.2, pv_noise=5.0)
    assert r.pid.ti == pytest.approx(4.0 * 54.0)


def test_dead_time_floor_avoids_infinite_gain():
    quick = Fopdt(k=0.42, t=85.0, l=0.0, b=43.2)
    r = propose(quick, "fast", 100.0, 2.0, 0.2, 0.0)
    assert r.l_used == 2.0 and np.isfinite(r.pid.kc)
    assert propose(quick, "fast", 100.0, 0.1, 0.2, 0.0).l_used == 0.4


def test_slope_based_formula_when_time_constant_is_uncertain():
    r = propose(MODEL, "normal", 100.0, 1.0, 0.2, 0.0, t_uncertain=True)
    ks = 0.42 / 85.0
    assert r.slope_based
    assert r.pid.kc == pytest.approx(1.0 / (ks * 45.0))
    assert r.pid.ti == pytest.approx(108.0)                     # T=85 と 2×(2L+L)=108 の大きいほう（上限 216）
    assert r.pid.td == pytest.approx(9.0)
    slow = Fopdt(k=4.2, t=850.0, l=18.0, b=0.0)
    assert propose(slow, "normal", 100.0, 1.0, 0.2, 0.0, t_uncertain=True).pid.ti == pytest.approx(216.0)


def test_cooling_process_uses_magnitude_of_gain():
    cooling = Fopdt(k=-0.42, t=85.0, l=18.0, b=80.0)
    assert propose(cooling, "normal", 100.0, 1.0, 0.2, 0.0).pid.kc > 0


@pytest.mark.parametrize("pref", ["stable", "normal", "fast"])
@pytest.mark.parametrize("uncertain", [False, True])
def test_proposal_is_well_behaved_on_the_true_process(pref, uncertain):
    r = propose(synth.TRUE, pref, synth.SPAN, 1.0, 0.2, 0.0, t_uncertain=uncertain)
    dt = 0.2
    t = np.arange(0.0, 1500.0, dt)
    sp = np.where(t >= 100.0, 65.0, 60.0)
    y, u = simulate_closed(synth.TRUE, r.pid, BUILTIN, synth.SPAN, sp, dt, y0=60.0)
    m = dg.step_metrics(t, sp, y, synth.SPAN)
    assert m.overshoot_pct < 25.0
    assert m.settle is not None and not m.swinging
