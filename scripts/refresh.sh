#!/usr/bin/env bash
# Refresh data, push, redeploy. Run from an Indian connection:
# Grid-India resets connections from GitHub Actions' US runners.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q
python -m cleanhour fetch --days 30
git add data/hourly.csv data/prices.csv data/grid_15min.csv site/data.json
git diff --cached --quiet || git commit -m "data: refresh $(date +%F)"
git push
(cd site && vercel deploy --prod --yes)
