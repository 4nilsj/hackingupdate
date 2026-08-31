"""Unit tests for feed fetching module."""

from unittest.mock import MagicMock, patch

import requests

from scripts.fetcher import _extract_articles_from_feed, fetch_feed


def test_fetch_feed_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
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

    with patch("requests.get", return_value=mock_resp):
        url, feed = fetch_feed("https://example.com/rss.xml")
        assert url == "https://example.com/rss.xml"
        assert feed is not None
        assert len(feed.entries) == 1
        assert feed.entries[0].title == "Test Security Advisory"


def test_fetch_feed_ssl_error_never_retries_insecurely():
    """A TLS/cert failure must never be retried with verification disabled — it should
    fall through to the feedparser fallback instead of risking a MITM'd response."""
    with patch(
        "requests.get",
        side_effect=requests.exceptions.SSLError("cert verify failed"),
    ) as mock_get, patch("feedparser.parse", return_value=MagicMock(entries=[])) as mock_parse:
        fetch_feed("https://example.com/rss.xml")
        assert mock_get.call_count == 1
        for call in mock_get.call_args_list:
            assert call.kwargs.get("verify", True) is not False
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
        for call in mock_get.call_args_list:
            assert call.kwargs.get("verify", True) is not False


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
