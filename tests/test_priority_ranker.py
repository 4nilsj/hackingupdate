"""Unit tests for priority threat ranker."""

from scripts.priority_ranker import fallback_rank_and_tag, rank_batch_with_llm
from hackingupdate import config


def test_fallback_rank_and_tag_critical():
    sample_article = {
        "id": "1",
        "title": "Critical Zero-day RCE in Apache Web Server (CVE-2026-9999)",
        "content_text": "Unauthenticated remote code execution exploit active in the wild.",
        "source": "SecurityFeed"
    }

    result = fallback_rank_and_tag(sample_article)
    assert result["id"] == "1"
    assert result["rank"] >= 7
    assert "web" in result["tags"]


def test_fallback_rank_and_tag_low():
    sample_article = {
        "id": "2",
        "title": "General Security Policy Update Announcement",
        "content_text": "Company releases updated privacy policy guidelines for employees.",
        "source": "NewsFeed"
    }

    result = fallback_rank_and_tag(sample_article)
    assert result["rank"] <= 4


def test_rank_batch_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    sample_batch = [
        {
            "id": "1",
            "title": "SQL Injection in WordPress Plugin",
            "content_text": "Web vulnerability allows auth bypass.",
            "source": "WPFeed"
        }
    ]
    rankings = rank_batch_with_llm(sample_batch)
    assert len(rankings) == 1
    assert rankings[0]["id"] == "1"
    assert "web" in rankings[0]["tags"]
