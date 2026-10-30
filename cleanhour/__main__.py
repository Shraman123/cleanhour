"""cleanhour CLI.

  python -m cleanhour fetch --days 30          # pull Grid-India + IEX data
  python -m cleanhour plan --hours 2           # when should a 2h job run?
  python -m cleanhour run --hours 2 -- python train.py   # wait for that window, then run
  python -m cleanhour report                   # backtest + write site/data.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time

from . import analysis, dataset
from .scheduler import best_window, forecast, window_mean


def _plan(args) -> tuple:
    carbon, price = dataset.load_series()
    now = dt.datetime.now()
    fc = forecast(carbon, now, args.within)
    # Use cleared DAM prices where they exist; beyond that, last week's hourly median.
    price_fc = forecast({t: p for t, p in price.items() if p is not None and t < now}, now, args.within)
    price = {t: price.get(t) if price.get(t) is not None else price_fc[t] for t in fc}
    w = best_window(fc, args.hours, price, args.objective, args.price_weight)
    first = min(fc)
    return w, fc, price, first


def cmd_plan(args) -> int:
    w, fc, price, first = _plan(args)
    now_c = window_mean(fc, first, args.hours)
    print(f"Job: {args.hours}h, objective={args.objective}, horizon={args.within}h")
    print(f"  Best window : {w.start:%a %d %b %H:%M} -> {w.end:%H:%M}  "
          f"~{w.carbon:.0f} gCO2/kWh" + (f", Rs {w.price:.2f}/kWh" if w.price else ""))
    print(f"  Start now   : {first:%a %d %b %H:%M}               ~{now_c:.0f} gCO2/kWh")
    print(f"  Carbon cut vs starting now: {100 * (1 - w.carbon / now_c):.0f}%")
    if args.kwh:
        saved = args.kwh * (now_c - w.carbon)
        print(f"  For a {args.kwh} kWh job that is {saved:.0f} gCO2 avoided")
    return 0


def cmd_run(args) -> int:
    if not args.cmd:
        print("usage: cleanhour run --hours N -- <command...>", file=sys.stderr)
        return 2
    w, *_ = _plan(args)
    wait = (w.start - dt.datetime.now()).total_seconds()
    print(f"[cleanhour] cleanest {args.hours}h window starts {w.start:%a %H:%M} "
          f"(~{w.carbon:.0f} gCO2/kWh); waiting {max(wait, 0) / 3600:.1f}h")
    if args.dry_run:
        return 0
    if wait > 0:
        time.sleep(wait)
    print(f"[cleanhour] starting: {' '.join(args.cmd)}", flush=True)
    return subprocess.call(args.cmd)


def cmd_fetch(args) -> int:
    dataset.build(args.days)
    analysis.export_site()
    print(f"Updated {analysis.SITE_DATA}")
    return 0


def cmd_report(args) -> int:
    p = analysis.export_site()
    for b in p["backtest"]:
        print(f"{b['job_hours']}h job, {b['submissions']} submissions: run-now {b['carbon_run_now']} -> "
              f"scheduled {b['carbon_scheduled']} g/kWh ({b['carbon_saving_pct']}% less; "
              f"oracle {b['oracle_saving_pct']}%), price Rs {b['price_run_now']} -> "
              f"{b['price_scheduled']} ({b['price_saving_pct']}% less)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cleanhour")
    sub = ap.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch"); f.add_argument("--days", type=int, default=30); f.set_defaults(fn=cmd_fetch)
    r = sub.add_parser("report"); r.set_defaults(fn=cmd_report)
    for name, fn in (("plan", cmd_plan), ("run", cmd_run)):
        p = sub.add_parser(name)
        p.add_argument("--hours", type=int, default=2, help="job length in hours")
        p.add_argument("--within", type=int, default=24, help="deadline: must finish within N hours")
        p.add_argument("--objective", choices=["carbon", "price", "blend"], default="carbon")
        p.add_argument("--price-weight", type=float, default=0.5)
        p.add_argument("--kwh", type=float, help="job energy, to print grams avoided")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("cmd", nargs=argparse.REMAINDER)
        p.set_defaults(fn=fn)
    args = ap.parse_args(argv)
    if getattr(args, "cmd", None) and args.cmd[0] == "--":
        args.cmd = args.cmd[1:]
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
