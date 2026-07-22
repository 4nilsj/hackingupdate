import sys
import json
from pathlib import Path

from hackingupdate.config import (
    get_logger, FULL_CACHE_FILE, FINGERPRINT_CACHE_FILE, DEDUPED_CACHE_FILE,
)

import hackingupdate.config as config

logger = config.get_logger("dedupe_fingerprints")

def jaccard_similarity(list1, list2):
    s1 = set(list1)
    s2 = set(list2)
    if not s1 or not s2:
        return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))

def main():
    if not config.FULL_CACHE_FILE.exists():
        logger.error(f"Full cache file not found: {config.FULL_CACHE_FILE}")
        sys.exit(1)
    if not config.FINGERPRINT_CACHE_FILE.exists():
        logger.error(f"Fingerprint cache file not found: {config.FINGERPRINT_CACHE_FILE}")
        sys.exit(1)

    try:
        with open(config.FULL_CACHE_FILE, "r", encoding="utf-8") as f:
            articles = json.load(f)
        with open(config.FINGERPRINT_CACHE_FILE, "r", encoding="utf-8") as f:
            fingerprints = json.load(f)
    except Exception as e:
        logger.critical(f"Failed to load cache files: {e}")
        sys.exit(1)

    logger.info(f"Loaded {len(articles)} articles and {len(fingerprints)} fingerprints for deduplication.")
    
    unique_articles = []
    seen_title_hashes = set()
    processed_fingerprints = []  # List of dicts: {"id": art_id, "title_hash": ..., "keywords": ...}

    duplicate_count = 0

    for article in articles:
        art_id = article["id"]
        fp = fingerprints.get(art_id)
        
        if not fp:
            # If no fingerprint found, keep the article by default
            unique_articles.append(article)
            continue

        title_hash = fp["title_hash"]
        keywords = fp["keywords"]
        
        # Check exact title match
        if title_hash and title_hash in seen_title_hashes:
            logger.debug(f"Discarding exact duplicate title: {article['title']}")
            duplicate_count += 1
            continue

        # Check semantic/keyword overlap with previously kept articles
        is_duplicate = False
        for seen_fp in processed_fingerprints:
            # If they share the exact title hash or have high keyword similarity
            sim = jaccard_similarity(keywords, seen_fp["keywords"])
            # Threshold of 0.60 Jaccard similarity is standard for near-duplicates
            if sim >= 0.60:
                logger.debug(f"Discarding near-duplicate (Jaccard Sim: {sim:.2f}): '{article['title']}' vs '{seen_fp['title']}'")
                is_duplicate = True
                duplicate_count += 1
                break
        
        if not is_duplicate:
            unique_articles.append(article)
            if title_hash:
                seen_title_hashes.add(title_hash)
            processed_fingerprints.append({
                "id": art_id,
                "title": article["title"],
                "title_hash": title_hash,
                "keywords": keywords
            })

    logger.info(f"Deduplication complete. Kept {len(unique_articles)} articles, discarded {duplicate_count} duplicates.")

    try:
        with open(config.DEDUPED_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(unique_articles, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved deduplicated articles to {config.DEDUPED_CACHE_FILE}")
    except Exception as e:
        logger.critical(f"Failed to save deduplicated articles: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
