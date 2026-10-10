"""Unit tests for content extraction and date freshness filtering."""

import json
from datetime import datetime, timedelta

import pytest

from scripts import extractor
from scripts.extractor import clean_html, is_article_fresh, parse_normalized_date


def test_parse_normalized_date_from_published_parsed():
    entry = {"published_parsed": [2026, 7, 20, 10, 30, 0, 0, 0, 0]}
    assert parse_normalized_date(entry) == "2026-07-20 10:30:00"


def test_parse_normalized_date_falls_back_to_published_string():
    entry = {"published": "Mon, 20 Jul 2026 10:30:00 +0000"}
    assert parse_normalized_date(entry) == "2026-07-20 10:30:00"


def test_parse_normalized_date_falls_back_to_updated_string():
    entry = {"updated": "2026-07-20"}
    assert parse_normalized_date(entry) == "2026-07-20 00:00:00"


def test_parse_normalized_date_returns_none_when_unparseable():
    entry = {"published": "not a real date"}
    assert parse_normalized_date(entry) is None


def test_parse_normalized_date_returns_none_when_missing():
    assert parse_normalized_date({}) is None


def _raw_article(**overrides):
    now = datetime.now()
    article = {
        "id": "1",
        "title": "Critical Apache Struts RCE",
        "link": "https://example.com/1",
        "feed_title": "Example Feed",
        "published_parsed": [now.year, now.month, now.day, now.hour, now.minute, now.second, 0, 0, 0],
        "summary": "A critical flaw was found.",
        "description": "",
        "content": [],
    }
    article.update(overrides)
    return article


def test_main_exits_when_raw_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(extractor.config, "RAW_CACHE_FILE", tmp_path / "missing.json")
    with pytest.raises(SystemExit) as exc_info:
        extractor.main()
    assert exc_info.value.code == 1


def _run_main_with(tmp_path, monkeypatch, raw_articles):
    raw_cache = tmp_path / "raw.json"
    full_cache = tmp_path / "full.json"
    raw_cache.write_text(json.dumps(raw_articles), encoding="utf-8")
    monkeypatch.setattr(extractor.config, "RAW_CACHE_FILE", raw_cache)
    monkeypatch.setattr(extractor.config, "FULL_CACHE_FILE", full_cache)
    extractor.main()
    return json.loads(full_cache.read_text(encoding="utf-8"))


def test_main_skips_articles_with_no_title(tmp_path, monkeypatch):
    result = _run_main_with(tmp_path, monkeypatch, [_raw_article(title="")])
    assert result == []


def test_main_skips_articles_with_unparseable_date(tmp_path, monkeypatch):
    article = _raw_article()
    del article["published_parsed"]
    result = _run_main_with(tmp_path, monkeypatch, [article])
    assert result == []


def test_main_skips_stale_articles(tmp_path, monkeypatch):
    old = datetime.now() - timedelta(days=10)
    article = _raw_article(
        published_parsed=[old.year, old.month, old.day, old.hour, old.minute, old.second, 0, 0, 0]
    )
    result = _run_main_with(tmp_path, monkeypatch, [article])
    assert result == []


def test_main_keeps_fresh_article_with_expected_fields(tmp_path, monkeypatch):
    result = _run_main_with(tmp_path, monkeypatch, [_raw_article()])
    assert len(result) == 1
    art = result[0]
    assert art["title"] == "Critical Apache Struts RCE"
    assert art["source"] == "Example Feed"
    assert "critical flaw" in art["content_text"].lower()


def test_main_falls_back_to_id_from_link_when_missing(tmp_path, monkeypatch):
    article = _raw_article()
    del article["id"]
    result = _run_main_with(tmp_path, monkeypatch, [article])
    assert result[0]["id"] == "https://example.com/1"


def test_main_truncates_excessively_long_content(tmp_path, monkeypatch):
    article = _raw_article(summary="x" * 7000)
    result = _run_main_with(tmp_path, monkeypatch, [article])
    assert "[Content Truncated]" in result[0]["content_text"]
    assert len(result[0]["content_text"]) < 6100


def test_clean_html():
    """Verify HTML tags and scripts are properly stripped."""
    raw_html = "<p>Hello <b>World</b><script>alert('xss')</script></p>"
    cleaned = clean_html(raw_html)
    assert "Hello World" in cleaned
    assert "script" not in cleaned


def test_is_article_fresh_today():
    """Verify today's date passes freshness filter."""
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assert is_article_fresh(today_str, max_age_days=1) is True


def test_is_article_fresh_old():
    """Verify an 8-day-old date fails freshness filter."""
    old_date = datetime.now() - timedelta(days=8)
    old_str = old_date.strftime("%Y-%m-%d %H:%M:%S")
    assert is_article_fresh(old_str, max_age_days=1) is False
