// PM2 Ecosystem Config
// Usage: pm2 start ecosystem.config.js
// Preferred over pm2_start.sh for cron scheduling

const path = require("path");
const repoDir = __dirname;
const python = path.join(repoDir, ".venv/bin/python3");

module.exports = {
  apps: [
    {
      name: "content-api",
      script: python,
      args: "-m uvicorn app.main:app --host 127.0.0.1 --port 8899",
      cwd: repoDir,
      watch: false,
      autorestart: true,
      max_restarts: 10,
      log_file: "logs/content-api.log",
      env: { PYTHONPATH: repoDir },
    },
    {
      // Daily pipeline — runs once at 5:00 AM local time
      name: "content-daily",
      script: python,
      args: "-m app.workers.daily_run",
      cwd: repoDir,
      watch: false,
      autorestart: false,         // Don't restart — cron fires it
      cron_restart: "0 5 * * *",  // 5:00 AM daily
      log_file: "logs/content-daily.log",
      env: { PYTHONPATH: repoDir },
    },
    {
      // Render queue — polls every 60s for pending topics
      name: "content-render",
      script: python,
      args: "-m app.workers.render_queue",
      cwd: repoDir,
      watch: false,
      autorestart: true,
      max_restarts: 20,
      log_file: "logs/content-render.log",
      env: { PYTHONPATH: repoDir },
    },
    {
      // Publish queue — polls every 2 min for due uploads
      name: "content-publisher",
      script: python,
      args: "-m app.workers.publish_queue",
      cwd: repoDir,
      watch: false,
      autorestart: true,
      max_restarts: 20,
      log_file: "logs/content-publisher.log",
      env: { PYTHONPATH: repoDir },
    },
    {
      // Analytics — runs every 4 hours
      name: "content-analytics",
      script: python,
      args: "-m app.workers.analytics_loop",
      cwd: repoDir,
      watch: false,
      autorestart: true,
      max_restarts: 10,
      log_file: "logs/content-analytics.log",
      env: { PYTHONPATH: repoDir },
    },
  ],
};
