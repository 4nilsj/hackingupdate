"""Unit tests for feed fetching module."""

from unittest.mock import MagicMock, patch, call

import pytest
import requests

from scripts.fetcher import _extract_articles_from_feed, fetch_feed, _pick_headers, _pick_different_headers, _BROWSER_PROFILES
from scripts import fetcher


def _make_rss_response(status_code=200):
    """Build a minimal mock HTTP response with valid RSS content."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status.return_value = None
    if status_code == 403:
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("403")
    mock_resp.content = b"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>Test Security Advisory</title>
          <link>https://example.com/advisory-1</link>
          <description>Critical vulnerability fixed</description>
        </item>
      </channel>
    </rss>"""
    return mock_resp


def test_fetch_feed_success():
    mock_resp = _make_rss_response(200)

    with patch("requests.get", return_value=mock_resp):
        url, feed = fetch_feed("https://example.com/rss.xml")
        assert url == "https://example.com/rss.xml"
        assert feed is not None
        assert len(feed.entries) == 1
        assert feed.entries[0].title == "Test Security Advisory"


def test_fetch_feed_retries_on_403_with_different_profile():
    """A 403 on first attempt triggers exactly one retry with a DIFFERENT User-Agent profile."""
    first_403 = _make_rss_response(403)
    second_200 = _make_rss_response(200)
    second_200.raise_for_status.return_value = None

    with patch("requests.get", side_effect=[first_403, second_200]) as mock_get:
        url, feed = fetch_feed("https://example.com/rss.xml")

    assert mock_get.call_count == 2
    # The two calls must have used different User-Agent strings
    ua_first = mock_get.call_args_list[0].kwargs.get("headers", {}).get("User-Agent", "")
    ua_second = mock_get.call_args_list[1].kwargs.get("headers", {}).get("User-Agent", "")
    assert ua_first != ua_second, "Retry must use a different User-Agent than the first attempt"


def test_fetch_feed_403_falls_back_to_feedparser_when_retry_also_fails():
    """If both attempts return 403, fall through to feedparser fallback."""
    four_oh_three = _make_rss_response(403)

    with patch("requests.get", return_value=four_oh_three), \
         patch("feedparser.parse", return_value=MagicMock(entries=[])) as mock_parse:
        fetch_feed("https://example.com/rss.xml")

    mock_parse.assert_called_once_with("https://example.com/rss.xml")


def test_fetch_feed_ssl_error_never_retries_insecurely():
    """A TLS/cert failure must never be retried with verification disabled — it should
    fall through to the feedparser fallback instead of risking a MITM'd response."""
    with patch(
        "requests.get",
        side_effect=requests.exceptions.SSLError("cert verify failed"),
    ) as mock_get, patch("feedparser.parse", return_value=MagicMock(entries=[])) as mock_parse:
        fetch_feed("https://example.com/rss.xml")
        assert mock_get.call_count == 1
        for c in mock_get.call_args_list:
            assert c.kwargs.get("verify", True) is not False
        # falls back to feedparser parsing the URL directly
        mock_parse.assert_called_once_with("https://example.com/rss.xml")


def test_fetch_feed_non_ssl_error_does_not_retry_insecurely():
    """Non-TLS failures (timeouts, connection errors, etc.) must never trigger a verify=False retry."""
    with patch(
        "requests.get",
        side_effect=requests.exceptions.ConnectionError("connection refused"),
    ) as mock_get, patch("feedparser.parse", return_value=MagicMock(entries=[])):
        fetch_feed("https://example.com/rss.xml")
        assert mock_get.call_count == 1
        for c in mock_get.call_args_list:
            assert c.kwargs.get("verify", True) is not False


def test_pick_headers_returns_valid_profile():
    """_pick_headers must always return a dict with at least User-Agent and Accept."""
    headers = _pick_headers()
    assert isinstance(headers, dict)
    assert "User-Agent" in headers
    assert "Accept" in headers


def test_pick_different_headers_returns_alternate_ua():
    """_pick_different_headers must return a profile with a different User-Agent."""
    original = _pick_headers()
    alternate = _pick_different_headers(original)
    # With 4 profiles there is always at least one alternative
    assert alternate.get("User-Agent") != original.get("User-Agent")


def test_browser_profiles_all_have_required_fields():
    """Every profile in _BROWSER_PROFILES must have User-Agent, Accept, Accept-Language, Accept-Encoding."""
    required = {"User-Agent", "Accept", "Accept-Language", "Accept-Encoding"}
    for profile in _BROWSER_PROFILES:
        missing = required - set(profile.keys())
        assert not missing, f"Profile missing fields: {missing} in {profile.get('User-Agent')}"


def test_extract_articles_from_feed():
    mock_feed = MagicMock()
    mock_feed.feed.get.return_value = "Test Source"
    mock_entry = {
        "title": "Advisory Title",
        "link": "https://example.com/1",
        "id": "1",
        "published": "2026-07-22",
        "summary": "Summary text",
        "description": "Desc text",
        "content": [{"value": "Full content"}]
    }
    mock_feed.entries = [mock_entry]

    articles = _extract_articles_from_feed("https://example.com/feed", mock_feed)
    assert len(articles) == 1
    assert articles[0]["title"] == "Advisory Title"
    assert articles[0]["feed_title"] == "Test Source"
    assert articles[0]["link"] == "https://example.com/1"


def test_main_fails_when_no_feed_returns_entries(tmp_path, monkeypatch):
    feeds_file = tmp_path / "feeds.txt"
    feeds_file.write_text("https://example.com/rss.xml\n", encoding="utf-8")
    monkeypatch.setattr(fetcher.config, "FEEDS_FILE", feeds_file)
    monkeypatch.setattr(fetcher.config, "RAW_CACHE_FILE", tmp_path / "articles_raw.json")

    empty_feed = MagicMock(entries=[])
    with patch.object(fetcher, "fetch_feed", return_value=("https://example.com/rss.xml", empty_feed)):
        with pytest.raises(SystemExit) as exc_info:
            fetcher.main()

    assert exc_info.value.code == 1
    assert not (tmp_path / "articles_raw.json").exists()
