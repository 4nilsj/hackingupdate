"""
Threat Intelligence Enrichment module for HackingUpdate.

Extracts CVE identifiers and enriches findings with:
  1. CISA KEV (Known Exploited Vulnerabilities) catalog lookup (actively exploited in wild)
  2. FIRST.org EPSS (Exploit Prediction Scoring System) probability & percentile
"""

import json
import re
import time
import requests

from hackingupdate import config

logger = config.get_logger("cve_enrichment")

CVE_REGEX = re.compile(r"\b(CVE-\d{4}-\d{4,7})\b", re.IGNORECASE)


def extract_cves(text: str) -> list[str]:
    """Extract sorted, unique CVE identifiers from arbitrary text."""
    if not text:
        return []
    matches = CVE_REGEX.findall(text)
    return sorted({cve.upper() for cve in matches})


def fetch_cisa_kev_catalog(force_refresh: bool = False) -> dict[str, dict]:
    """
    Fetch the CISA Known Exploited Vulnerabilities catalog.
    Uses local cache if refreshed within CISA_KEV_CACHE_TTL_HOURS.
    Falls back gracefully to existing cache or empty dict on network failure.

    Returns:
        dict mapping CVE ID (e.g. 'CVE-2023-34362') to vulnerability metadata.
    """
    cache_file = config.CISA_KEV_CACHE_FILE
    now = time.time()
    ttl_seconds = config.CISA_KEV_CACHE_TTL_HOURS * 3600

    # 1. Check if cache exists and is fresh
    if not force_refresh and cache_file.exists():
        try:
            mtime = cache_file.stat().st_mtime
            if (now - mtime) < ttl_seconds:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    if isinstance(cached_data, dict):
                        logger.debug(f"Loaded {len(cached_data)} CISA KEV entries from cache: {cache_file}")
                        return cached_data
        except Exception as e:
            logger.warning(f"Error reading CISA KEV cache: {e}. Will attempt fresh download.")

    # 2. Attempt download from CISA
    logger.info(f"Downloading CISA KEV catalog from {config.CISA_KEV_URL}...")
    headers = {
        "User-Agent": "HackingUpdate-ThreatIntel/1.0",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(config.CISA_KEV_URL, headers=headers, timeout=20)
        resp.raise_for_status()
        catalog_raw = resp.json()

        vulnerabilities = catalog_raw.get("vulnerabilities", [])
        kev_dict = {}
        for item in vulnerabilities:
            cve_id = item.get("cveID", "").strip().upper()
            if cve_id:
                kev_dict[cve_id] = {
                    "cve_id": cve_id,
                    "vendor_project": item.get("vendorProject", ""),
                    "product": item.get("product", ""),
                    "vulnerability_name": item.get("vulnerabilityName", ""),
                    "date_added": item.get("dateAdded", ""),
                    "short_description": item.get("shortDescription", ""),
                    "required_action": item.get("requiredAction", ""),
                    "due_date": item.get("dueDate", ""),
                    "known_ransomware_campaign_use": item.get("knownRansomwareCampaignUse", ""),
                    "notes": item.get("notes", ""),
                }

        # Cache to disk
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(kev_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Successfully downloaded and cached {len(kev_dict)} CISA KEV entries to {cache_file}")
        return kev_dict

    except Exception as e:
        logger.warning(f"Failed to download fresh CISA KEV catalog: {e}")
        # Fallback to existing cache if available (even if expired)
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    fallback_data = json.load(f)
                    logger.info(f"Using existing cached CISA KEV catalog ({len(fallback_data)} entries) as fallback.")
                    return fallback_data
            except Exception as e_cache:
                logger.error(f"Failed to read fallback CISA KEV cache: {e_cache}")
        return {}


def fetch_epss_scores(cves: list[str]) -> dict[str, dict]:
    """
    Fetch EPSS scores and percentiles for a list of CVEs from FIRST.org.
    Caches results locally to avoid redundant API hits.

    Returns:
        dict mapping CVE ID -> {"epss": float, "percentile": float}
    """
    if not cves:
        return {}

    # Load persistent/transient EPSS cache
    epss_cache: dict[str, dict] = {}
    cache_file = config.EPSS_CACHE_FILE
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                epss_cache = json.load(f)
        except Exception:
            epss_cache = {}

    # Identify uncached CVEs
    needed_cves = [cve for cve in cves if cve not in epss_cache]
    if not needed_cves:
        return {cve: epss_cache[cve] for cve in cves if cve in epss_cache}

    # Query in batches of 50 (FIRST.org limit safe)
    batch_size = 50
    headers = {
        "User-Agent": "HackingUpdate-ThreatIntel/1.0",
        "Accept": "application/json",
    }

    for i in range(0, len(needed_cves), batch_size):
        batch = needed_cves[i:i + batch_size]
        cve_query = ",".join(batch)
        try:
            resp = requests.get(
                config.EPSS_API_URL,
                params={"cve": cve_query},
                headers=headers,
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    item_cve = item.get("cve", "").upper()
                    try:
                        epss_score = float(item.get("epss", 0.0))
                    except (ValueError, TypeError):
                        epss_score = 0.0
                    try:
                        percentile = float(item.get("percentile", 0.0))
                    except (ValueError, TypeError):
                        percentile = 0.0

                    epss_cache[item_cve] = {
                        "epss": epss_score,
                        "percentile": percentile,
                    }
        except Exception as e:
            logger.warning(f"Error fetching EPSS scores for batch ({len(batch)} CVEs): {e}")

    # Persist updated cache
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(epss_cache, f, indent=2)
    except Exception as e:
        logger.debug(f"Could not persist EPSS cache: {e}")

    return {cve: epss_cache[cve] for cve in cves if cve in epss_cache}


def enrich_articles(articles: list[dict]) -> list[dict]:
    """
    Enrich a list of articles with CISA KEV and EPSS threat intelligence metadata.

    Modifies each article in-place or returns a new enriched list with:
      - 'cves': list[str]
      - 'cisa_kev': {'is_kev': bool, 'ransomware': bool, 'hits': list[dict]}
      - 'epss': {'max_score': float, 'max_percentile': float, 'details': dict}
    """
    # 1. Extract CVEs for all articles
    article_cves_map: dict[str, list[str]] = {}
    all_unique_cves: set[str] = set()

    for art in articles:
        art_id = art.get("id", "")
        text = f"{art.get('title', '')} {art.get('description', '')} {art.get('summary', '')} {art.get('content_text', '')}"
        cves = extract_cves(text)
        article_cves_map[art_id] = cves
        all_unique_cves.update(cves)

    logger.info(f"CVE Enrichment: identified {len(all_unique_cves)} unique CVEs across {len(articles)} articles.")

    # 2. Lookup CISA KEV catalog
    kev_catalog = fetch_cisa_kev_catalog()

    # 3. Lookup EPSS scores
    epss_scores = fetch_epss_scores(list(all_unique_cves)) if all_unique_cves else {}

    # 4. Attach enrichment data to each article
    enriched_articles = []
    kev_match_count = 0
    ransomware_count = 0

    for art in articles:
        art_id = art.get("id", "")
        art_cves = article_cves_map.get(art_id, [])

        kev_hits = [kev_catalog[cve] for cve in art_cves if cve in kev_catalog]
        is_kev = len(kev_hits) > 0
        ransomware = any(
            h.get("known_ransomware_campaign_use", "").lower() == "known"
            for h in kev_hits
        )

        if is_kev:
            kev_match_count += 1
        if ransomware:
            ransomware_count += 1

        cve_epss_items = [epss_scores[cve] for cve in art_cves if cve in epss_scores]
        max_epss = max([item["epss"] for item in cve_epss_items], default=0.0)
        max_percentile = max([item["percentile"] for item in cve_epss_items], default=0.0)

        art_copy = dict(art)
        art_copy["cves"] = art_cves
        art_copy["is_cisa_kev"] = is_kev
        art_copy["cisa_ransomware"] = ransomware
        art_copy["cisa_kev"] = {
            "is_kev": is_kev,
            "ransomware": ransomware,
            "hits": kev_hits,
        }
        art_copy["epss_score"] = max_epss
        art_copy["epss"] = {
            "max_score": max_epss,
            "max_percentile": max_percentile,
            "details": {c: epss_scores[c] for c in art_cves if c in epss_scores}
        }
        enriched_articles.append(art_copy)

    logger.info(
        f"CVE Enrichment complete: {kev_match_count} article(s) matched CISA KEV "
        f"({ransomware_count} ransomware-associated)."
    )
    return enriched_articles
