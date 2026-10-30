import datetime as dt
from pathlib import Path

import pytest

from cleanhour import carbon, grid
from cleanhour.dataset import to_hourly
from cleanhour.scheduler import best_window, forecast

FIXTURE = Path(__file__).parent / "fixtures" / "psp_2026-10-29.xls"


def test_parse_real_psp_report():
    rows = grid.parse_timeseries(FIXTURE, dt.date(2026, 10, 29))
    assert len(rows) == 96
    assert rows[0]["ts"] == "2026-10-29T00:00"
    assert rows[-1]["ts"] == "2026-10-29T23:45"
    # Values copied by hand from the sheet's 00:00 and 12:00 rows.
    assert rows[0]["thermal"] == 148788 and rows[0]["solar"] == 0
    noon = next(r for r in rows if r["ts"].endswith("12:00"))
    assert noon["solar"] == 82473 and noon["storage"] == 33
    assert noon["demand"] == 220822  # DEMAND MET, not NET DEMAND MET


def test_hourly_noon_cleaner_than_night():
    hourly = {h["ts"][11:13]: h for h in to_hourly(grid.parse_timeseries(FIXTURE, dt.date(2026, 10, 29)))}
    assert len(hourly) == 24
    assert hourly["12"]["intensity"] < 0.75 * hourly["21"]["intensity"]


def test_intensity_bounds():
    assert carbon.intensity_g_per_kwh({"solar": 10}) == 0
    assert carbon.intensity_g_per_kwh({"thermal": 10}) == pytest.approx(960)
    assert carbon.intensity_g_per_kwh({"thermal": 1, "solar": 1}) == pytest.approx(480)
    with pytest.raises(ValueError):
        carbon.intensity_g_per_kwh({})


def _series(start, values):
    return {start + dt.timedelta(hours=i): v for i, v in enumerate(values)}


def test_best_window_finds_contiguous_minimum():
    t0 = dt.datetime(2026, 1, 1)
    s = _series(t0, [9, 9, 1, 9, 2, 2, 9, 9])
    # lone 1 loses to the 2+2 pair for a 2h job
    w = best_window(s, 2)
    assert w.start == t0 + dt.timedelta(hours=4) and w.carbon == 2
    assert best_window(s, 1).start == t0 + dt.timedelta(hours=2)


def test_price_and_blend_objectives():
    t0 = dt.datetime(2026, 1, 1)
    c = _series(t0, [1, 5, 5, 5])
    p = _series(t0, [9, 9, 1, 9])
    assert best_window(c, 1, p, "carbon").start == t0
    assert best_window(c, 1, p, "price").start == t0 + dt.timedelta(hours=2)
    with pytest.raises(ValueError):
        best_window(c, 5)


def test_forecast_uses_only_the_past():
    t0 = dt.datetime(2026, 1, 1)
    hist = {t0 + dt.timedelta(hours=i): float((i % 24 == 12) * -100 + 500) for i in range(24 * 7)}
    now = t0 + dt.timedelta(days=7, hours=3, minutes=20)
    fc = forecast(hist, now)
    assert min(fc) == now.replace(minute=0) + dt.timedelta(hours=1)
    assert len(fc) == 24
    noon = next(t for t in fc if t.hour == 12)
    assert fc[noon] == 400 and best_window(fc, 1).start == noon
    with pytest.raises(ValueError):
        forecast(hist, t0 + dt.timedelta(days=2))  # not enough history
