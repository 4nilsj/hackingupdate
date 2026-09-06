"""Unit tests for CVE extraction and CISA KEV / EPSS threat intelligence enrichment."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts import cve_enrichment


def test_extract_cves():
    text = (
        "Advisory for CVE-2023-34362 in MOVEit Transfer and also cve-2021-44228 (Log4Shell). "
        "Ignore invalid like CVE-123 or CVE-2024-ABC. Duplicate CVE-2023-34362 should only appear once."
    )
    cves = cve_enrichment.extract_cves(text)
    assert cves == ["CVE-2021-44228", "CVE-2023-34362"]


def test_extract_cves_empty():
    assert cve_enrichment.extract_cves("") == []
    assert cve_enrichment.extract_cves("No vulnerabilities mentioned here.") == []


def test_fetch_cisa_kev_catalog_download(tmp_path, monkeypatch):
    cache_file = tmp_path / "cisa_kev.json"
    monkeypatch.setattr(cve_enrichment.config, "CISA_KEV_CACHE_FILE", cache_file)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "title": "CISA KEV",
        "vulnerabilities": [
            {
                "cveID": "CVE-2023-34362",
                "vendorProject": "Progress",
                "product": "MOVEit Transfer",
                "vulnerabilityName": "MOVEit SQL Injection",
                "dateAdded": "2023-06-02",
                "knownRansomwareCampaignUse": "Known",
            }
        ],
    }

    with patch("requests.get", return_value=mock_response):
        catalog = cve_enrichment.fetch_cisa_kev_catalog(force_refresh=True)

    assert "CVE-2023-34362" in catalog
    assert catalog["CVE-2023-34362"]["product"] == "MOVEit Transfer"
    assert catalog["CVE-2023-34362"]["known_ransomware_campaign_use"] == "Known"
    assert cache_file.exists()


def test_fetch_cisa_kev_catalog_cache_hit(tmp_path, monkeypatch):
    cache_file = tmp_path / "cisa_kev.json"
    cached_content = {
        "CVE-2021-44228": {
            "cve_id": "CVE-2021-44228",
            "product": "Log4j",
            "known_ransomware_campaign_use": "Known",
        }
    }
    cache_file.write_text(json.dumps(cached_content), encoding="utf-8")
    monkeypatch.setattr(cve_enrichment.config, "CISA_KEV_CACHE_FILE", cache_file)
    monkeypatch.setattr(cve_enrichment.config, "CISA_KEV_CACHE_TTL_HOURS", 24)

    # Should not make any network request because cache is fresh
    with patch("requests.get") as mock_get:
        catalog = cve_enrichment.fetch_cisa_kev_catalog(force_refresh=False)
        mock_get.assert_not_called()

    assert "CVE-2021-44228" in catalog
    assert catalog["CVE-2021-44228"]["product"] == "Log4j"


def test_fetch_cisa_kev_offline_fallback(tmp_path, monkeypatch):
    cache_file = tmp_path / "cisa_kev.json"
    cached_content = {
        "CVE-2020-0601": {
            "cve_id": "CVE-2020-0601",
            "product": "Windows CryptoAPI",
            "known_ransomware_campaign_use": "Unknown",
        }
    }
    cache_file.write_text(json.dumps(cached_content), encoding="utf-8")
    monkeypatch.setattr(cve_enrichment.config, "CISA_KEV_CACHE_FILE", cache_file)

    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Offline")):
        catalog = cve_enrichment.fetch_cisa_kev_catalog(force_refresh=True)

    assert "CVE-2020-0601" in catalog


def test_fetch_epss_scores_with_mock(tmp_path, monkeypatch):
    cache_file = tmp_path / "epss_cache.json"
    monkeypatch.setattr(cve_enrichment.config, "EPSS_CACHE_FILE", cache_file)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "OK",
        "data": [
            {
                "cve": "CVE-2023-34362",
                "epss": "0.9754",
                "percentile": "0.9998",
            }
        ],
    }

    with patch("requests.get", return_value=mock_response):
        scores = cve_enrichment.fetch_epss_scores(["CVE-2023-34362"])

    assert "CVE-2023-34362" in scores
    assert pytest.approx(scores["CVE-2023-34362"]["epss"], 0.001) == 0.9754
    assert pytest.approx(scores["CVE-2023-34362"]["percentile"], 0.001) == 0.9998
    assert cache_file.exists()


def test_enrich_articles():
    articles = [
        {
            "id": "art-1",
            "title": "Critical RCE Exploit in CVE-2023-34362 MOVEit",
            "description": "Active exploitation observed in the wild.",
            "content_text": "Attackers leverage CVE-2023-34362 to compromise systems.",
        },
        {
            "id": "art-2",
            "title": "General Security Report",
            "description": "No CVEs mentioned here.",
            "content_text": "Security hygiene best practices.",
        },
    ]

    mock_kev = {
        "CVE-2023-34362": {
            "cve_id": "CVE-2023-34362",
            "product": "MOVEit Transfer",
            "known_ransomware_campaign_use": "Known",
        }
    }
    mock_epss = {
        "CVE-2023-34362": {"epss": 0.95, "percentile": 0.99}
    }

    with patch.object(cve_enrichment, "fetch_cisa_kev_catalog", return_value=mock_kev), \
         patch.object(cve_enrichment, "fetch_epss_scores", return_value=mock_epss):
        enriched = cve_enrichment.enrich_articles(articles)

    assert len(enriched) == 2
    art1 = enriched[0]
    assert art1["cves"] == ["CVE-2023-34362"]
    assert art1["is_cisa_kev"] is True
    assert art1["cisa_ransomware"] is True
    assert art1["epss_score"] == 0.95

    art2 = enriched[1]
    assert art2["cves"] == []
    assert art2["is_cisa_kev"] is False
    assert art2["epss_score"] == 0.0
