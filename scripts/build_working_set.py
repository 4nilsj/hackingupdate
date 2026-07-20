import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

logger = config.get_logger("build_working_set")

def main():
    if not config.RANKED_CACHE_FILE.exists():
        logger.error(f"Ranked cache file not found: {config.RANKED_CACHE_FILE}")
        sys.exit(1)

    try:
        with open(config.RANKED_CACHE_FILE, "r", encoding="utf-8") as f:
            ranked_articles = json.load(f)
    except Exception as e:
        logger.critical(f"Failed to load ranked cache file: {e}")
        sys.exit(1)

    logger.info(f"Loaded {len(ranked_articles)} ranked articles.")

    # Load fingerprints for secondary semantic check
    try:
        with open(config.FINGERPRINT_CACHE_FILE, "r", encoding="utf-8") as f:
            fingerprints = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load fingerprints for secondary deduplication: {e}")
        fingerprints = {}

    import re
    cve_pattern = re.compile(r'\b(CVE-\d{4}-\d{4,})\b', re.IGNORECASE)
    
    def extract_cves(art):
        text = f"{art.get('title', '')} {art.get('description', '')} {art.get('content_text', '')}"
        return set(cve.upper() for cve in cve_pattern.findall(text))

    def jaccard_similarity(list1, list2):
        s1 = set(list1)
        s2 = set(list2)
        if not s1 or not s2:
            return 0.0
        return len(s1.intersection(s2)) / len(s1.union(s2))

    # Apply strict deduplication: subset CVE coverage and semantic check
    unique_ranked_articles = []
    seen_cves = set()

    for art in ranked_articles:
        art_id = art["id"]
        art_cves = extract_cves(art)
        
        # 1. CVE subset check: if all CVEs in this article are already covered, skip it
        if art_cves and art_cves.issubset(seen_cves):
            logger.info(f"Skipping duplicate CVE coverage: '{art['title']}' (CVEs: {list(art_cves)})")
            continue
            
        # 2. Semantic check: if the article keywords highly overlap with a kept article, skip it
        fp = fingerprints.get(art_id)
        if fp:
            is_semantic_dup = False
            for kept_art in unique_ranked_articles:
                kept_fp = fingerprints.get(kept_art["id"])
                if kept_fp:
                    sim = jaccard_similarity(fp["keywords"], kept_fp["keywords"])
                    if sim >= 0.50:
                        logger.info(f"Skipping semantic duplicate: '{art['title']}' vs '{kept_art['title']}' (Jaccard: {sim:.2f})")
                        is_semantic_dup = True
                        break
            if is_semantic_dup:
                continue

        unique_ranked_articles.append(art)
        if art_cves:
            seen_cves.update(art_cves)

    logger.info(f"Deduplication complete. Kept {len(unique_ranked_articles)} unique ranked articles.")

    # Select working set based on threshold: rank >= 5
    working_set = [art for art in unique_ranked_articles if art.get("rank", 0) >= 5]
    
    # If the working set is too small, fallback to top 8 articles regardless of rank
    if len(working_set) < 5 and len(unique_ranked_articles) > 0:
        logger.info(f"Only {len(working_set)} articles passed rank threshold. Falling back to top 8 articles.")
        working_set = unique_ranked_articles[:8]
        
    # Cap the working set to top 15 articles to ensure reports remain concise and high impact
    if len(working_set) > 15:
        logger.info(f"Truncating working set from {len(working_set)} to top 15 highest-ranked articles.")
        working_set = working_set[:15]

    logger.info(f"Selected {len(working_set)} articles for the working set.")

    try:
        with open(config.WORKING_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(working_set, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved working set to {config.WORKING_CACHE_FILE}")
    except Exception as e:
        logger.critical(f"Failed to save working set cache: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
