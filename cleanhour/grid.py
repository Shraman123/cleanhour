"""Download and parse Grid-India (NLDC) daily Power Supply Position reports.

Each daily PSP .xls has a "TimeSeries" sheet with all-India generation by fuel
in 15-minute blocks. Files are listed through the same JSON API the
grid-india.in reports page uses.
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.request
from pathlib import Path

import xlrd

API = "https://webapi.grid-india.in/api/v1/file"
CDN = "https://webcdn.grid-india.in/"
UA = {"User-Agent": "cleanhour/0.1 (+https://github.com/Shraman123/cleanhour)",
      "Content-Type": "application/json"}

# TimeSeries sheet column -> our field name (by header text, so column moves don't break us).
HEADER_MAP = {
    "DEMAND MET": "demand",
    "NUCLEAR": "nuclear",
    "WIND": "wind",
    "SOLAR": "solar",
    "HYDRO": "hydro",
    "GAS": "gas",
    "THERMAL": "thermal",
    "STORAGE (PSP": "storage",
    "OTHERS": "others",
}


def _post(payload: dict) -> dict:
    req = urllib.request.Request(API, data=json.dumps(payload).encode(), headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fiscal_year(d: dt.date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def list_daily_xls(year: int, month: int) -> dict[dt.date, str]:
    """Map of data-date -> CDN path for that month's daily PSP .xls files.

    A report titled "29.10.26_NLDC_PSP" holds data for 29 Oct 2026 (published
    the next morning). When a day was re-issued, the newest upload wins.
    """
    first = dt.date(year, month, 1)
    res = _post({"_source": "GRDW", "_type": "daily_psp_report",
                 "_fileDate": fiscal_year(first), "_month": f"{month:02d}"})
    out: dict[dt.date, tuple[int, str]] = {}
    for f in res.get("retData", []):
        if "excel" not in f.get("MimeType", "") and not f["FilePath"].endswith(".xls"):
            continue
        day = dt.datetime.strptime(f["Title_"].split("_")[0], "%d.%m.%y").date()
        if day not in out or f["Id"] > out[day][0]:
            out[day] = (f["Id"], f["FilePath"])
    return {d: p for d, (_, p) in sorted(out.items())}


def download(path: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(CDN + path, headers={"User-Agent": UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())
    time.sleep(0.5)  # be polite to a public server
    return dest


def parse_timeseries(xls_path: Path, day: dt.date) -> list[dict]:
    """Return 96 rows of {ts, demand, <fuel MW>...} for one day."""
    sheet = xlrd.open_workbook(str(xls_path)).sheet_by_name("TimeSeries")
    header_row = next(r for r in range(sheet.nrows)
                      if str(sheet.cell_value(r, 0)).strip().upper() == "TIME")
    cols: dict[str, int] = {}
    for c in range(sheet.ncols):
        text = " ".join(str(sheet.cell_value(header_row, c)).upper().split())
        for key, field in HEADER_MAP.items():
            # "STORAGE DEMAND" (charging) must not be mistaken for STORAGE generation.
            if text.startswith(key) and field not in cols and not text.startswith("STORAGE DEMAND"):
                if key == "DEMAND MET" and text.startswith("NET"):
                    continue
                cols[field] = c
    missing = set(HEADER_MAP.values()) - set(cols)
    if missing:
        raise ValueError(f"{xls_path.name}: missing columns {sorted(missing)}")

    rows = []
    for r in range(header_row + 1, sheet.nrows):
        t = str(sheet.cell_value(r, 0)).strip()
        if ":" not in t or len(t) > 5:
            continue
        hh, mm = (int(x) for x in t.split(":"))
        row = {"ts": dt.datetime.combine(day, dt.time(hh, mm)).isoformat(timespec="minutes")}
        for field, c in cols.items():
            v = sheet.cell_value(r, c)
            row[field] = float(v) if v not in ("", None) else 0.0
        rows.append(row)
    if len(rows) != 96:
        raise ValueError(f"{xls_path.name}: expected 96 blocks, got {len(rows)}")
    return rows
