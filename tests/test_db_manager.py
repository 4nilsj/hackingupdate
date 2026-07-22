"""Unit tests for SQLite database manager and duplicate prevention."""

import sqlite3
from pathlib import Path
from datetime import date

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
