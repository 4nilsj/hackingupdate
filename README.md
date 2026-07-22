# HackingUpdate — Daily Security Intelligence Briefing

An AI-powered pipeline that aggregates security feeds, deduplicates findings, ranks threats by severity, and delivers a polished daily briefing to your team via HTML reports, Microsoft Teams, and WhatsApp.

## Features

- **Multi-Feed Aggregation** — RSS/Atom feeds from CISA, PacketStorm, SecurityWeek, BleepingComputer, and more (concurrent fetching)
- **AI-Powered Ranking** — LLM-based threat scoring with pentest-relevant tagging & automatic retry with exponential backoff
- **Smart Deduplication** — Fingerprint-based detection eliminates duplicate CVE coverage across feeds
- **Date Freshness Filter** — Configurable article age filter (default: 1 day, adjustable via CLI/env)
- **SQLite Persistence** — Stores findings date-wise with built-in duplicate prevention & pipeline metrics tracking
- **Beautiful HTML Reports** — Dark-mode, glassmorphism UI with search, filtering, and mobile-responsive design
- **RSS 2.0 Output Feed** — Generates `reports/rss.xml` and `reports/feed.xml` for syndication
- **Multi-Channel Notifications** — Microsoft Teams webhooks + Twilio WhatsApp + SMTP Email notifications
- **OPML Import/Export** — Seamlessly import & export feed subscriptions via OPML standard
- **Automated Daily Execution** — Cron-ready pipeline with log rotation & Docker healthchecks
- **Productized CLI** — Full `hackingupdate` command-line tool with subcommands
- **Docker Ready** — One-command containerized deployment

## Quick Start

### Option 1: CLI (pip install)

```bash
# Clone and install
git clone https://github.com/4nilsj/hackingupdate.git
cd hackingupdate
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
hackingupdate run
```

### Option 2: Docker

```bash
# Build and run
docker build -t hackingupdate .
docker run --env-file .env -v ./reports:/app/reports hackingupdate

# Or with docker compose
docker compose up
```

### Option 3: Legacy Shell Script

```bash
./run_brief.sh
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```env
# Required: LLM API key for threat ranking
OPENROUTER_API_KEY=sk-or-v1-xxxx
OPENROUTER_MODEL=google/gemini-2.5-flash:free

# Optional: Microsoft Teams webhook URL
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...

# Optional: Twilio WhatsApp
TWILIO_ACCOUNT_SID=ACxxxx
TWILIO_AUTH_TOKEN=xxxx
TWILIO_FROM_NUMBER=whatsapp:+14155238886
TWILIO_TO_NUMBER=whatsapp:+91xxxxxxxxxx

# Optional: Email / SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_TO_EMAILS=secops@company.com

# Optional: Tuning
ARTICLE_MAX_AGE_DAYS=1
LLM_BATCH_DELAY=2.0
LOG_FORMAT=text  # text or json
```

## Pipeline Architecture

```
feeds.txt → fetcher (concurrent) → extractor (date filter) → fingerprint_analyzer → dedupe
    → priority_ranker (LLM + retry) → build_working_set → db_manager (SQLite)
    → report_generator → html_generator → rss_generator
    → [teams_notifier, whatsapp_notifier, email_notifier] → prune_logs
```

| Step | Description | Critical? |
|---|---|---|
| `fetch` | Pull RSS/Atom feeds (concurrent) | ✅ Yes |
| `extract` | Clean HTML, filter articles by max age | ✅ Yes |
| `fingerprint` | Generate content hashes for dedup | ✅ Yes |
| `dedupe` | Remove duplicate articles (Jaccard similarity) | ✅ Yes |
| `rank` | AI-powered threat scoring (1-10) with retry | ✅ Yes |
| `workingset` | Select top-ranked articles for the report | ✅ Yes |
| `db_store` | Persist findings to SQLite (optional) | ⚡ Optional |
| `report` | Generate Markdown daily brief | ✅ Yes |
| `html` | Render HTML report with glassmorphism UI | ✅ Yes |
| `rss` | Generate RSS 2.0 XML feed | ⚡ Optional |
| `teams` | Send Teams webhook notification | ⚡ Optional |
| `whatsapp` | Send Twilio WhatsApp notification | ⚡ Optional |
| `email` | Send SMTP Email notification | ⚡ Optional |
| `prune` | Clean up logs older than 5 days | ⚡ Optional |

## CLI Commands

```bash
# Pipeline
hackingupdate run                  # Full pipeline
hackingupdate run --step fetch     # Single step only
hackingupdate run --step rank      # Only ranking
hackingupdate run --age-days 3     # Override article max age filter
hackingupdate run --no-cache-clear # Keep existing cache
hackingupdate steps                # List all pipeline steps

# Notifications
hackingupdate notify --whatsapp    # Send WhatsApp notification
hackingupdate notify --teams       # Send Teams notification
hackingupdate notify --email       # Send Email notification
hackingupdate notify --all         # Send to all channels

# Feed Management
hackingupdate feeds list           # Show configured feeds
hackingupdate feeds add <url>      # Add a new feed
hackingupdate feeds add <url> --verify # Add and verify feed URL
hackingupdate feeds remove <url>   # Remove a feed
hackingupdate feeds import <file>  # Import feeds from OPML file
hackingupdate feeds export         # Export feeds to feeds.opml

# Database
hackingupdate db stats             # Show DB summary (total findings, days)
hackingupdate db today             # Show today's findings with severity
hackingupdate db history           # Show pipeline run history

# Info
hackingupdate init                 # Show config, paths, API status
hackingupdate --version            # Show version
```

## SQLite Database

Findings are stored in `data/hackingupdate.db` with automatic deduplication:

- **Date-wise storage** — Each finding is tagged with its briefing date
- **No duplicates** — `UNIQUE(briefing_date, link)` constraint prevents re-insertion
- **Multiple runs safe** — Running the pipeline 5x in a day stores data only once
- **Severity tracking** — Auto-classified: Rank ≥8 = CRITICAL, ≥6 = HIGH, ≥4 = MEDIUM

```sql
-- Query example: Get today's critical findings
SELECT title, rank, severity FROM findings
WHERE briefing_date = date('now') AND severity = 'CRITICAL'
ORDER BY rank DESC;
```

## Scheduling (cron)

```bash
# Daily at 7:30 AM IST
30 2 * * * cd /path/to/hackingupdate && /path/to/venv/bin/hackingupdate run >> logs/cron.log 2>&1
```

## Project Structure

```
hackingupdate/
├── hackingupdate/          # Python package (productized)
│   ├── __init__.py
│   ├── cli.py              # Click-based CLI entry point
│   ├── config.py           # Configuration management
│   └── pipeline.py         # Orchestration engine
├── scripts/                # Pipeline step modules
│   ├── fetcher.py          # RSS/Atom feed fetcher
│   ├── extractor.py        # HTML cleaner + date filter
│   ├── fingerprint_analyzer.py  # Content fingerprinting
│   ├── dedupe_fingerprints.py   # Deduplication engine
│   ├── priority_ranker.py  # AI-powered threat ranker
│   ├── build_working_set.py# Working set builder
│   ├── db_manager.py       # SQLite persistence layer
│   ├── report_generator.py # Markdown report generator
│   ├── html_generator.py   # HTML report renderer
│   ├── teams_notifier.py   # MS Teams webhook sender
│   ├── whatsapp_notifier.py# Twilio WhatsApp sender
│   └── prune_logs.py       # Log rotation
├── feeds/                  # Feed URL configuration
│   └── feeds.txt
├── data/                   # SQLite database (auto-created)
│   └── hackingupdate.db
├── cache/                  # Runtime JSON cache (cleared each run)
├── reports/                # Generated HTML & Markdown reports
├── logs/                   # Pipeline execution logs
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── Makefile
├── run_brief.sh            # Legacy shell orchestrator
├── .env.example
└── README.md
```

## Make Commands

```bash
make install        # pip install -e ".[dev]"
make run            # hackingupdate run
make feeds          # hackingupdate feeds list
make notify-wa      # Send WhatsApp notification
make notify-teams   # Send Teams notification
make docker-build   # docker build -t hackingupdate .
make docker-run     # Run in Docker with .env
make clean          # Remove cache, reports, logs
make test           # pytest tests/ -v
```

## License

MIT
