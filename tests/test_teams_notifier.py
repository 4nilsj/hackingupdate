"""Unit tests for the Microsoft Teams webhook notifier."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts import teams_notifier


def test_parse_executive_summary_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.md"
    assert teams_notifier.parse_executive_summary(missing) == (
        "Daily intelligence report generated successfully."
    )


def test_parse_executive_summary_extracts_block(tmp_path):
    md_path = tmp_path / "brief.md"
    md_path.write_text(
        "# Daily Brief\n\n## Executive Summary\nCritical RCE found in Foo.\n\n## Findings\nMore text.\n",
        encoding="utf-8",
    )
    assert teams_notifier.parse_executive_summary(md_path) == "Critical RCE found in Foo."


def test_parse_executive_summary_no_match_returns_default(tmp_path):
    md_path = tmp_path / "brief.md"
    md_path.write_text("# Daily Brief\n\nNo summary heading here.\n", encoding="utf-8")
    assert teams_notifier.parse_executive_summary(md_path) == (
        "Daily intelligence report generated successfully."
    )


def _sample_working_set():
    return [
        {"title": "Critical RCE", "rank": 9, "source": "CISA", "link": "https://example.com/1", "tags": ["web"]},
        {"title": "Medium XSS", "rank": 5, "source": "PacketStorm", "link": "https://example.com/2", "tags": ["web"]},
    ]


def test_send_teams_notification_success_builds_expected_payload():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = teams_notifier.send_teams_notification(
            "https://webhook.example.com/x", "2026-08-30", "All quiet.", _sample_working_set()
        )

    assert result is True
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    payload = kwargs["json"]
    assert payload["title"] == "🛡️ Daily Security Intelligence Briefing - 2026-08-30"
    assert payload["sections"][0]["text"] == "All quiet."
    facts = payload["sections"][1]["facts"]
    assert len(facts) == 2
    assert "Critical RCE" in facts[0]["name"]


def test_send_teams_notification_caps_facts_at_five():
    working_set = [
        {"title": f"Finding {i}", "rank": 5, "source": "Src", "link": "#", "tags": []} for i in range(8)
    ]
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp) as mock_post:
        teams_notifier.send_teams_notification("https://webhook.example.com/x", "2026-08-30", "Summary", working_set)

    payload = mock_post.call_args.kwargs["json"]
    assert len(payload["sections"][1]["facts"]) == 5


def test_send_teams_notification_returns_false_on_error():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("boom")):
        result = teams_notifier.send_teams_notification(
            "https://webhook.example.com/x", "2026-08-30", "Summary", _sample_working_set()
        )
    assert result is False


def test_main_skips_when_webhook_not_configured(monkeypatch):
    monkeypatch.setattr(teams_notifier.config, "TEAMS_WEBHOOK_URL", "")
    with pytest.raises(SystemExit) as exc_info:
        teams_notifier.main()
    assert exc_info.value.code == 0


def test_main_exits_when_working_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(teams_notifier.config, "TEAMS_WEBHOOK_URL", "https://webhook.example.com/x")
    monkeypatch.setattr(teams_notifier.config, "WORKING_CACHE_FILE", tmp_path / "missing.json")
    with pytest.raises(SystemExit) as exc_info:
        teams_notifier.main()
    assert exc_info.value.code == 1


def test_main_happy_path_sends_notification(tmp_path, monkeypatch):
    working_cache = tmp_path / "articles_working.json"
    working_cache.write_text(json.dumps(_sample_working_set()), encoding="utf-8")

    monkeypatch.setattr(teams_notifier.config, "TEAMS_WEBHOOK_URL", "https://webhook.example.com/x")
    monkeypatch.setattr(teams_notifier.config, "WORKING_CACHE_FILE", working_cache)
    monkeypatch.setattr(teams_notifier.config, "REPORTS_DIR", tmp_path)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp) as mock_post:
        teams_notifier.main()

    mock_post.assert_called_once()
