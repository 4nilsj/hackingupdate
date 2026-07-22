import sys
import json
import requests
import feedparser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from hackingupdate.config import (
    get_logger, FEEDS_FILE, RAW_CACHE_FILE,
)

import hackingupdate.config as config

logger = config.get_logger("fetcher")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Maximum number of concurrent feed fetch workers
MAX_WORKERS: int = 8


def fetch_feed(url: str) -> tuple[str, "feedparser.FeedParserDict | None"]:
    """Fetch and parse a single RSS/Atom feed URL.

    Returns:
        Tuple of (url, parsed_feed_or_None).
    """
    logger.info(f"Fetching feed: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    response = None
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.SSLError as ssl_err:
        logger.warning(f"SSL certificate verification failed for {url}, retrying without SSL verification...")
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
        except Exception as e_unverified:
            logger.error(f"Unverified SSL fetch failed for {url}: {e_unverified}")
    except Exception as e:
        logger.warning(f"Initial HTTP fetch failed for {url}: {e}")
        # Try with verify=False if it was a connection or cert error
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            if response.status_code == 200:
                logger.info(f"Unverified SSL fetch succeeded for {url}")
        except Exception:
            pass

    if response and response.status_code == 200:
        try:
            feed = feedparser.parse(response.content)
            if feed and feed.entries:
                return (url, feed)
        except Exception as parse_err:
            logger.warning(f"Failed to parse XML content for {url}: {parse_err}")

    # Fallback to direct feedparser parsing
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

                feed_title = feed.feed.get("title", feed_url)
                logger.info(f"Found {len(feed.entries)} entries in '{feed_title}'")
                articles = _extract_articles_from_feed(feed_url, feed)
                raw_articles.extend(articles)
            except Exception as e:
                logger.error(f"Unexpected error processing feed {url}: {e}")

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

