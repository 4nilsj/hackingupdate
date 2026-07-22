"""Unit tests for content extraction and date freshness filtering."""

from datetime import datetime, timedelta

from scripts.extractor import clean_html, is_article_fresh


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
