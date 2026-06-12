#!/bin/bash
# Start all McDEE services under PM2

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$REPO_DIR/.venv/bin/python3"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: .venv not found. Run: bash scripts/setup.sh"
    exit 1
fi

cd "$REPO_DIR"

echo "=== Starting McDEE Services under PM2 ==="

# Kill existing instances if running
pm2 delete content-api content-daily content-render content-publisher content-analytics 2>/dev/null || true

# API server
pm2 start "$VENV_PYTHON" \
    --name content-api \
    --cwd "$REPO_DIR" \
    -- -m uvicorn app.main:app --host 127.0.0.1 --port 8899

# Daily run at 5 AM (use cron scheduler)
# For PM2 cron: requires pm2-cron or ecosystem.config.js
# For now, run as persistent process with internal scheduling
pm2 start "$VENV_PYTHON" \
    --name content-daily \
    --cwd "$REPO_DIR" \
    -- -m app.workers.daily_run

# Render queue worker (continuous)
pm2 start "$VENV_PYTHON" \
    --name content-render \
    --cwd "$REPO_DIR" \
    -- -m app.workers.render_queue

# Publish queue worker (continuous)
pm2 start "$VENV_PYTHON" \
    --name content-publisher \
    --cwd "$REPO_DIR" \
    -- -m app.workers.publish_queue

# Analytics loop (every 4 hours)
pm2 start "$VENV_PYTHON" \
    --name content-analytics \
    --cwd "$REPO_DIR" \
    -- -m app.workers.analytics_loop

pm2 save

echo ""
echo "=== PM2 Services Started ==="
pm2 list

echo ""
echo "Useful commands:"
echo "  pm2 logs content-daily"
echo "  pm2 logs content-render"
echo "  pm2 logs content-publisher"
echo "  pm2 status"
echo "  watch -n 2 nvidia-smi"
