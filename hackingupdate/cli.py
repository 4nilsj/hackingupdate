"""
CLI entry point for HackingUpdate.

Usage:
    hackingupdate run                  # Full pipeline
    hackingupdate run --step fetch     # Single step
    hackingupdate run --step rank      # Only ranking
    hackingupdate run --no-cache-clear # Keep existing cache
    hackingupdate notify --whatsapp    # Send notifications only
    hackingupdate notify --teams       # Send Teams notification only
    hackingupdate feeds list           # Show configured feeds
    hackingupdate feeds add <url>      # Add a new feed
    hackingupdate init                 # Show config info
    hackingupdate version              # Show version
"""

import click
from pathlib import Path

from hackingupdate import __version__
from hackingupdate.pipeline import run_pipeline, run_step, PIPELINE_STEPS


@click.group()
@click.version_option(version=__version__, prog_name="hackingupdate")
def cli():
    """HackingUpdate — AI-powered daily security intelligence briefing."""
    pass


# ─── run ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--step", "-s",
    type=click.Choice([s[0] for s in PIPELINE_STEPS], case_sensitive=False),
    default=None,
    help="Run only a specific pipeline step.",
)
@click.option(
    "--no-cache-clear",
    is_flag=True,
    default=False,
    help="Skip clearing the cache before running.",
)
@click.option(
    "--age-days", "-a",
    type=int,
    default=None,
    help="Max article age in days (overrides ARTICLE_MAX_AGE_DAYS env var).",
)
@click.option(
    "--cross-day-days",
    type=int,
    default=None,
    help="Days of historical findings to deduplicate against (default: 7).",
)
@click.option(
    "--no-cross-day-dedupe",
    is_flag=True,
    default=False,
    help="Disable cross-day SQLite deduplication.",
)
def run(step, no_cache_clear, age_days, cross_day_days, no_cross_day_dedupe):
    """Run the daily security briefing pipeline."""
    import os
    import hackingupdate.config as cfg

    if age_days is not None:
        os.environ["ARTICLE_MAX_AGE_DAYS"] = str(age_days)
        cfg.ARTICLE_MAX_AGE_DAYS = age_days

    if cross_day_days is not None:
        os.environ["CROSS_DAY_DEDUPE_DAYS"] = str(cross_day_days)
        cfg.CROSS_DAY_DEDUPE_DAYS = cross_day_days

    if no_cross_day_dedupe:
        os.environ["ENABLE_CROSS_DAY_DEDUPE"] = "false"
        cfg.ENABLE_CROSS_DAY_DEDUPE = False

    if step:
        click.echo(f"🔒 Running single step: {step}")
        success = run_step(step)
    else:
        click.echo("🔒 Running full Daily Security Briefing Pipeline...")
        steps_list = None
        success = run_pipeline(steps=steps_list, skip_cache_clear=no_cache_clear)

    if success:
        click.echo("✅ Pipeline completed successfully!")
    else:
        click.echo("❌ Pipeline finished with errors. Check logs for details.")
        raise SystemExit(1)


@cli.command()
@click.option("--whatsapp", is_flag=True, help="Send WhatsApp notification.")
@click.option("--teams", is_flag=True, help="Send Teams notification.")
@click.option("--email", is_flag=True, help="Send Email notification.")
@click.option("--all", "all_channels", is_flag=True, help="Send to all channels.")
@click.option("--channel", "-c", type=click.Choice(["whatsapp", "teams", "email", "all"], case_sensitive=False), help="Select notification channel.")
def notify(whatsapp, teams, email, all_channels, channel):
    """Send notifications via configured channels."""
    if channel:
        channel = channel.lower()
        if channel == "whatsapp":
            whatsapp = True
        elif channel == "teams":
            teams = True
        elif channel == "email":
            email = True
        elif channel == "all":
            all_channels = True

    if not whatsapp and not teams and not email and not all_channels:
        click.echo("Specify a channel: --whatsapp, --teams, --email, --channel <name>, or --all")
        raise SystemExit(1)

    steps = []
    if whatsapp or all_channels:
        steps.append("whatsapp")
    if teams or all_channels:
        steps.append("teams")
    if email or all_channels:
        steps.append("email")

    failed = False
    for step_name in steps:
        click.echo(f"📤 Sending {step_name} notification...")
        success = run_step(step_name)
        if not success:
            failed = True
            click.echo(f"  ❌ {step_name} notification failed.")
        else:
            click.echo(f"  ✅ {step_name} notification sent!")

    if failed:
        raise SystemExit(1)


# ─── feeds ────────────────────────────────────────────────────────────────────

@cli.group()
def feeds():
    """Manage RSS/Atom feed sources."""
    pass


@feeds.command("list")
def feeds_list():
    """Show all configured feed URLs."""
    from hackingupdate.config import FEEDS_FILE

    if not FEEDS_FILE.exists():
        click.echo("No feeds file found. Run 'hackingupdate init' first.")
        return

    with open(FEEDS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    feed_urls = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]

    if not feed_urls:
        click.echo("No feeds configured.")
        return

    click.echo(f"📡 Configured feeds ({len(feed_urls)}):\n")
    for i, url in enumerate(feed_urls, 1):
        click.echo(f"  {i}. {url}")


@feeds.command("add")
@click.argument("url")
@click.option("--verify", is_flag=True, default=False, help="Verify that the URL is a reachable RSS/Atom feed.")
def feeds_add(url, verify):
    """Add a new feed URL."""
    from hackingupdate.config import FEEDS_FILE

    # Validate URL format
    if not url.startswith(("http://", "https://")):
        click.echo("❌ Invalid URL. Must start with http:// or https://")
        raise SystemExit(1)

    if verify:
        click.echo(f"🔍 Verifying feed URL: {url}...")
        import feedparser
        import requests
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            if not parsed.entries and not parsed.feed.get("title"):
                click.echo("⚠️ Warning: URL responded, but no RSS/Atom feed entries or title found.")
            else:
                title = parsed.feed.get("title", "Unknown")
                click.echo(f"  Verified feed: '{title}' ({len(parsed.entries)} entries)")
        except Exception as e:
            click.echo(f"❌ Could not verify feed URL: {e}")
            raise SystemExit(1)

    # Check for duplicates
    existing = []
    if FEEDS_FILE.exists():
        with open(FEEDS_FILE, "r", encoding="utf-8") as f:
            existing = [line.strip() for line in f.readlines()]

    if url in existing:
        click.echo(f"⚠️  Feed already exists: {url}")
        return

    with open(FEEDS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{url}\n")

    click.echo(f"✅ Added feed: {url}")


@feeds.command("import")
@click.argument("opml_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def feeds_import(opml_file):
    """Import feed URLs from an OPML file."""
    import xml.etree.ElementTree as ET
    from hackingupdate.config import FEEDS_FILE

    click.echo(f"📥 Importing feeds from OPML: {opml_file}...")
    try:
        tree = ET.parse(opml_file)
        root = tree.getroot()
        imported = 0
        skipped = 0

        # Existing feeds
        existing = set()
        if FEEDS_FILE.exists():
            with open(FEEDS_FILE, "r", encoding="utf-8") as f:
                existing = set(line.strip() for line in f if line.strip() and not line.strip().startswith("#"))

        new_urls = []
        for outline in root.findall(".//outline"):
            xml_url = outline.get("xmlUrl") or outline.get("url")
            if xml_url and xml_url.startswith(("http://", "https://")):
                if xml_url in existing:
                    skipped += 1
                else:
                    existing.add(xml_url)
                    new_urls.append(xml_url)
                    imported += 1

        if new_urls:
            with open(FEEDS_FILE, "a", encoding="utf-8") as f:
                for u in new_urls:
                    f.write(f"{u}\n")

        click.echo(f"✅ Imported {imported} new feed(s) ({skipped} skipped as duplicates).")
    except Exception as e:
        click.echo(f"❌ Failed to parse OPML file: {e}")
        raise SystemExit(1)


@feeds.command("export")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=Path("feeds.opml"), help="Output OPML file path.")
def feeds_export(output):
    """Export configured feed URLs to an OPML file."""
    from hackingupdate.config import FEEDS_FILE
    import xml.etree.ElementTree as ET

    if not FEEDS_FILE.exists():
        click.echo("No feeds file found.")
        return

    with open(FEEDS_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    if not urls:
        click.echo("No feeds to export.")
        return

    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    title = ET.SubElement(head, "title")
    title.text = "HackingUpdate Feeds Export"
    body = ET.SubElement(opml, "body")

    for url in urls:
        ET.SubElement(body, "outline", type="rss", xmlUrl=url, text=url)

    tree = ET.ElementTree(opml)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)
    click.echo(f"✅ Exported {len(urls)} feed(s) to {output}")


@feeds.command("remove")
@click.argument("url")
def feeds_remove(url):
    """Remove a feed URL."""
    from hackingupdate.config import FEEDS_FILE

    if not FEEDS_FILE.exists():
        click.echo("No feeds file found.")
        return

    with open(FEEDS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = [line for line in lines if line.strip() != url]

    if len(new_lines) == len(lines):
        click.echo(f"⚠️  Feed not found: {url}")
        return

    with open(FEEDS_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    click.echo(f"🗑️  Removed feed: {url}")


# ─── init ─────────────────────────────────────────────────────────────────────

@cli.command()
def init():
    """Display configuration and project info."""
    from hackingupdate.config import (
        BASE_DIR, CACHE_DIR, FEEDS_DIR, REPORTS_DIR, LOGS_DIR,
        FEEDS_FILE, OPENROUTER_MODEL, TEAMS_WEBHOOK_URL,
        TWILIO_ACCOUNT_SID, TWILIO_TO_NUMBER, SMTP_HOST, SMTP_TO_EMAILS,
        ARTICLE_MAX_AGE_DAYS, LLM_BATCH_DELAY,
    )

    click.echo(f"🔒 HackingUpdate v{__version__}\n")
    click.echo(f"  Project Root:  {BASE_DIR}")
    click.echo(f"  Cache Dir:     {CACHE_DIR}")
    click.echo(f"  Feeds Dir:     {FEEDS_DIR}")
    click.echo(f"  Reports Dir:   {REPORTS_DIR}")
    click.echo(f"  Logs Dir:      {LOGS_DIR}")
    click.echo(f"  Feeds File:    {FEEDS_FILE}")
    click.echo()
    click.echo("  Pipeline Settings:")
    click.echo(f"    Max Article Age: {ARTICLE_MAX_AGE_DAYS} day(s)")
    click.echo(f"    LLM Batch Delay: {LLM_BATCH_DELAY}s")
    from hackingupdate.config import CROSS_DAY_DEDUPE_DAYS, ENABLE_CROSS_DAY_DEDUPE, CISA_KEV_CACHE_FILE
    click.echo(f"    Cross-Day Dedupe: {'✅ ' + str(CROSS_DAY_DEDUPE_DAYS) + ' days' if ENABLE_CROSS_DAY_DEDUPE else '❌ Disabled'}")
    click.echo(f"    CISA KEV Cache:   {'✅ ' + str(CISA_KEV_CACHE_FILE) if CISA_KEV_CACHE_FILE.exists() else '⏳ Not cached yet'}")
    click.echo()
    click.echo("  API & Channel Config:")
    click.echo(f"    LLM Model:       {OPENROUTER_MODEL}")
    click.echo(f"    Teams Webhook:   {'✅ Configured' if TEAMS_WEBHOOK_URL else '❌ Not set'}")
    click.echo(f"    Twilio SID:      {'✅ Configured' if TWILIO_ACCOUNT_SID else '❌ Not set'}")
    click.echo(f"    WhatsApp Target: {'✅ ' + TWILIO_TO_NUMBER if TWILIO_TO_NUMBER else '❌ Not set'}")
    click.echo(f"    SMTP Host:       {'✅ ' + SMTP_HOST if SMTP_HOST else '❌ Not set'}")
    click.echo(f"    Email Target:    {'✅ ' + SMTP_TO_EMAILS if SMTP_TO_EMAILS else '❌ Not set'}")

    # Show DB info
    from hackingupdate.config import DB_PATH
    db_exists = DB_PATH.exists()
    click.echo(f"    SQLite DB:       {'✅ ' + str(DB_PATH) if db_exists else '❌ Not created yet'}")


# ─── steps ────────────────────────────────────────────────────────────────────

@cli.command()
def steps():
    """Show all available pipeline steps."""
    click.echo("📋 Pipeline Steps:\n")
    for i, (name, _, description) in enumerate(PIPELINE_STEPS, 1):
        click.echo(f"  {i:2d}. {name:<15s}  {description}")
    click.echo("\nRun a single step: hackingupdate run --step <name>")


# ─── db ───────────────────────────────────────────────────────────────────────

@cli.group()
def db():
    """Query the SQLite findings database."""
    pass


@db.command("stats")
def db_stats():
    """Show database summary statistics."""
    try:
        from hackingupdate import db_manager
        db_manager.init_db()
        stats = db_manager.get_stats()
        click.echo("📊 Database Statistics:\n")
        click.echo(f"  Database:        {stats['db_path']}")
        click.echo(f"  Total Findings:  {stats['total_findings']}")
        click.echo(f"  Unique Days:     {stats['unique_dates']}")
        click.echo(f"  Pipeline Runs:   {stats['total_runs']}")
        click.echo(f"  CISA KEV Alerts: {stats.get('total_cisa_kev', 0)}")
        click.echo(f"  Ransomware Hits: {stats.get('total_ransomware', 0)}")
        click.echo(f"  Max EPSS Score:  {stats.get('max_epss', 0.0):.1%}")
        click.echo(f"  Latest Date:     {stats['latest_date']} ({stats['latest_count']} findings)")
    except Exception as e:
        click.echo(f"❌ Could not read database: {e}")


@db.command("today")
def db_today():
    """Show today's findings from the database."""
    try:
        from hackingupdate import db_manager
        db_manager.init_db()
        findings = db_manager.get_findings_by_date()

        if not findings:
            click.echo("No findings stored for today yet.")
            return

        click.echo(f"🔒 Today's Findings ({len(findings)}):\n")
        for f in findings:
            severity = f.get("severity", "?")
            rank = f.get("rank", 0)
            is_kev = bool(f.get("is_cisa_kev", 0))
            epss = float(f.get("epss_score") or 0.0)
            badges = []
            if is_kev:
                badges.append("🚨 CISA KEV")
            if epss >= 0.2:
                badges.append(f"EPSS: {epss:.0%}")
            badge_str = f" [{' | '.join(badges)}]" if badges else ""
            title = f.get("title", "")[:65]
            click.echo(f"  [{severity:8s}] Rank {rank:2d} | {title}{badge_str}")
    except Exception as e:
        click.echo(f"❌ Could not read database: {e}")


@db.command("history")
@click.option("--limit", "-n", default=10, help="Number of runs to show.")
def db_history(limit):
    """Show pipeline run history."""
    try:
        from hackingupdate import db_manager
        db_manager.init_db()
        runs = db_manager.get_run_history(limit)

        if not runs:
            click.echo("No pipeline runs logged yet.")
            return

        click.echo(f"📜 Pipeline Run History (last {len(runs)}):\n")
        for r in runs:
            click.echo(f"  {r['run_timestamp']}  |  "
                       f"Fetched: {r['articles_fetched']}  "
                       f"Stored: {r['articles_stored']}  "
                       f"Dups: {r['articles_skipped_dup']}  "
                       f"({r['pipeline_duration_sec']:.1f}s)")
    except Exception as e:
        click.echo(f"❌ Could not read database: {e}")


# ─── doctor ───────────────────────────────────────────────────────────────────

@cli.command()
def doctor():
    """Check system health: API keys, feeds, DB, disk space, and config."""
    import shutil
    import sqlite3
    import time
    import requests
    import feedparser

    import hackingupdate.config as cfg

    ok_count = 0
    warn_count = 0
    err_count = 0

    def _ok(msg: str):
        nonlocal ok_count
        ok_count += 1
        click.echo(f"  ✅ {msg}")

    def _warn(msg: str):
        nonlocal warn_count
        warn_count += 1
        click.echo(f"  ⚠️  {msg}")

    def _err(msg: str):
        nonlocal err_count
        err_count += 1
        click.echo(f"  ❌ {msg}")

    click.echo(f"\n🩺 HackingUpdate v{__version__} — Health Check\n")

    # ── 1. OpenRouter API Key ──────────────────────────────────────────────────
    click.echo("── LLM / AI ──────────────────────────────────────────────────")
    if not cfg.OPENROUTER_API_KEY:
        _err("OpenRouter API key not set (OPENROUTER_API_KEY missing in .env)")
    else:
        try:
            resp = requests.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {cfg.OPENROUTER_API_KEY}"},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                usage = data.get("usage", 0)
                limit = data.get("limit")
                limit_str = f"{limit:.0f}" if limit else "unlimited"
                _ok(f"OpenRouter API key valid  (model: {cfg.OPENROUTER_MODEL}, usage: ${usage:.4f} / ${limit_str})")
            elif resp.status_code == 401:
                _err(f"OpenRouter API key EXPIRED or INVALID — renew at https://openrouter.ai/keys")
            else:
                _warn(f"OpenRouter API key check returned HTTP {resp.status_code}")
        except Exception as e:
            _warn(f"Could not reach OpenRouter to validate key: {e}")

    # ── 2. CISA KEV Cache ──────────────────────────────────────────────────────
    click.echo("\n── Threat Intelligence ───────────────────────────────────────")
    kev_cache = cfg.CISA_KEV_CACHE_FILE
    if kev_cache.exists():
        age_sec = time.time() - kev_cache.stat().st_mtime
        age_h = age_sec / 3600
        try:
            import json as _json
            with open(kev_cache) as f:
                kev = _json.load(f)
            entry_count = len(kev)
            if age_h < cfg.CISA_KEV_CACHE_TTL_HOURS:
                _ok(f"CISA KEV cache fresh  ({entry_count:,} entries, updated {age_h:.1f}h ago)")
            else:
                _warn(f"CISA KEV cache stale  ({entry_count:,} entries, updated {age_h:.1f}h ago — TTL: {cfg.CISA_KEV_CACHE_TTL_HOURS}h)")
        except Exception:
            _warn("CISA KEV cache file exists but could not be read")
    else:
        _warn("CISA KEV cache not downloaded yet — run 'hackingupdate run --step rank' to populate")

    # EPSS API
    try:
        resp = requests.get(
            cfg.EPSS_API_URL,
            params={"cve": "CVE-2021-44228"},  # log4shell — always present
            timeout=8,
        )
        if resp.status_code == 200:
            _ok("EPSS API reachable  (api.first.org)")
        else:
            _warn(f"EPSS API returned HTTP {resp.status_code}")
    except Exception as e:
        _warn(f"EPSS API unreachable: {e}")

    # ── 3. Feed health ─────────────────────────────────────────────────────────
    click.echo("\n── Feeds ─────────────────────────────────────────────────────")
    if not cfg.FEEDS_FILE.exists():
        _err(f"Feeds file not found: {cfg.FEEDS_FILE}")
    else:
        with open(cfg.FEEDS_FILE) as f:
            feed_urls = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]

        dead_feeds = []
        slow_feeds = []

        for url in feed_urls:
            try:
                t0 = time.time()
                r = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
                elapsed = time.time() - t0
                if r.status_code == 200:
                    parsed = feedparser.parse(r.content)
                    entry_count = len(parsed.entries)
                    if entry_count == 0:
                        dead_feeds.append((url, "no entries returned"))
                    elif elapsed > 5:
                        slow_feeds.append((url, f"{elapsed:.1f}s"))
                else:
                    dead_feeds.append((url, f"HTTP {r.status_code}"))
            except requests.exceptions.SSLError as e:
                dead_feeds.append((url, f"SSL error: {str(e)[:60]}"))
            except Exception as e:
                dead_feeds.append((url, str(e)[:60]))

        healthy = len(feed_urls) - len(dead_feeds)
        if not dead_feeds:
            _ok(f"All {len(feed_urls)} feeds healthy")
        else:
            _warn(f"{healthy}/{len(feed_urls)} feeds healthy — {len(dead_feeds)} failing:")
            for url, reason in dead_feeds:
                click.echo(f"       🔴 {url}")
                click.echo(f"          Reason: {reason}")
        if slow_feeds:
            _warn(f"{len(slow_feeds)} feeds responding slowly:")
            for url, t in slow_feeds:
                click.echo(f"       🟡 {url}  ({t})")

    # ── 4. SQLite Database ─────────────────────────────────────────────────────
    click.echo("\n── Database ──────────────────────────────────────────────────")
    db_path = cfg.DB_PATH
    if not db_path.exists():
        _warn("SQLite database not created yet — run the pipeline to initialise it")
    else:
        try:
            conn = sqlite3.connect(str(db_path))
            total = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            days = conn.execute("SELECT COUNT(DISTINCT briefing_date) FROM findings").fetchone()[0]
            conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            size_kb = db_path.stat().st_size / 1024
            _ok(f"SQLite DB healthy  ({total} findings across {days} days, {size_kb:.1f} KB)")
        except Exception as e:
            _err(f"SQLite DB error: {e}")

    # ── 5. Disk space ──────────────────────────────────────────────────────────
    click.echo("\n── Storage ───────────────────────────────────────────────────")
    total_b, used_b, free_b = shutil.disk_usage(cfg.BASE_DIR)
    free_gb = free_b / 1024**3
    if free_gb < 0.5:
        _err(f"Low disk space: {free_gb:.2f} GB free — cache/reports may fail")
    elif free_gb < 2.0:
        _warn(f"Disk space: {free_gb:.1f} GB free (below 2 GB recommended)")
    else:
        _ok(f"Disk space: {free_gb:.1f} GB free")

    # Reports and cache dir sizes
    for label, path in [("reports/", cfg.REPORTS_DIR), ("cache/", cfg.CACHE_DIR), ("logs/", cfg.LOGS_DIR)]:
        if path.exists():
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            click.echo(f"     {label:<12} {size/1024:.1f} KB")

    # ── 6. Notification channels ───────────────────────────────────────────────
    click.echo("\n── Notification Channels ─────────────────────────────────────")
    channels_configured = 0

    if cfg.TEAMS_WEBHOOK_URL:
        channels_configured += 1
        try:
            r = requests.head(cfg.TEAMS_WEBHOOK_URL, timeout=6)
            _ok(f"Teams webhook reachable  (HTTP {r.status_code})")
        except Exception as e:
            _warn(f"Teams webhook not reachable: {e}")
    else:
        click.echo("     Teams webhook:     ⬜ Not configured (TEAMS_WEBHOOK_URL)")

    if cfg.TWILIO_ACCOUNT_SID and cfg.TWILIO_AUTH_TOKEN:
        channels_configured += 1
        _ok(f"Twilio WhatsApp configured  → {cfg.TWILIO_TO_NUMBER}")
    else:
        click.echo("     Twilio WhatsApp:   ⬜ Not configured (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN)")

    if cfg.SMTP_HOST and cfg.SMTP_USERNAME:
        channels_configured += 1
        _ok(f"Email (SMTP) configured  ({cfg.SMTP_HOST}:{cfg.SMTP_PORT} → {cfg.SMTP_TO_EMAILS})")
    else:
        click.echo("     Email/SMTP:        ⬜ Not configured (SMTP_HOST / SMTP_USERNAME)")

    if channels_configured == 0:
        _warn("No notification channels configured — reports will only be saved to disk")

    # ── Summary ────────────────────────────────────────────────────────────────
    total_checks = ok_count + warn_count + err_count
    click.echo(f"\n{'─'*58}")
    if err_count == 0 and warn_count == 0:
        click.echo(f"✅ All {total_checks} checks passed — system is healthy")
    elif err_count == 0:
        click.echo(f"⚠️  {ok_count} ok · {warn_count} warning(s) · {err_count} error(s)  — check warnings above")
    else:
        click.echo(f"❌ {ok_count} ok · {warn_count} warning(s) · {err_count} error(s)  — fix errors before running pipeline")
    click.echo()


if __name__ == "__main__":
    cli()

