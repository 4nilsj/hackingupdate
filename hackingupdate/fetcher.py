import sys
import json
import random
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed

import hackingupdate.config as config

logger = config.get_logger("fetcher")

# Maximum number of concurrent feed fetch workers
MAX_WORKERS: int = 8

# ---------------------------------------------------------------------------
# Realistic browser header profiles — rotated per-fetch to avoid 403 blocks.
# Sites like CISA, BleepingComputer, SecurityWeek, and Talos inspect
# User-Agent, Accept, Accept-Encoding, and Cache-Control to detect bots.
# ---------------------------------------------------------------------------
_BROWSER_PROFILES: list[dict] = [
    {
        # Chrome 128 on macOS
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        # Chrome 127 on Windows
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.6533.99 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        # Firefox 129 on Linux
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) "
            "Gecko/20100101 Firefox/129.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
    {
        # Safari 17 on macOS
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.5 Safari/605.1.15"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
]


def _pick_headers() -> dict:
    """Return a randomly selected browser header profile."""
    return dict(random.choice(_BROWSER_PROFILES))


def _pick_different_headers(used: dict) -> dict:
    """Return a different profile than the one already used."""
    ua_used = used.get("User-Agent", "")
    alternates = [p for p in _BROWSER_PROFILES if p.get("User-Agent") != ua_used]
    return dict(random.choice(alternates) if alternates else random.choice(_BROWSER_PROFILES))


def fetch_feed(url: str) -> tuple[str, "feedparser.FeedParserDict | None"]:
    """Fetch and parse a single RSS/Atom feed URL.

    Uses rotating browser header profiles to avoid bot-detection 403 blocks.
    On a 403 it retries once with a different profile before falling through
    to direct feedparser parsing.

    Returns:
        Tuple of (url, parsed_feed_or_None).
    """
    logger.info(f"Fetching feed: {url}")
    headers = _pick_headers()

    response = None
    try:
        response = requests.get(url, headers=headers, timeout=15)

        # On 403 — retry once with a different browser profile before giving up
        if response.status_code == 403:
            retry_headers = _pick_different_headers(headers)
            logger.warning(
                f"403 for {url} — retrying with alternate browser profile "
                f"({retry_headers.get('User-Agent', '')[:40]}...)"
            )
            response = requests.get(url, headers=retry_headers, timeout=15)

        response.raise_for_status()

    except requests.exceptions.SSLError as ssl_err:
        # Never retry with verification disabled — that would accept a MITM'd
        # response and feed attacker-controlled content into the ranker/report.
        # Fall straight through to the feedparser fallback below instead.
        logger.warning(f"SSL certificate verification failed for {url}: {ssl_err}")
        response = None
    except Exception as e:
        logger.warning(f"Initial HTTP fetch failed for {url}: {e}")
        response = None

    if response and response.status_code == 200:
        try:
            feed = feedparser.parse(response.content)
            if feed and feed.entries:
                return (url, feed)
        except Exception as parse_err:
            logger.warning(f"Failed to parse XML content for {url}: {parse_err}")

    # Fallback to direct feedparser parsing (uses its own User-Agent)
    try:
        logger.info(f"Retrying {url} directly with feedparser...")
        feed = feedparser.parse(url)
        return (url, feed)
    except Exception as e_inner:
        logger.error(f"Fallback fetch also failed for {url}: {e_inner}")
        return (url, None)


def _extract_articles_from_feed(url: str, feed) -> list[dict]:
    """Extract raw article dicts from a parsed feed."""
    if not feed or not feed.entries:
        return []

    feed_title = feed.feed.get("title", url)
    articles = []

    for entry in feed.entries:
        article_raw = {
            "feed_title": feed_title,
            "feed_url": url,
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "id": entry.get("id", entry.get("link", "")),
            # Storing multiple possible date fields
            "published": entry.get("published", ""),
            "published_parsed": list(entry.published_parsed) if entry.get("published_parsed") else None,
            "updated": entry.get("updated", ""),
            "updated_parsed": list(entry.updated_parsed) if entry.get("updated_parsed") else None,
            # Descriptions and content summaries
            "summary": entry.get("summary", ""),
            "description": entry.get("description", ""),
            "content": [c.get("value", "") for c in entry.get("content", [])] if entry.get("content") else []
        }
        articles.append(article_raw)

    return articles


def main():
    if not config.FEEDS_FILE.exists():
        logger.error(f"Feeds file not found: {config.FEEDS_FILE}")
        sys.exit(1)

    with open(config.FEEDS_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    if not urls:
        logger.warning("No URLs found in feeds file.")
        sys.exit(0)

    raw_articles: list[dict] = []
    successful_feeds = 0

    # Fetch all feeds concurrently for significant speedup
    logger.info(f"Fetching {len(urls)} feeds concurrently with {MAX_WORKERS} workers...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_feed, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                feed_url, feed = future.result()
                if not feed or not feed.entries:
                    logger.warning(f"No entries found for feed: {feed_url}")
                    continue

                successful_feeds += 1
                feed_title = feed.feed.get("title", feed_url)
                logger.info(f"Found {len(feed.entries)} entries in '{feed_title}'")
                articles = _extract_articles_from_feed(feed_url, feed)
                raw_articles.extend(articles)
            except Exception as e:
                logger.error(f"Unexpected error processing feed {url}: {e}")

    if successful_feeds == 0:
        logger.critical("No feeds returned entries; refusing to replace the raw cache with an empty result.")
        sys.exit(1)

    # Save raw articles to cache
    try:
        with open(config.RAW_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(raw_articles, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully fetched and cached {len(raw_articles)} raw articles to {config.RAW_CACHE_FILE}")
    except Exception as e:
        logger.critical(f"Failed to save raw cache file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

