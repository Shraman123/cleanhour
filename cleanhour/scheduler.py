"""Forecast the next 24 hours and pick the best contiguous window for a job."""
from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import dataclass


@dataclass
class Window:
    start: dt.datetime
    hours: int
    carbon: float          # mean gCO2/kWh over the window
    price: float | None    # mean Rs/kWh over the window, if known

    @property
    def end(self) -> dt.datetime:
        return self.start + dt.timedelta(hours=self.hours)


def hour_profile(history: dict[dt.datetime, float], before: dt.datetime, days: int = 7) -> dict[int, float]:
    """Median value per hour-of-day over the `days` days before `before`."""
    cutoff = before - dt.timedelta(days=days)
    buckets: dict[int, list[float]] = {h: [] for h in range(24)}
    for ts, v in history.items():
        if cutoff <= ts < before:
            buckets[ts.hour].append(v)
    if any(len(b) < max(1, days // 2) for b in buckets.values()):
        raise ValueError(f"not enough history before {before} for a {days}-day profile")
    return {h: statistics.median(b) for h, b in buckets.items()}


def forecast(history: dict[dt.datetime, float], now: dt.datetime, horizon: int = 24,
             days: int = 7) -> dict[dt.datetime, float]:
    """Seasonal-naive forecast: each future hour = median of the same hour last week."""
    prof = hour_profile(history, now, days)
    start = now.replace(minute=0, second=0, microsecond=0)
    if start < now:
        start += dt.timedelta(hours=1)
    return {start + dt.timedelta(hours=i): prof[(start + dt.timedelta(hours=i)).hour]
            for i in range(horizon)}


def _norm(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    return [0.0 if hi == lo else (v - lo) / (hi - lo) for v in vals]


def best_window(carbon: dict[dt.datetime, float], hours: int,
                price: dict[dt.datetime, float] | None = None,
                objective: str = "carbon", price_weight: float = 0.5) -> Window:
    """Contiguous `hours`-long window inside the carbon horizon minimising the objective.

    objective: "carbon" | "price" | "blend". Blend scores each hour as
    (1-w)*norm(carbon) + w*norm(price), both normalised within the horizon.
    """
    slots = sorted(carbon)
    if hours < 1 or hours > len(slots):
        raise ValueError(f"job of {hours}h does not fit a {len(slots)}h horizon")
    c = [carbon[s] for s in slots]
    p = [price.get(s) if price else None for s in slots]
    if objective != "carbon" and any(v is None for v in p):
        raise ValueError("price objective needs a price for every hour in the horizon")

    if objective == "carbon":
        score = c
    elif objective == "price":
        score = p
    elif objective == "blend":
        score = [(1 - price_weight) * a + price_weight * b for a, b in zip(_norm(c), _norm(p))]
    else:
        raise ValueError(f"unknown objective {objective!r}")

    best_i = min(range(len(slots) - hours + 1), key=lambda i: sum(score[i:i + hours]))
    win_p = p[best_i:best_i + hours]
    return Window(
        start=slots[best_i],
        hours=hours,
        carbon=sum(c[best_i:best_i + hours]) / hours,
        price=None if any(v is None for v in win_p) else sum(win_p) / hours,
    )


def window_mean(series: dict[dt.datetime, float], start: dt.datetime, hours: int) -> float:
    return sum(series[start + dt.timedelta(hours=i)] for i in range(hours)) / hours
