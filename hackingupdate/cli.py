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
def run(step, no_cache_clear, age_days):
    """Run the daily security briefing pipeline."""
    import os
    if age_days is not None:
        os.environ["ARTICLE_MAX_AGE_DAYS"] = str(age_days)
        # Update imported config variable if needed
        import hackingupdate.config as cfg
        cfg.ARTICLE_MAX_AGE_DAYS = age_days

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

    for step_name in steps:
        click.echo(f"📤 Sending {step_name} notification...")
        success = run_step(step_name)
        if not success:
            click.echo(f"  ❌ {step_name} notification failed.")
        else:
            click.echo(f"  ✅ {step_name} notification sent!")


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
    click.echo(f"\nRun a single step: hackingupdate run --step <name>")


# ─── db ───────────────────────────────────────────────────────────────────────

@cli.group()
def db():
    """Query the SQLite findings database."""
    pass


@db.command("stats")
def db_stats():
    """Show database summary statistics."""
    import sys as _sys
    _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent / "scripts"))
    _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))

    try:
        from scripts import db_manager
        db_manager.init_db()
        stats = db_manager.get_stats()
        click.echo(f"📊 Database Statistics:\n")
        click.echo(f"  Database:        {stats['db_path']}")
        click.echo(f"  Total Findings:  {stats['total_findings']}")
        click.echo(f"  Unique Days:     {stats['unique_dates']}")
        click.echo(f"  Pipeline Runs:   {stats['total_runs']}")
        click.echo(f"  Latest Date:     {stats['latest_date']} ({stats['latest_count']} findings)")
    except Exception as e:
        click.echo(f"❌ Could not read database: {e}")


@db.command("today")
def db_today():
    """Show today's findings from the database."""
    import sys as _sys
    _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent / "scripts"))
    _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))

    try:
        from scripts import db_manager
        db_manager.init_db()
        findings = db_manager.get_findings_by_date()

        if not findings:
            click.echo("No findings stored for today yet.")
            return

        click.echo(f"🔒 Today's Findings ({len(findings)}):\n")
        for f in findings:
            severity = f.get("severity", "?")
            rank = f.get("rank", 0)
            title = f.get("title", "")[:70]
            click.echo(f"  [{severity:8s}] Rank {rank:2d} | {title}")
    except Exception as e:
        click.echo(f"❌ Could not read database: {e}")


@db.command("history")
@click.option("--limit", "-n", default=10, help="Number of runs to show.")
def db_history(limit):
    """Show pipeline run history."""
    import sys as _sys
    _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent / "scripts"))
    _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))

    try:
        from scripts import db_manager
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


if __name__ == "__main__":
    cli()

