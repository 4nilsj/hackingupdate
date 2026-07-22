"""Unit tests for feed fetching module."""

from unittest.mock import patch, MagicMock
from scripts.fetcher import fetch_feed, _extract_articles_from_feed


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
