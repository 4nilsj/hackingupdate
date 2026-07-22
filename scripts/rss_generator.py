"""
RSS 2.0 Feed Generator for HackingUpdate.

Reads the curated working set (or SQLite findings) and outputs standard RSS 2.0 XML
to reports/rss.xml and reports/feed.xml for syndication across Slack, Discord, Zapier,
Make.com, and RSS readers.
"""

import sys
import json
import html
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from hackingupdate.config import get_logger, WORKING_CACHE_FILE, REPORTS_DIR

import hackingupdate.config as config

logger = config.get_logger("rss_generator")


def generate_rss_xml(articles: list[dict], today_str: str) -> str:
    """Generate RSS 2.0 XML string from a list of article dictionaries."""
    now = datetime.now(timezone.utc)
    pub_date_formatted = format_datetime(now)

    items_xml = []
    for art in articles:
        title = html.escape(art.get("title", "Security Advisory"))
        link = html.escape(art.get("link", "#"))
        guid = link
        rank = art.get("rank", 5)
        source = html.escape(art.get("source", "Threat Intelligence"))
        tags = art.get("tags", [])
        tags_str = ", ".join(tags).upper() if tags else "GENERAL"

        # Determine severity label
        if rank >= 8:
            severity = "CRITICAL"
        elif rank >= 6:
            severity = "HIGH"
        elif rank >= 4:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Construct item description
        rank_reason = html.escape(art.get("rank_reason", ""))
        content_text = art.get("content_text", "")[:300]
        content_snippet = html.escape(content_text)

        description_html = (
            f"&lt;p&gt;&lt;strong&gt;Priority Rank:&lt;/strong&gt; {rank}/10 ({severity}) | "
            f"&lt;strong&gt;Category:&lt;/strong&gt; {tags_str} | "
            f"&lt;strong&gt;Source:&lt;/strong&gt; {source}&lt;/p&gt;"
            f"&lt;p&gt;{rank_reason}&lt;/p&gt;"
            f"&lt;p&gt;{content_snippet}...&lt;/p&gt;"
            f"&lt;p&gt;&lt;a href=&quot;{link}&quot;&gt;Read full advisory on {source}&amp;rarr;&lt;/a&gt;&lt;/p&gt;"
        )

        categories_xml = "\n".join([f"      <category>{html.escape(t)}</category>" for t in tags])

        item = f"""    <item>
      <title>[Rank {rank}/10 - {severity}] {title}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{guid}</guid>
      <pubDate>{pub_date_formatted}</pubDate>
{categories_xml}
      <description>{description_html}</description>
    </item>"""
        items_xml.append(item)

    items_joined = "\n".join(items_xml)

    rss_content = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>HackingUpdate — Daily Security Intelligence Digest</title>
    <link>https://github.com/4nilsj/hackingupdate</link>
    <description>Daily AI-curated vulnerability, zero-day, and threat intelligence feed for penetration testers and SecOps.</description>
    <language>en-us</language>
    <pubDate>{pub_date_formatted}</pubDate>
    <lastBuildDate>{pub_date_formatted}</lastBuildDate>
    <generator>HackingUpdate AI Engine v1.0.0</generator>
{items_joined}
  </channel>
</rss>
"""
    return rss_content


def main():
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Load working set
    if not config.WORKING_CACHE_FILE.exists():
        logger.warning(f"Working set not found: {config.WORKING_CACHE_FILE}. Skipping RSS generation.")
        return

    try:
        with open(config.WORKING_CACHE_FILE, "r", encoding="utf-8") as f:
            articles = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load working set: {e}")
        sys.exit(1)

    logger.info(f"Generating RSS 2.0 feed for {len(articles)} articles...")
    try:
        rss_xml = generate_rss_xml(articles, today_str)

        # Save to reports/rss.xml and reports/feed.xml
        rss_file = config.REPORTS_DIR / "rss.xml"
        feed_file = config.REPORTS_DIR / "feed.xml"

        with open(rss_file, "w", encoding="utf-8") as f:
            f.write(rss_xml)
        with open(feed_file, "w", encoding="utf-8") as f:
            f.write(rss_xml)

        logger.info(f"Successfully generated RSS feeds at: {rss_file} and {feed_file}")
    except Exception as e:
        logger.critical(f"Failed to generate RSS feed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
