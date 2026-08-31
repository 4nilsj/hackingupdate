"""Unit tests for the WhatsApp (Twilio + generic gateway) notifier."""

import json
from unittest.mock import MagicMock, patch

import requests

from scripts import whatsapp_notifier


def test_parse_executive_summary_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.md"
    assert whatsapp_notifier.parse_executive_summary(missing) == (
        "Daily security briefing generated successfully."
    )


def test_parse_executive_summary_extracts_block(tmp_path):
    md_path = tmp_path / "brief.md"
    md_path.write_text(
        "## Executive Summary\nA critical flaw was patched.\n\n## Findings\nMore text.\n",
        encoding="utf-8",
    )
    assert whatsapp_notifier.parse_executive_summary(md_path) == "A critical flaw was patched."


def test_load_working_set_prefers_working_cache(tmp_path, monkeypatch):
    working = tmp_path / "working.json"
    ranked = tmp_path / "ranked.json"
    working.write_text(json.dumps([{"title": "From working cache"}]), encoding="utf-8")
    ranked.write_text(json.dumps([{"title": "From ranked cache"}]), encoding="utf-8")

    monkeypatch.setattr(whatsapp_notifier.config, "WORKING_CACHE_FILE", working)
    monkeypatch.setattr(whatsapp_notifier.config, "RANKED_CACHE_FILE", ranked)

    result = whatsapp_notifier.load_working_set_with_fallback("2026-08-30")
    assert result == [{"title": "From working cache"}]


def test_load_working_set_falls_back_to_ranked_cache(tmp_path, monkeypatch):
    working = tmp_path / "working.json"  # does not exist
    ranked = tmp_path / "ranked.json"
    ranked.write_text(json.dumps([{"title": "From ranked cache"}]), encoding="utf-8")

    monkeypatch.setattr(whatsapp_notifier.config, "WORKING_CACHE_FILE", working)
    monkeypatch.setattr(whatsapp_notifier.config, "RANKED_CACHE_FILE", ranked)

    result = whatsapp_notifier.load_working_set_with_fallback("2026-08-30")
    assert result == [{"title": "From ranked cache"}]


def test_load_working_set_falls_back_to_db(tmp_path, monkeypatch):
    monkeypatch.setattr(whatsapp_notifier.config, "WORKING_CACHE_FILE", tmp_path / "missing1.json")
    monkeypatch.setattr(whatsapp_notifier.config, "RANKED_CACHE_FILE", tmp_path / "missing2.json")

    fake_db_manager = MagicMock()
    fake_db_manager.get_findings_by_date.return_value = [{"title": "From DB"}]
    with patch.dict("sys.modules", {"scripts.db_manager": fake_db_manager}):
        result = whatsapp_notifier.load_working_set_with_fallback("2026-08-30")

    assert result == [{"title": "From DB"}]


def test_load_working_set_returns_empty_when_nothing_available(tmp_path, monkeypatch):
    monkeypatch.setattr(whatsapp_notifier.config, "WORKING_CACHE_FILE", tmp_path / "missing1.json")
    monkeypatch.setattr(whatsapp_notifier.config, "RANKED_CACHE_FILE", tmp_path / "missing2.json")

    fake_db_manager = MagicMock()
    fake_db_manager.get_findings_by_date.return_value = []
    with patch.dict("sys.modules", {"scripts.db_manager": fake_db_manager}):
        result = whatsapp_notifier.load_working_set_with_fallback("2026-08-30")

    assert result == []


def test_format_whatsapp_message_empty_working_set():
    msg = whatsapp_notifier.format_whatsapp_message("2026-08-30", "summary", [])
    assert "Daily Security Digest Available" in msg


def test_format_whatsapp_message_lists_articles():
    working_set = [{"title": "Critical RCE", "link": "https://example.com/1"}]
    msg = whatsapp_notifier.format_whatsapp_message("2026-08-30", "summary", working_set)
    assert "Critical RCE" in msg
    assert "https://example.com/1" in msg


def test_format_whatsapp_message_truncates_long_lists():
    # Long enough per-item that the running length exceeds the 1520-char cap
    # before all 10 (of the eligible) articles are appended.
    working_set = [
        {"title": f"Advisory {i} " + "x" * 200, "link": f"https://example.com/{i}"} for i in range(20)
    ]
    msg = whatsapp_notifier.format_whatsapp_message("2026-08-30", "summary", working_set)
    assert len(msg) <= 1620
    assert "truncated" in msg


def test_send_twilio_notification_adds_whatsapp_prefix():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = whatsapp_notifier.send_twilio_notification(
            "ACxxx", "authtoken", "+14155238886", "+919999999999", "hello"
        )

    assert result is True
    _, kwargs = mock_post.call_args
    assert kwargs["data"]["From"] == "whatsapp:+14155238886"
    assert kwargs["data"]["To"] == "whatsapp:+919999999999"


def test_send_twilio_notification_failure_logs_response_text():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("bad request")
    mock_resp.text = "Invalid 'To' Phone Number"

    with patch("requests.post", return_value=mock_resp):
        result = whatsapp_notifier.send_twilio_notification(
            "ACxxx", "authtoken", "whatsapp:+14155238886", "whatsapp:+919999999999", "hello"
        )

    assert result is False


def test_send_whatsapp_notification_callmebot_success():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = whatsapp_notifier.send_whatsapp_notification(
            "https://api.callmebot.com/whatsapp.php", "token123", "+919999999999", "hello"
        )

    assert result is True
    mock_get.assert_called_once()


def test_send_whatsapp_notification_callmebot_failure():
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("boom")):
        result = whatsapp_notifier.send_whatsapp_notification(
            "https://api.callmebot.com/whatsapp.php", "token123", "+919999999999", "hello"
        )
    assert result is False


def test_send_whatsapp_notification_generic_gateway_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = whatsapp_notifier.send_whatsapp_notification(
            "https://gateway.example.com/send", "token123", "+919999999999", "hello"
        )

    assert result is True
    mock_post.assert_called_once()


def test_send_whatsapp_notification_generic_gateway_retries_as_json_on_415():
    first_resp = MagicMock()
    first_resp.status_code = 415

    second_resp = MagicMock()
    second_resp.status_code = 200
    second_resp.raise_for_status.return_value = None

    with patch("requests.post", side_effect=[first_resp, second_resp]) as mock_post:
        result = whatsapp_notifier.send_whatsapp_notification(
            "https://gateway.example.com/send", "token123", "+919999999999", "hello"
        )

    assert result is True
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[1].kwargs["json"] is not None


def test_main_uses_twilio_when_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(whatsapp_notifier.config, "WORKING_CACHE_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(whatsapp_notifier.config, "RANKED_CACHE_FILE", tmp_path / "missing2.json")
    monkeypatch.setattr(whatsapp_notifier.config, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(whatsapp_notifier.config, "TWILIO_ACCOUNT_SID", "ACxxx")
    monkeypatch.setattr(whatsapp_notifier.config, "TWILIO_AUTH_TOKEN", "authtoken")
    monkeypatch.setattr(whatsapp_notifier.config, "TWILIO_FROM_NUMBER", "whatsapp:+14155238886")
    monkeypatch.setattr(whatsapp_notifier.config, "TWILIO_TO_NUMBER", "whatsapp:+919999999999")
    monkeypatch.setattr(whatsapp_notifier.config, "WHATSAPP_API_URL", "")
    monkeypatch.setattr(whatsapp_notifier.config, "WHATSAPP_TOKEN", "")
    monkeypatch.setattr(whatsapp_notifier.config, "WHATSAPP_RECIPIENT", "")

    fake_db_manager = MagicMock()
    fake_db_manager.get_findings_by_date.return_value = []

    with patch.dict("sys.modules", {"scripts.db_manager": fake_db_manager}), \
         patch.object(whatsapp_notifier, "send_twilio_notification", return_value=True) as mock_send:
        whatsapp_notifier.main()

    mock_send.assert_called_once()


def test_main_skips_when_nothing_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(whatsapp_notifier.config, "WORKING_CACHE_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(whatsapp_notifier.config, "RANKED_CACHE_FILE", tmp_path / "missing2.json")
    monkeypatch.setattr(whatsapp_notifier.config, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(whatsapp_notifier.config, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(whatsapp_notifier.config, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(whatsapp_notifier.config, "TWILIO_TO_NUMBER", "")
    monkeypatch.setattr(whatsapp_notifier.config, "WHATSAPP_API_URL", "")
    monkeypatch.setattr(whatsapp_notifier.config, "WHATSAPP_TOKEN", "")
    monkeypatch.setattr(whatsapp_notifier.config, "WHATSAPP_RECIPIENT", "")

    fake_db_manager = MagicMock()
    fake_db_manager.get_findings_by_date.return_value = []

    with patch.dict("sys.modules", {"scripts.db_manager": fake_db_manager}), \
         patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        whatsapp_notifier.main()

    mock_post.assert_not_called()
    mock_get.assert_not_called()
