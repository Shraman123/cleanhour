"""Backtest the scheduler and export everything the dashboard needs."""
from __future__ import annotations

import datetime as dt
import json
import statistics
from pathlib import Path

from .carbon import EMISSION_FACTORS
from .dataset import DATA, ROOT, read_csv
from .scheduler import best_window, forecast, window_mean

SITE_DATA = ROOT / "site" / "data.json"


def backtest(carbon: dict, price: dict, hours: int = 2, profile_days: int = 7) -> dict:
    """Submit a job at every hour; scheduler sees only a forecast built from the past.

    Compares the actual carbon of the window it picked with (a) starting
    immediately and (b) the hindsight-optimal window in the same 24h horizon.
    """
    slots = sorted(carbon)
    first_ok = slots[0] + dt.timedelta(days=profile_days)
    results = []
    for now in slots:
        if now < first_ok or now + dt.timedelta(hours=24) > slots[-1] + dt.timedelta(hours=1):
            continue
        horizon = [now + dt.timedelta(hours=i) for i in range(24)]
        actual = {t: carbon[t] for t in horizon}
        picked = best_window(forecast(carbon, now, 24, profile_days), hours)
        oracle = best_window(actual, hours)
        results.append({
            "now": window_mean(carbon, now, hours),
            "picked": window_mean(carbon, picked.start, hours),
            "oracle": oracle.carbon,
            "now_price": window_mean(price, now, hours),
            "picked_price": best_window(actual, hours, {t: price[t] for t in horizon}, "price").price,
        })
    n = len(results)
    mean = lambda k: statistics.mean(r[k] for r in results)
    return {
        "job_hours": hours,
        "submissions": n,
        "carbon_run_now": round(mean("now"), 1),
        "carbon_scheduled": round(mean("picked"), 1),
        "carbon_oracle": round(mean("oracle"), 1),
        "carbon_saving_pct": round(100 * (1 - mean("picked") / mean("now")), 1),
        "oracle_saving_pct": round(100 * (1 - mean("oracle") / mean("now")), 1),
        "price_run_now": round(mean("now_price"), 2),
        "price_scheduled": round(mean("picked_price"), 2),
        "price_saving_pct": round(100 * (1 - mean("picked_price") / mean("now_price")), 1),
    }


def hour_of_day(rows: list[dict]) -> list[dict]:
    out = []
    for h in range(24):
        r = [x for x in rows if int(x["ts"][11:13]) == h]
        vals = sorted(x["intensity"] for x in r)
        prices = [x["price"] for x in r if x["price"] is not None]
        out.append({
            "hour": h,
            "intensity_mean": round(statistics.mean(vals), 1),
            "intensity_p10": round(vals[int(0.1 * (len(vals) - 1))], 1),
            "intensity_p90": round(vals[int(0.9 * (len(vals) - 1))], 1),
            "clean_share": round(statistics.mean(x["clean_share"] for x in r), 4),
            "solar_gw": round(statistics.mean(x["solar"] for x in r) / 1000, 1),
            "thermal_gw": round(statistics.mean(x["thermal"] for x in r) / 1000, 1),
            "price_mean": round(statistics.mean(prices), 2) if prices else None,
        })
    return out


def export_site(experiment: dict | None = None) -> dict:
    rows = read_csv(DATA / "hourly.csv")
    carbon = {dt.datetime.fromisoformat(r["ts"]): r["intensity"] for r in rows}
    price = {dt.datetime.fromisoformat(r["ts"]): r["price"]
             for r in read_csv(DATA / "prices.csv")}
    last = max(carbon)
    nxt = last + dt.timedelta(hours=1)
    fc = forecast(carbon, nxt, 24)
    plan = best_window(fc, 2)
    worst = max((plan_start for plan_start in sorted(fc)[:-1]),
                key=lambda s: fc[s] + fc[s + dt.timedelta(hours=1)])
    exp_path = DATA / "experiment.json"
    if experiment is None and exp_path.exists():
        experiment = json.loads(exp_path.read_text())

    vals = [r["intensity"] for r in rows]
    payload = {
        "generated": dt.datetime.now().isoformat(timespec="minutes"),
        "range": [rows[0]["ts"], rows[-1]["ts"]],
        "factors": EMISSION_FACTORS,
        "summary": {
            "mean": round(statistics.mean(vals), 1),
            "min": min(vals), "max": max(vals),
            "cleanest": next(r["ts"] for r in rows if r["intensity"] == min(vals)),
            "dirtiest": next(r["ts"] for r in rows if r["intensity"] == max(vals)),
        },
        "hourly": [{k: r[k] for k in ("ts", "intensity", "clean_share", "solar", "wind",
                                      "hydro", "nuclear", "thermal", "gas", "price")}
                   for r in rows],
        "hour_of_day": hour_of_day(rows),
        "backtest": [backtest(carbon, price, h) for h in (1, 2, 4)],
        "forecast": {
            "from": nxt.isoformat(timespec="minutes"),
            "series": [{"ts": t.isoformat(timespec="minutes"), "intensity": round(v, 1),
                        "price": price.get(t)} for t, v in sorted(fc.items())],
            "best_2h": {"start": plan.start.isoformat(timespec="minutes"), "carbon": round(plan.carbon, 1)},
            "worst_2h": {"start": worst.isoformat(timespec="minutes"),
                         "carbon": round((fc[worst] + fc[worst + dt.timedelta(hours=1)]) / 2, 1)},
        },
        "experiment": experiment,
    }
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(payload, separators=(",", ":")))
    return payload
