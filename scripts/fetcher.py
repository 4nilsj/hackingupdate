import sys
import json
import requests
import feedparser
from pathlib import Path

# Add project root to sys.path so config can be imported
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

logger = config.get_logger("fetcher")

def fetch_feed(url):
    logger.info(f"Fetching feed: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # Some security feeds block default python user-agents, so we use requests with headers
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        # Parse XML content string
        feed = feedparser.parse(response.content)
        
        if feed.bozo:
            logger.warning(f"Feed parser reported potential issues (bozo bit set) for {url}: {feed.bozo_exception}")
            
        return feed
    except Exception as e:
        logger.error(f"Error fetching feed {url}: {e}")
        # Try direct feedparser as a fallback
        try:
            logger.info(f"Retrying {url} directly with feedparser...")
            feed = feedparser.parse(url)
            return feed
        except Exception as e_inner:
            logger.error(f"Fallback fetch also failed for {url}: {e_inner}")
            return None

def main():
    if not config.FEEDS_FILE.exists():
        logger.error(f"Feeds file not found: {config.FEEDS_FILE}")
        sys.exit(1)

    with open(config.FEEDS_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    if not urls:
        logger.warning("No URLs found in feeds file.")
        sys.exit(0)

    raw_articles = []
    
    for url in urls:
        feed = fetch_feed(url)
        if not feed or not feed.entries:
            logger.warning(f"No entries found for feed: {url}")
            continue

        feed_title = feed.feed.get("title", url)
        logger.info(f"Found {len(feed.entries)} entries in '{feed_title}'")
        
        for entry in feed.entries:
            # Construct a dictionary containing raw entry properties
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
            raw_articles.append(article_raw)

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
