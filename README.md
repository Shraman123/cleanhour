# CleanHour

**Carbon-aware scheduling for AI jobs on India's grid.**

India's grid swings hard every day. At noon, solar meets a big share of demand. By 9 pm, solar is gone and coal fills the gap. CleanHour measures that swing from Grid-India's own data, hour by hour. It then starts heavy jobs (training runs, batch inference, ETL) in the cleanest window before your deadline. On the power exchange that window is usually the cheapest too.

**Live dashboard:** https://cleanhour.vercel.app

## Findings: last 30 days of Grid-India data (30 Sep – 29 Oct 2026)

| | 12:00 | 21:00 |
|---|---|---|
| Grid carbon intensity (30-day mean) | **501 gCO₂/kWh** | **747 gCO₂/kWh** |
| Share from solar/wind/hydro/nuclear | 46% | 18% |
| IEX Day-Ahead price (30-day mean) | **₹1.67/kWh** | **₹9.00/kWh** |

- A kWh used at noon carries **33% less CO₂** than one used at 9 pm. On the exchange it costs **81% less**.
- **Backtest:** a 2-hour job was submitted at every hour of the month, and the scheduler saw only the past. It cut CO₂ by **26.7%** against starting immediately. With perfect hindsight the best possible was 27.0%. The price paid fell 76%, from ₹6.83 to ₹1.64 per kWh.
- **Real job:** a measured CIFAR-10 training run on a GTX 1650 laptop is pending (see `experiments/`).

## Install and use

```bash
pip install -r requirements.txt
python -m cleanhour fetch --days 30            # pull Grid-India PSP + IEX DAM data
python -m cleanhour plan --hours 2 --kwh 50    # cleanest 2h window in the next 24h
python -m cleanhour plan --hours 3 --objective price
python -m cleanhour run --hours 2 --within 24 -- python train.py   # waits, then runs
python -m cleanhour report                     # backtest + rebuild site/data.json
```

`--objective` is `carbon` (default), `price` or `blend` (`--price-weight 0.5`). `--within` is the deadline: the job must start and finish inside that many hours.

## How it works

1. **Data.** Grid-India (NLDC) publishes a daily *Power Supply Position* report. Its `TimeSeries` sheet gives all-India MW by fuel every 15 minutes: thermal (coal + lignite), gas, nuclear, hydro, wind, solar, storage and others. `cleanhour/grid.py` lists the files through the same API that grid-india.in uses, downloads the `.xls` files, and parses them by header name. Prices come from the IEX Day-Ahead Market (`cleanhour/iex.py`).
2. **Intensity.** Generation-weighted direct emissions (`cleanhour/carbon.py`): coal/lignite 0.96 tCO₂/MWh (the CEA CO₂ Baseline Database operating margin), gas 0.45, everything else 0. The 30-day mean comes out at 686 g/kWh. CEA's published grid average is about 0.71–0.79 t/MWh depending on year and boundary.
3. **Forecast.** Seasonal naive: each future hour is the median of the same hour over the past 7 days. India's solar-driven daily cycle is so regular that this lands within 0.3 points of perfect hindsight. Prices need no forecast inside the cleared DAM day, because they are already published. Hours beyond that use the same median.
4. **Schedule.** The planner slides a window over the 24-hour horizon and picks the contiguous block with the lowest mean (`cleanhour/scheduler.py`).

## Laptop experiment

`experiments/laptop_train.py` trains a 1.2M-parameter CNN on CIFAR-10 on a GTX 1650 laptop, with CodeCarbon recording energy. `experiments/compare.py` prices the measured kWh at each hour of the grid. The job uses the same energy at any hour. Only the CO₂ and price attached to each kWh change.

## Caveats

- **Direct emissions only.** Lifecycle factors would lift every hour a little, but would barely change the noon-vs-night gap.
- **National average.** A real facility sits in one state, under specific power contracts. Regional data is the next step.
- **Partly estimated energy.** On Windows, CodeCarbon *estimates* CPU and RAM power (there are no RAPL counters). GPU power is measured through NVML.
- **Exchange prices.** The DAM price is what a bulk buyer on the exchange pays. Home and most commercial tariffs are flat, except where time-of-day tariffs apply.

## Layout

```
cleanhour/      grid.py (Grid-India) · iex.py (prices) · carbon.py · scheduler.py · analysis.py (backtest) · __main__.py (CLI)
experiments/    laptop_train.py · compare.py
data/           hourly.csv · grid_15min.csv · prices.csv · experiment.json · emissions.csv (CodeCarbon)
site/           static dashboard (index.html, app.js, data.json) deployed on Vercel
tests/          parser checked against a real PSP report, scheduler and forecast unit tests
```

`scripts/refresh.sh` refreshes the data, pushes and redeploys. It runs from a local machine because Grid-India resets connections from GitHub Actions' US runners. CI runs the tests on every push.

Data: [Grid-India](https://grid-india.in/en/reports/daily-psp-report) and [IEX](https://www.iexindia.com/market-data/day-ahead-market/market-snapshot). Emission factor: [CEA CO₂ Baseline Database](https://cea.nic.in/cdm-co2-baseline-database/). MIT licensed.
