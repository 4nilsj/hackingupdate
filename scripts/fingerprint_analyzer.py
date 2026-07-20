import sys
import json
import re
import hashlib
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

logger = config.get_logger("fingerprint_analyzer")

def normalize_text(text):
    # Lowercase and remove all non-alphanumeric characters
    text = text.lower()
    return re.sub(r'[^a-z0-9]', '', text)

def get_keywords(text, num_keywords=25):
    # Lowercase and split into words
    words = re.findall(r'\b[a-z]{5,15}\b', text.lower())
    
    # Filter out common stop words
    stop_words = {
        "about", "above", "after", "again", "against", "along", "already", "would",
        "could", "should", "there", "their", "these", "those", "under", "which",
        "while", "would", "other", "where", "which", "whose", "through", "between",
        "vulnerability", "security", "exploit", "cve-202" # Generic security terms
    }
    filtered_words = [w for w in words if w not in stop_words]
    
    # Calculate word frequencies
    freq = {}
    for w in filtered_words:
        freq[w] = freq.get(w, 0) + 1
        
    # Sort by frequency, then alphabetically
    sorted_keywords = sorted(freq.keys(), key=lambda w: (-freq[w], w))
    return sorted_keywords[:num_keywords]

def main():
    if not config.FULL_CACHE_FILE.exists():
        logger.error(f"Full cache file not found: {config.FULL_CACHE_FILE}")
        sys.exit(1)

    try:
        with open(config.FULL_CACHE_FILE, "r", encoding="utf-8") as f:
            articles = json.load(f)
    except Exception as e:
        logger.critical(f"Failed to load full cache file: {e}")
        sys.exit(1)

    logger.info(f"Generating fingerprints for {len(articles)} articles.")
    fingerprints = {}

    for article in articles:
        art_id = article["id"]
        title = article["title"]
        content = article["content_text"]
        
        # Calculate Title Hash (exact match detector)
        norm_title = normalize_text(title)
        title_hash = hashlib.md5(norm_title.encode('utf-8')).hexdigest() if norm_title else ""
        
        # Calculate Content keywords (semantic near-duplicate detector)
        combined_text = f"{title} {content}"
        keywords = get_keywords(combined_text)
        
        fingerprints[art_id] = {
            "title_hash": title_hash,
            "keywords": keywords,
            "link": article["link"]
        }

    try:
        with open(config.FINGERPRINT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(fingerprints, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully generated and saved fingerprints to {config.FINGERPRINT_CACHE_FILE}")
    except Exception as e:
        logger.critical(f"Failed to save fingerprints: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
