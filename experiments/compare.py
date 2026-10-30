"""Price the measured laptop run at noon vs 9 pm on India's grid.

The job uses the same energy whenever it runs; what changes is how much CO2
each kWh carries and what it costs. We use the 30-day hour-of-day means from
data/hourly.csv and IEX DAM prices.

    python experiments/compare.py
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cleanhour.analysis import export_site, hour_of_day  # noqa: E402
from cleanhour.dataset import DATA, read_csv  # noqa: E402


def main():
    raw = json.loads((DATA / "experiment_raw.json").read_text())
    kwh = raw["energy_kwh"]
    hod = {h["hour"]: h for h in hour_of_day(read_csv(DATA / "hourly.csv"))}
    noon, nine = hod[12], hod[21]
    best = min(hod.values(), key=lambda h: h["intensity_mean"])
    worst = max(hod.values(), key=lambda h: h["intensity_mean"])

    g = lambda h: kwh * h["intensity_mean"]
    out = {
        **raw,
        "noon": {"intensity": noon["intensity_mean"], "grams": round(g(noon), 2),
                 "price": noon["price_mean"]},
        "nine_pm": {"intensity": nine["intensity_mean"], "grams": round(g(nine), 2),
                    "price": nine["price_mean"]},
        "cleanest_hour": best["hour"], "dirtiest_hour": worst["hour"],
        "saving_pct": round(100 * (1 - noon["intensity_mean"] / nine["intensity_mean"]), 1),
        "price_saving_pct": round(100 * (1 - noon["price_mean"] / nine["price_mean"]), 1),
        # Same shift applied to 1 MWh of compute (roughly one 8-GPU server for ~4 days).
        "per_mwh_kg_avoided": round(nine["intensity_mean"] - noon["intensity_mean"], 1),
        "per_mwh_rs_saved": round((nine["price_mean"] - noon["price_mean"]) * 1000),
        "daily_mean_intensity": round(statistics.mean(h["intensity_mean"] for h in hod.values()), 1),
    }
    (DATA / "experiment.json").write_text(json.dumps(out, indent=2))
    export_site(out)
    print(f"Measured: {kwh * 1000:.1f} Wh over {raw['duration_s'] / 60:.1f} min "
          f"(GPU {raw['gpu_kwh'] * 1000:.1f} Wh measured, CPU {raw['cpu_kwh'] * 1000:.1f} Wh est., "
          f"RAM {raw['ram_kwh'] * 1000:.1f} Wh est.)")
    print(f"  at 12:00  {noon['intensity_mean']:.0f} g/kWh -> {g(noon):.1f} gCO2, DAM Rs {noon['price_mean']}/kWh")
    print(f"  at 21:00  {nine['intensity_mean']:.0f} g/kWh -> {g(nine):.1f} gCO2, DAM Rs {nine['price_mean']}/kWh")
    print(f"  noon is {out['saving_pct']}% lower carbon and {out['price_saving_pct']}% cheaper at DAM prices")
    print(f"  per MWh shifted: {out['per_mwh_kg_avoided']} kg CO2 avoided, Rs {out['per_mwh_rs_saved']:,} saved")


if __name__ == "__main__":
    main()
