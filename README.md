# McDEE Content Factory

**Autonomous trend-to-video pipeline for daily YouTube + X publishing.**

Runs locally on `taorig1`. Scans trends, ranks opportunities, generates scripts and assets, renders videos, queues uploads, posts to X, and learns from analytics — up to 10 videos/day.

---

## What It Does

```
trend_scanner  →  topic_ranker  →  research_agent  →  script_agent
     →  thumbnail_agent  →  voice_agent  →  video_agent
     →  quality_agent  →  queue_manager
     →  youtube_publisher  →  x_publisher  →  analytics_agent  →  (feedback loop)
```

**Daily output:** up to 10 upload packages, one per top trend, spaced evenly across an 8 AM–8 PM window.

---

## Safety Rules

1. Max 10 videos/day. No mass dumps.
2. No auto-posting until `AUTO_APPROVE=true` (default: false).
3. Quality score ≥ 75 required to enter publish queue.
4. No "guaranteed profit", "risk-free", or financial promise phrases — scripts are rejected.
5. No adult content, hate speech, extremism, jailbreak, or medical claim topics.
6. No direct copy-paste from sources — research grounds the script, never fills it.
7. No copyrighted music or video without license.
8. No secrets committed to Git.

---

## Hardware (taorig1)

- Ubuntu 24.04 / Python 3.12
- RTX 3090 24GB + 2× RTX 3060 12GB
- 32GB RAM / 2TB SSD
- Ollama running at `http://127.0.0.1:11434`

---

## Setup

```bash
git clone https://github.com/McDEE1311/mcdee-content-factory.git
cd mcdee-content-factory

bash scripts/setup.sh
```

This will:
- Create `.venv`
- Install all dependencies
- Copy `.env.example` → `.env`
- Initialize SQLite database
- Check Ollama and ffmpeg

Then edit your config:

```bash
nano .env                        # Add API keys
nano config/channels.yaml        # Set channel info
```

Verify setup:

```bash
python3 -m app.main
# → http://127.0.0.1:8899/health
```

---

## First Run (Dry Run — Scripts Only, No Render)

```bash
source .venv/bin/activate
python3 -m app.workers.daily_run --dry-run
```

Expected output:

```
outputs/upload_packages/YYYY-MM-DD/<topic-slug>/script.md
outputs/upload_packages/YYYY-MM-DD/<topic-slug>/metadata.json
outputs/upload_packages/YYYY-MM-DD/<topic-slug>/x_post.txt
```

---

## Full Run (Render + Package)

```bash
python3 -m app.workers.daily_run
```

This runs all phases: scan → rank → research → script → thumbnail → voice → video → quality → queue.

---

## Run Under PM2 (Recommended)

```bash
bash scripts/pm2_start.sh
# or
pm2 start ecosystem.config.js
```

Services started:

| PM2 Name | What It Does |
|---|---|
| `content-api` | FastAPI server at `:8899` |
| `content-daily` | Daily pipeline, fires at 5:00 AM |
| `content-render` | Polls for pending topics, renders assets |
| `content-publisher` | Fires scheduled publish queue entries |
| `content-analytics` | Collects analytics every 4 hours |

Monitor:

```bash
pm2 logs content-daily
pm2 logs content-render
pm2 status
watch -n 2 nvidia-smi
```

Health check:

```bash
bash scripts/healthcheck.sh
```

---

## Output Package Structure

Each approved video produces:

```
outputs/upload_packages/YYYY-MM-DD/<topic-slug>/
├── video.mp4           ← rendered video (if ffmpeg available)
├── thumbnail.png       ← 1280×720 thumbnail
├── metadata.json       ← title, description, tags
├── script.md           ← full script
└── x_post.txt          ← matching X post text
```

---

## Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| **0** | ✅ Done | Repo skeleton, DB, health endpoint, PM2 |
| **1** | ✅ Done | Trend scan + topic ranking + script generation |
| **2** | ✅ Done | TTS + thumbnails + video render + upload packages |
| **3** | 🔄 Active | Manual review — inspect packages, upload by hand for 7 days |
| **4** | Pending | YouTube OAuth + scheduled upload + X API posting |
| **5** | Pending | `AUTO_APPROVE=true` — fully autonomous |

**Do not skip Phase 3.** Run manual uploads for at least 7 days before enabling API posting.

---

## Enabling Autonomous Mode (Phase 5)

Only after quality is stable:

```bash
# In .env:
AUTO_APPROVE=true
```

This enables the publish queue to fire YouTube uploads and X posts automatically on schedule.

---

## Configuration Reference

### `.env` Key Settings

| Variable | Default | Description |
|---|---|---|
| `DAILY_VIDEO_LIMIT` | `10` | Max videos per day |
| `AUTO_APPROVE` | `false` | Enable autonomous publishing |
| `UPLOAD_START_HOUR` | `8` | Publish window start (local time) |
| `UPLOAD_END_HOUR` | `20` | Publish window end |
| `LOCAL_TIMEZONE` | `America/Chicago` | Your timezone |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Local LLM model |

### API Keys Needed (Per Phase)

| Key | Phase | Where to Get |
|---|---|---|
| `REDDIT_CLIENT_ID/SECRET` | Phase 1 (optional) | reddit.com/prefs/apps |
| `YOUTUBE_CLIENT_SECRET_FILE` | Phase 4 | Google Cloud Console |
| `X_API_KEY` / `X_ACCESS_TOKEN` | Phase 4 | developer.twitter.com |

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## Channel Strategy (First Channel)

**Niche:** AI Agents, GPU Infrastructure, Bittensor, Crypto Compute, Automation Tools

**Why:** Real technical context, harder for generic faceless channels to copy, high CPM ($15–40 range).

**Topic categories:**
1. AI agent tools and releases
2. Bittensor subnet updates
3. GPU / server hardware deals
4. Open-source AI model releases
5. Crypto compute networks
6. YouTube/content automation
7. AI business opportunities
8. Government auction hardware
9. Rural data center buildouts
10. Trading / market automation explainers

**Avoid:** generic stoicism, motivational content, fake wealth, celebrity gossip, copied news recaps.

**30-day targets:** 300 videos max, 100+ subs, 100K+ impressions, identify 3 winning clusters.

---

## Repo Structure

```
mcdee-content-factory/
├── app/
│   ├── agents/          ← one file per pipeline stage
│   ├── services/        ← external clients (Ollama, RSS, Reddit, TTS, etc.)
│   ├── prompts/         ← LLM prompt templates
│   ├── workers/         ← PM2 process entrypoints
│   ├── db.py            ← SQLAlchemy session management
│   ├── models.py        ← all ORM table definitions
│   ├── settings.py      ← pydantic-settings from .env
│   └── main.py          ← FastAPI app + /health
├── config/
│   ├── trend_sources.yaml
│   ├── safety_rules.yaml
│   └── channels.example.yaml
├── scripts/
│   ├── setup.sh
│   ├── init_db.py
│   ├── pm2_start.sh
│   ├── run_daily_once.sh
│   └── healthcheck.sh
├── tests/
├── data/                ← SQLite DB (gitignored)
├── logs/                ← rotating log files (gitignored)
├── outputs/             ← upload packages + rendered videos (gitignored)
├── .env.example
├── requirements.txt
└── ecosystem.config.js  ← PM2 config with cron
```

---

## Troubleshooting

**Ollama not responding:**
```bash
ollama serve &
ollama pull qwen2.5:7b-instruct
```

**No trends found:**
- pytrends is rate-limited by Google — RSS feeds will still run
- Check `logs/daily_run_YYYYMMDD.log`

**Video render fails:**
```bash
sudo apt install ffmpeg
```

**TTS not working:**
```bash
# Install Piper
pip install piper-tts
# or use espeak as fallback:
sudo apt install espeak
```

**DB issues:**
```bash
python3 scripts/init_db.py
```

---

## License

Private — McDEE1311. Not for redistribution.
