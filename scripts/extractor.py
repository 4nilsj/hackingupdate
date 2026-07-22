import sys
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

from hackingupdate.config import (
    get_logger, RAW_CACHE_FILE, FULL_CACHE_FILE, ARTICLE_MAX_AGE_DAYS,
)

import hackingupdate.config as config

logger = config.get_logger("extractor")

def clean_html(html_content):
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator=" ")
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        logger.warning(f"Error cleaning HTML: {e}")
        return html_content

def parse_normalized_date(entry):
    # Try published_parsed first if present
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            # parsed is a list/tuple: (year, month, day, hour, minute, second, day of week, day of year, dst)
            dt = datetime(*parsed[:6])
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    # Fallback to string parsers
    for date_field in ["published", "updated"]:
        date_str = entry.get(date_field)
        if not date_str:
            continue
        # Strip common offset formats or try parsing
        for fmt in (
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
            
    # Default to None if missing or unparseable (will be filtered out)
    return None

# Maximum age of articles to include (in days) — configurable via ARTICLE_MAX_AGE_DAYS env var
MAX_ARTICLE_AGE_DAYS: int = ARTICLE_MAX_AGE_DAYS


def is_article_fresh(published_date_str, max_age_days=MAX_ARTICLE_AGE_DAYS):
    """Check if an article is fresh enough to include (today or yesterday)."""
    if not published_date_str:
        return False
    try:
        article_date = datetime.strptime(published_date_str, "%Y-%m-%d %H:%M:%S")
        cutoff = datetime.now() - timedelta(days=max_age_days)
        return article_date >= cutoff
    except (ValueError, TypeError):
        return False


def main():
    if not config.RAW_CACHE_FILE.exists():
        logger.error(f"Raw cache file not found: {config.RAW_CACHE_FILE}")
        sys.exit(1)

    try:
        with open(config.RAW_CACHE_FILE, "r", encoding="utf-8") as f:
            raw_articles = json.load(f)
    except Exception as e:
        logger.critical(f"Failed to load raw cache file: {e}")
        sys.exit(1)

    logger.info(f"Loaded {len(raw_articles)} raw articles for extraction.")
    extracted_articles = []
    skipped_old = 0
    skipped_no_date = 0

    for index, entry in enumerate(raw_articles):
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        feed_title = entry.get("feed_title", "").strip()
        
        if not title:
            logger.debug(f"Skipping article at index {index} with no title.")
            continue

        # Parse the date first to filter stale articles early
        normalized_date = parse_normalized_date(entry)

        if not normalized_date:
            logger.debug(f"Skipping article with unparseable date: {title}")
            skipped_no_date += 1
            continue

        if not is_article_fresh(normalized_date):
            logger.debug(f"Skipping stale article ({normalized_date}): {title}")
            skipped_old += 1
            continue

        # Combine description, summary, and content list for text cleaning
        raw_text_parts = []
        if entry.get("summary"):
            raw_text_parts.append(entry["summary"])
        if entry.get("description"):
            raw_text_parts.append(entry["description"])
        if entry.get("content"):
            raw_text_parts.extend(entry["content"])

        combined_raw_text = "\n".join(raw_text_parts)
        cleaned_body = clean_html(combined_raw_text)

        # Fallback to title if body is completely empty
        if not cleaned_body:
            cleaned_body = title

        # Truncate content text if it is excessively long to save token limit
        if len(cleaned_body) > 6000:
            cleaned_body = cleaned_body[:6000] + "... [Content Truncated]"

        extracted_articles.append({
            "id": entry.get("id") or link or title,
            "title": title,
            "link": link,
            "source": feed_title,
            "published_date": normalized_date,
            "content_text": cleaned_body
        })

    logger.info(f"Date filter: kept {len(extracted_articles)} fresh articles, "
                f"skipped {skipped_old} stale (>{MAX_ARTICLE_AGE_DAYS}d old), "
                f"{skipped_no_date} with no date")

    try:
        with open(config.FULL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(extracted_articles, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully extracted and saved {len(extracted_articles)} articles to {config.FULL_CACHE_FILE}")
    except Exception as e:
        logger.critical(f"Failed to save extracted articles: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
