"""Unit tests for priority threat ranker."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests
import tenacity

from hackingupdate import config
from scripts import priority_ranker
from scripts.priority_ranker import (
    _call_openrouter_with_retry,
    fallback_rank_and_tag,
    rank_batch_with_llm,
)


@pytest.fixture(autouse=True)
def _no_real_sleep():
    """Tenacity's backoff and the inter-batch delay both call time.sleep — never
    actually wait for it in tests."""
    with patch("time.sleep"):
        yield


def _sample_article(article_id="1"):
    return {
        "id": article_id,
        "title": "SQL Injection in WordPress Plugin",
        "content_text": "Web vulnerability allows auth bypass.",
        "source": "WPFeed",
    }


def _mock_openrouter_response(rankings):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps({"rankings": rankings})}}]
    }
    return mock_resp


def test_call_openrouter_with_retry_success():
    mock_resp = _mock_openrouter_response([{"id": "1", "rank": 8, "tags": ["web"], "reason": "x"}])
    with patch("requests.post", return_value=mock_resp) as mock_post:
        content = _call_openrouter_with_retry({}, {})
    assert json.loads(content)["rankings"][0]["id"] == "1"
    mock_post.assert_called_once()


def test_call_openrouter_with_retry_raises_on_empty_choices():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"choices": []}
    with patch("requests.post", return_value=mock_resp) as mock_post, pytest.raises(ValueError):
        _call_openrouter_with_retry({}, {})
    # ValueError is not in the retryable exception set, so no retries happen.
    mock_post.assert_called_once()


def test_call_openrouter_with_retry_recovers_after_transient_failure():
    mock_success = _mock_openrouter_response([{"id": "1", "rank": 8, "tags": ["web"], "reason": "x"}])
    with patch(
        "requests.post",
        side_effect=[requests.exceptions.ConnectionError("timeout"), mock_success],
    ) as mock_post:
        content = _call_openrouter_with_retry({}, {})
    assert json.loads(content)["rankings"][0]["id"] == "1"
    assert mock_post.call_count == 2


def test_call_openrouter_with_retry_exhausts_all_attempts():
    # tenacity has no reraise=True set, so exhausting all attempts raises its
    # own RetryError (wrapping the ConnectionError) rather than the original.
    with (
        patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")) as mock_post,
        pytest.raises(tenacity.RetryError),
    ):
        _call_openrouter_with_retry({}, {})
    assert mock_post.call_count == 3


def test_rank_batch_with_llm_maps_results_by_id(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-fake-key")
    batch = [_sample_article("1"), _sample_article("2")]
    rankings = [
        {"id": "1", "rank": 9, "tags": ["web"], "reason": "Critical auth bypass"},
        {"id": "2", "rank": 3, "tags": ["news"], "reason": "Low impact"},
    ]
    with patch.object(priority_ranker, "_call_openrouter_with_retry", return_value=json.dumps({"rankings": rankings})):
        result = rank_batch_with_llm(batch)

    assert result[0] == {"id": "1", "rank": 9, "tags": ["web"], "reason": "Critical auth bypass"}
    assert result[1]["rank"] == 3


def test_rank_batch_with_llm_clamps_out_of_range_rank(monkeypatch):
    """A prompt-injected or hallucinated rank outside 1-10 must never be trusted as-is."""
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-fake-key")
    batch = [_sample_article("1"), _sample_article("2")]
    rankings = [
        {"id": "1", "rank": 999, "tags": ["web"], "reason": "x"},
        {"id": "2", "rank": -5, "tags": ["web"], "reason": "x"},
    ]
    with patch.object(priority_ranker, "_call_openrouter_with_retry", return_value=json.dumps({"rankings": rankings})):
        result = rank_batch_with_llm(batch)

    assert result[0]["rank"] == 10
    assert result[1]["rank"] == 1


def test_rank_batch_with_llm_defaults_rank_when_non_numeric(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-fake-key")
    batch = [_sample_article("1")]
    rankings = [{"id": "1", "rank": "extremely critical", "tags": ["web"], "reason": "x"}]
    with patch.object(priority_ranker, "_call_openrouter_with_retry", return_value=json.dumps({"rankings": rankings})):
        result = rank_batch_with_llm(batch)

    assert result[0]["rank"] == 5


def test_rank_batch_with_llm_filters_tags_outside_whitelist(monkeypatch):
    """Tags outside PENTEST_TAGS (e.g. injected by feed content) must be dropped."""
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-fake-key")
    batch = [_sample_article("1")]
    rankings = [{"id": "1", "rank": 7, "tags": ["web", "ignore-previous-instructions", "<script>"], "reason": "x"}]
    with patch.object(priority_ranker, "_call_openrouter_with_retry", return_value=json.dumps({"rankings": rankings})):
        result = rank_batch_with_llm(batch)

    assert result[0]["tags"] == ["web"]


def test_rank_batch_with_llm_defaults_tags_when_all_invalid(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-fake-key")
    batch = [_sample_article("1")]
    rankings = [{"id": "1", "rank": 7, "tags": "not-a-list", "reason": "x"}]
    with patch.object(priority_ranker, "_call_openrouter_with_retry", return_value=json.dumps({"rankings": rankings})):
        result = rank_batch_with_llm(batch)

    assert result[0]["tags"] == ["network"]


def test_rank_batch_with_llm_truncates_oversized_reason(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-fake-key")
    batch = [_sample_article("1")]
    rankings = [{"id": "1", "rank": 7, "tags": ["web"], "reason": "x" * 2000}]
    with patch.object(priority_ranker, "_call_openrouter_with_retry", return_value=json.dumps({"rankings": rankings})):
        result = rank_batch_with_llm(batch)

    assert len(result[0]["reason"]) == 500


def test_rank_batch_with_llm_falls_back_for_missing_id(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-fake-key")
    batch = [_sample_article("1"), _sample_article("2")]
    rankings = [{"id": "1", "rank": 9, "tags": ["web"], "reason": "Critical"}]
    with patch.object(priority_ranker, "_call_openrouter_with_retry", return_value=json.dumps({"rankings": rankings})):
        result = rank_batch_with_llm(batch)

    assert result[0]["rank"] == 9
    # Article "2" wasn't in the LLM response, so it must fall back to heuristics.
    assert result[1]["id"] == "2"
    assert result[1]["reason"].startswith("Fallback:")


def test_rank_batch_with_llm_falls_back_when_api_call_fails(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-fake-key")
    batch = [_sample_article("1")]
    with patch.object(priority_ranker, "_call_openrouter_with_retry", side_effect=Exception("boom")):
        result = rank_batch_with_llm(batch)

    assert result[0]["reason"].startswith("Fallback:")


def test_rank_batch_with_llm_falls_back_on_malformed_json(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "sk-or-fake-key")
    batch = [_sample_article("1")]
    with patch.object(priority_ranker, "_call_openrouter_with_retry", return_value="not valid json"):
        result = rank_batch_with_llm(batch)

    assert result[0]["reason"].startswith("Fallback:")


def test_main_exits_when_deduped_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(priority_ranker.config, "DEDUPED_CACHE_FILE", tmp_path / "missing.json")
    with pytest.raises(SystemExit) as exc_info:
        priority_ranker.main()
    assert exc_info.value.code == 1


def test_main_ranks_and_sorts_descending(tmp_path, monkeypatch):
    deduped_cache = tmp_path / "deduped.json"
    ranked_cache = tmp_path / "ranked.json"
    articles = [
        {"id": "1", "title": "General Security Policy Update", "content_text": "Company releases updated privacy policy.", "source": "NewsFeed"},
        {"id": "2", "title": "Critical Zero-day RCE Exploit Active", "content_text": "Unauthenticated remote code execution exploit active in the wild.", "source": "SecFeed"},
    ]
    deduped_cache.write_text(json.dumps(articles), encoding="utf-8")

    monkeypatch.setattr(priority_ranker.config, "DEDUPED_CACHE_FILE", deduped_cache)
    monkeypatch.setattr(priority_ranker.config, "RANKED_CACHE_FILE", ranked_cache)
    monkeypatch.setattr(priority_ranker.config, "OPENROUTER_API_KEY", "")

    priority_ranker.main()

    result = json.loads(ranked_cache.read_text(encoding="utf-8"))
    assert len(result) == 2
    assert result[0]["id"] == "2"  # higher rank sorted first
    assert result[0]["rank"] >= result[1]["rank"]


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
