"""Hourly Day-Ahead Market clearing prices from the Indian Energy Exchange.

The DAM for day D clears around 13:00 IST on D-1, so tomorrow's hourly prices
are known in advance. That makes price a real forecast, not a guess.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.request

URL = ("https://www.iexindia.com/api/v1/dam/market-snapshot"
       "?interval=ONE_HOUR&dp=SELECT_RANGE&fromDate={d}&toDate={d2}")


def fetch_dam(start: dt.date, end: dt.date) -> list[dict]:
    """Rows of {ts, price_rs_per_kwh} for each hour in [start, end]."""
    url = URL.format(d=start.strftime("%d-%m-%Y"), d2=end.strftime("%d-%m-%Y"))
    req = urllib.request.Request(url, headers={"User-Agent": "cleanhour/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    out = []
    for row in body.get("data", []):
        day = dt.datetime.strptime(row["date"], "%d-%m-%Y").date()
        hour = int(row["hour"]) - 1  # IEX hour 1 = 00:00-01:00
        mcp = float(row["mcp"])      # Rs/MWh
        out.append({"ts": dt.datetime.combine(day, dt.time(hour)).isoformat(timespec="minutes"),
                    "price_rs_per_kwh": round(mcp / 1000.0, 4)})
    return out
