#!/bin/bash
# Run the full daily pipeline once (not under PM2)
# Usage: bash scripts/run_daily_once.sh
# Usage: bash scripts/run_daily_once.sh --dry-run

set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
python3 -m app.workers.daily_run "$@"
