"""Unit tests for SQLite database manager and duplicate prevention."""

from datetime import date

import pytest

from scripts import db_manager


def test_db_init_and_store(tmp_path, monkeypatch):
    """Test storing findings and verifying duplicate prevention."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db_manager, "DB_PATH", test_db)

    db_manager.init_db()
    assert test_db.exists()

    sample_articles = [
        {
            "id": "1",
            "title": "Test Vulnerability Flaw",
            "link": "https://example.com/test-1",
            "source": "TestSource",
            "published_date": "2026-07-21 10:00:00",
            "rank": 9,
            "tags": ["web"],
            "rank_reason": "High impact",
            "content_text": "Test content",
        }
    ]

    # First store: 1 inserted
    res1 = db_manager.store_findings(sample_articles, briefing_date=date.today())
    assert res1["stored"] == 1
    assert res1["skipped_duplicate"] == 0

    # Second store of same item: 0 inserted, 1 skipped duplicate
    res2 = db_manager.store_findings(sample_articles, briefing_date=date.today())
    assert res2["stored"] == 0
    assert res2["skipped_duplicate"] == 1


def test_store_and_query_cisa_kev_and_epss(tmp_path, monkeypatch):
    """Test storing findings with CISA KEV and EPSS threat intelligence fields."""
    test_db = tmp_path / "test_intel.db"
    monkeypatch.setattr(db_manager, "DB_PATH", test_db)

    db_manager.init_db()

    articles = [
        {
            "id": "1",
            "title": "Critical KEV Vulnerability",
            "link": "https://example.com/kev-vuln",
            "source": "CISA",
            "rank": 9,
            "tags": ["infra"],
            "cves": ["CVE-2023-34362"],
            "is_cisa_kev": True,
            "cisa_ransomware": True,
            "epss_score": 0.942,
        },
        {
            "id": "2",
            "title": "Standard Flaw",
            "link": "https://example.com/standard-flaw",
            "source": "BleepingComputer",
            "rank": 6,
            "tags": ["web"],
            "cves": ["CVE-2024-1111"],
            "is_cisa_kev": False,
            "cisa_ransomware": False,
            "epss_score": 0.05,
        }
    ]

    res = db_manager.store_findings(articles, briefing_date=date.today())
    assert res["stored"] == 2

    # Query findings
    findings = db_manager.get_findings_by_date(date.today())
    assert len(findings) == 2
    kev_finding = next(f for f in findings if f["link"] == "https://example.com/kev-vuln")
    assert kev_finding["is_cisa_kev"] == 1
    assert kev_finding["cisa_ransomware"] == 1
    assert pytest.approx(kev_finding["epss_score"], 0.001) == 0.942

    # Verify stats
    stats = db_manager.get_stats()
    assert stats["total_findings"] == 2
    assert stats["total_cisa_kev"] == 1
    assert stats["total_ransomware"] == 1
    assert pytest.approx(stats["max_epss"], 0.001) == 0.942


def test_get_recent_finding_identifiers(tmp_path, monkeypatch):
    """Test retrieving historical links and titles for cross-day deduplication."""
    test_db = tmp_path / "test_history.db"
    monkeypatch.setattr(db_manager, "DB_PATH", test_db)

    db_manager.init_db()

    from datetime import timedelta
    yesterday = date.today() - timedelta(days=1)
    past_articles = [
        {
            "id": "1",
            "title": "Yesterday Breach Announcement",
            "link": "https://example.com/yesterday-breach",
            "rank": 7,
        }
    ]
    db_manager.store_findings(past_articles, briefing_date=yesterday)

    # Query with exclude_date=today
    links, titles = db_manager.get_recent_finding_identifiers(days=7, exclude_date=date.today())
    assert "https://example.com/yesterday-breach" in links
    assert "yesterday breach announcement" in titles

    # Query with days=0 returns empty
    empty_links, _ = db_manager.get_recent_finding_identifiers(days=0)
    assert len(empty_links) == 0
