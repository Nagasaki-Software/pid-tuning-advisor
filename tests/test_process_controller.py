from dataclasses import replace

import numpy as np

from app.controller import simulate_closed
from app.process_model import Fopdt, delayed, lag_filter, simulate_open
from app.profile import BUILTIN, Pid

MODEL = Fopdt(k=0.42, t=85.0, l=18.0, b=43.2)
DT = 0.2


def test_lag_filter_reaches_63_percent_at_time_constant():
    u = np.ones(2000)
    u[0] = 0.0
    x = lag_filter(u, 0.1, 20.0)
    assert x[0] == 0.0
    assert abs(x[200] - 0.632) < 0.01
    assert abs(x[-1] - 1.0) < 1e-3


def test_delayed_shifts_and_holds_first_value():
    x = np.arange(10.0)
    assert np.allclose(delayed(x, 1.0, 3.0), [0, 0, 0, 0, 1, 2, 3, 4, 5, 6])
    assert np.allclose(delayed(x, 1.0, 0.5)[1:], x[1:] - 0.5)


def test_open_loop_step_response():
    n = int(900 / DT)
    u = np.where(np.arange(n) * DT >= 60.0, 50.0, 40.0)
    y = simulate_open(MODEL, u, DT)
    assert abs(y[0] - 60.0) < 1e-9
    assert abs(y[int(77 / DT)] - 60.0) < 1e-6                 # むだ時間のあいだは動かない
    assert abs(y[int((60 + 18 + 85) / DT)] - (60.0 + 0.632 * 4.2)) < 0.05
    assert abs(y[-1] - 64.2) < 0.01


def test_open_loop_from_unsettled_start():
    y = simulate_open(MODEL, np.full(5000, 40.0), DT, y0=62.0)
    assert abs(y[0] - 62.0) < 1e-9 and abs(y[-1] - 60.0) < 0.01


def _run(pid, profile=BUILTIN, model=MODEL, sp0=60.0, sp1=65.0, seconds=900):
    n = int(seconds / DT)
    sp = np.where(np.arange(n) * DT >= 120.0, sp1, sp0)
    return sp, *simulate_closed(model, pid, profile, 100.0, sp, DT, y0=sp0)


def test_closed_loop_starts_settled_and_reaches_setpoint():
    sp, y, u = _run(Pid(kc=5.0, ti=94.0, td=8.0))
    assert np.allclose(y[: int(119 / DT)], 60.0, atol=1e-6)
    assert np.allclose(u[: int(119 / DT)], 40.0, atol=1e-6)
    assert abs(y[-1] - 65.0) < 0.05
    assert abs(u[-1] - (65.0 - 43.2) / 0.42) < 0.5


def test_output_stays_inside_limits():
    _, _, u = _run(Pid(kc=40.0, ti=20.0, td=0.0))
    assert u.min() >= 0.0 and u.max() <= 100.0 and u.max() == 100.0
    narrow = replace(BUILTIN, name="x", out_min=10.0, out_max=80.0)
    _, _, u = _run(Pid(kc=40.0, ti=20.0, td=0.0), profile=narrow)
    assert u.min() >= 10.0 and u.max() <= 80.0


def test_bump_mode_jumps_at_setpoint_change_and_bumpless_does_not():
    i = int(120 / DT)
    _, _, u = _run(Pid(kc=5.0, ti=94.0, td=0.0))
    assert abs((u[i] - u[i - 1]) - 5.0 * 5.0) < 0.5           # ゲイン 5 × 偏差 5%
    smooth = replace(BUILTIN, name="x", sp_response="bumpless")
    _, y, u = _run(Pid(kc=5.0, ti=94.0, td=0.0), profile=smooth)
    assert abs(u[i] - u[i - 1]) < 0.5
    assert abs(y[-1] - 65.0) < 0.1


def test_derivative_on_error_kicks_at_setpoint_change():
    i = int(120 / DT)
    on_error = replace(BUILTIN, name="x", d_on="error")
    _, _, u_pv = _run(Pid(kc=2.0, ti=94.0, td=2.0))
    _, _, u_err = _run(Pid(kc=2.0, ti=94.0, td=2.0), profile=on_error)
    assert u_err[i] > u_pv[i] + 20.0


def test_direct_action_with_cooling_process():
    cooling = Fopdt(k=-0.3, t=60.0, l=10.0, b=40.0)          # 出力を上げると下がる設備
    direct = replace(BUILTIN, name="x", reverse=False)
    _, y, u = _run(Pid(kc=3.0, ti=60.0, td=0.0), profile=direct, model=cooling, sp0=25.0, sp1=22.0)
    assert abs(y[-1] - 22.0) < 0.05 and u[-1] > u[0]


def test_p_only_leaves_offset():
    _, y, _ = _run(Pid(kc=5.0, ti=None, td=0.0))
    assert 0.5 < 65.0 - y[-1] < 3.0
