"""Build the local dataset: 15-min grid mix -> hourly intensity, joined with IEX prices."""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from . import grid, iex
from .carbon import FUELS, clean_share, intensity_g_per_kwh

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"


def collect_grid(days: int, end: dt.date | None = None, log=print) -> list[dict]:
    """15-min rows for the last `days` days that Grid-India has published."""
    end = end or dt.date.today()
    start = end - dt.timedelta(days=days + 3)  # slack: the newest day may not be out yet
    listing: dict[dt.date, str] = {}
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        listing.update(grid.list_daily_xls(y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    chosen = [d for d in sorted(listing) if start <= d <= end][-days:]

    rows = []
    for d in chosen:
        path = grid.download(listing[d], RAW / f"psp_{d.isoformat()}.xls")
        rows.extend(grid.parse_timeseries(path, d))
        log(f"  grid {d}  ok")
    return rows


def collect_prices(first: dt.date, last: dt.date) -> list[dict]:
    out, d = [], first
    while d <= last:  # small chunks keep the IEX response well under any limit
        chunk_end = min(d + dt.timedelta(days=6), last)
        out.extend(iex.fetch_dam(d, chunk_end))
        d = chunk_end + dt.timedelta(days=1)
    return out


def to_hourly(rows: list[dict]) -> list[dict]:
    """Average the four 15-min blocks in each hour, then compute intensity."""
    by_hour: dict[str, list[dict]] = {}
    for r in rows:
        by_hour.setdefault(r["ts"][:13], []).append(r)
    out = []
    for key in sorted(by_hour):
        blocks = by_hour[key]
        mix = {f: sum(b[f] for b in blocks) / len(blocks) for f in FUELS + ["demand"]}
        out.append({
            "ts": key + ":00",
            "intensity": round(intensity_g_per_kwh(mix), 1),
            "clean_share": round(clean_share(mix), 4),
            **{f: round(mix[f]) for f in FUELS + ["demand"]},
        })
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open() as f:
        return [{k: (v if k == "ts" else (float(v) if v != "" else None)) for k, v in r.items()}
                for r in csv.DictReader(f)]


def build(days: int = 30, log=print) -> list[dict]:
    log(f"Fetching {days} days of Grid-India PSP data...")
    q = collect_grid(days, log=log)
    write_csv(DATA / "grid_15min.csv", q)
    hourly = to_hourly(q)

    first = dt.date.fromisoformat(hourly[0]["ts"][:10])
    # Include tomorrow: the DAM has usually cleared it by early afternoon.
    last = dt.date.today() + dt.timedelta(days=1)
    log(f"Fetching IEX DAM prices {first} -> {last}...")
    prices = {p["ts"]: p["price_rs_per_kwh"] for p in collect_prices(first, last)}
    for h in hourly:
        h["price"] = prices.get(h["ts"])
    write_csv(DATA / "hourly.csv", hourly)
    write_csv(DATA / "prices.csv", [{"ts": k, "price": v} for k, v in sorted(prices.items())])
    log(f"Wrote {len(q)} 15-min rows, {len(hourly)} hourly rows, {len(prices)} price hours.")
    return hourly


def load_series() -> tuple[dict[dt.datetime, float], dict[dt.datetime, float]]:
    """(hourly carbon intensity, hourly price incl. future DAM hours)."""
    carbon = {dt.datetime.fromisoformat(r["ts"]): r["intensity"] for r in read_csv(DATA / "hourly.csv")}
    price = {dt.datetime.fromisoformat(r["ts"]): r["price"] for r in read_csv(DATA / "prices.csv")}
    return carbon, price
