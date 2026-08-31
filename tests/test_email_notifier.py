"""Unit tests for the SMTP email notifier."""

import json
from unittest.mock import MagicMock, patch

from scripts import email_notifier


def test_parse_executive_summary_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.md"
    assert email_notifier.parse_executive_summary(missing) == (
        "Daily security briefing generated successfully."
    )


def test_parse_executive_summary_extracts_block(tmp_path):
    md_path = tmp_path / "brief.md"
    md_path.write_text(
        "## Executive Summary\nA critical flaw was patched.\n\n## Findings\nMore text.\n",
        encoding="utf-8",
    )
    assert email_notifier.parse_executive_summary(md_path) == "A critical flaw was patched."


def test_load_working_set_prefers_working_cache(tmp_path, monkeypatch):
    working = tmp_path / "working.json"
    ranked = tmp_path / "ranked.json"
    working.write_text(json.dumps([{"title": "From working cache"}]), encoding="utf-8")
    ranked.write_text(json.dumps([{"title": "From ranked cache"}]), encoding="utf-8")

    monkeypatch.setattr(email_notifier, "WORKING_CACHE_FILE", working)
    monkeypatch.setattr(email_notifier, "RANKED_CACHE_FILE", ranked)

    assert email_notifier.load_working_set_with_fallback() == [{"title": "From working cache"}]


def test_load_working_set_falls_back_to_db(tmp_path, monkeypatch):
    monkeypatch.setattr(email_notifier, "WORKING_CACHE_FILE", tmp_path / "missing1.json")
    monkeypatch.setattr(email_notifier, "RANKED_CACHE_FILE", tmp_path / "missing2.json")

    fake_db_manager = MagicMock()
    fake_db_manager.get_findings_by_date.return_value = [{"title": "From DB"}]
    with patch.dict("sys.modules", {"scripts.db_manager": fake_db_manager}):
        result = email_notifier.load_working_set_with_fallback()

    assert result == [{"title": "From DB"}]


def test_load_working_set_returns_empty_when_nothing_available(tmp_path, monkeypatch):
    monkeypatch.setattr(email_notifier, "WORKING_CACHE_FILE", tmp_path / "missing1.json")
    monkeypatch.setattr(email_notifier, "RANKED_CACHE_FILE", tmp_path / "missing2.json")

    fake_db_manager = MagicMock()
    fake_db_manager.get_findings_by_date.return_value = []
    with patch.dict("sys.modules", {"scripts.db_manager": fake_db_manager}):
        result = email_notifier.load_working_set_with_fallback()

    assert result == []


def test_severity_badge_thresholds():
    assert "CRITICAL" in email_notifier._severity_badge(9)
    assert "CRITICAL" in email_notifier._severity_badge(8)
    assert "HIGH" in email_notifier._severity_badge(6)
    assert "MEDIUM" in email_notifier._severity_badge(4)
    assert "LOW" in email_notifier._severity_badge(1)


def test_format_email_html_includes_summary_and_findings():
    working_set = [{"title": "Critical RCE", "link": "https://example.com/1", "rank": 9, "source": "CISA", "tags": ["web"]}]
    html = email_notifier.format_email_html("2026-08-30", "All quiet.", working_set)

    assert "2026-08-30" in html
    assert "All quiet." in html
    assert "Critical RCE" in html
    assert "https://example.com/1" in html
    assert "CRITICAL" in html


def test_format_email_html_truncates_long_summary():
    long_summary = "x" * 1000
    html = email_notifier.format_email_html("2026-08-30", long_summary, [])
    assert "x" * 500 in html
    assert "x" * 501 not in html


def test_send_email_no_recipients_returns_false(monkeypatch):
    monkeypatch.setattr(email_notifier, "SMTP_TO_EMAILS", "")
    result = email_notifier.send_email("subject", "<html></html>")
    assert result is False


def test_send_email_success_with_tls(monkeypatch):
    monkeypatch.setattr(email_notifier, "SMTP_TO_EMAILS", "secops@example.com, other@example.com")
    monkeypatch.setattr(email_notifier, "SMTP_FROM_EMAIL", "brief@example.com")
    monkeypatch.setattr(email_notifier, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_notifier, "SMTP_PORT", 587)
    monkeypatch.setattr(email_notifier, "SMTP_USE_TLS", True)
    monkeypatch.setattr(email_notifier, "SMTP_USERNAME", "user")
    monkeypatch.setattr(email_notifier, "SMTP_PASSWORD", "pass")

    mock_server = MagicMock()
    with patch.object(email_notifier.smtplib, "SMTP", return_value=mock_server) as mock_smtp:
        result = email_notifier.send_email("subject", "<html></html>")

    assert result is True
    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=15)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user", "pass")
    mock_server.sendmail.assert_called_once()
    mock_server.quit.assert_called_once()


def test_send_email_success_without_tls_or_auth(monkeypatch):
    monkeypatch.setattr(email_notifier, "SMTP_TO_EMAILS", "secops@example.com")
    monkeypatch.setattr(email_notifier, "SMTP_FROM_EMAIL", "brief@example.com")
    monkeypatch.setattr(email_notifier, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_notifier, "SMTP_PORT", 25)
    monkeypatch.setattr(email_notifier, "SMTP_USE_TLS", False)
    monkeypatch.setattr(email_notifier, "SMTP_USERNAME", "")
    monkeypatch.setattr(email_notifier, "SMTP_PASSWORD", "")

    mock_server = MagicMock()
    with patch.object(email_notifier.smtplib, "SMTP", return_value=mock_server):
        result = email_notifier.send_email("subject", "<html></html>")

    assert result is True
    mock_server.starttls.assert_not_called()
    mock_server.login.assert_not_called()


def test_send_email_returns_false_on_smtp_error(monkeypatch):
    monkeypatch.setattr(email_notifier, "SMTP_TO_EMAILS", "secops@example.com")
    monkeypatch.setattr(email_notifier, "SMTP_FROM_EMAIL", "brief@example.com")
    monkeypatch.setattr(email_notifier, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_notifier, "SMTP_PORT", 587)
    monkeypatch.setattr(email_notifier, "SMTP_USE_TLS", True)
    monkeypatch.setattr(email_notifier, "SMTP_USERNAME", "")
    monkeypatch.setattr(email_notifier, "SMTP_PASSWORD", "")

    with patch.object(email_notifier.smtplib, "SMTP", side_effect=OSError("connection refused")):
        result = email_notifier.send_email("subject", "<html></html>")

    assert result is False


def test_main_skips_when_smtp_not_configured(monkeypatch):
    monkeypatch.setattr(email_notifier, "SMTP_HOST", "")
    monkeypatch.setattr(email_notifier, "SMTP_FROM_EMAIL", "")
    monkeypatch.setattr(email_notifier, "SMTP_TO_EMAILS", "")

    with patch.object(email_notifier, "send_email") as mock_send:
        email_notifier.main()

    mock_send.assert_not_called()


def test_main_happy_path_sends_email(tmp_path, monkeypatch):
    monkeypatch.setattr(email_notifier, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_notifier, "SMTP_FROM_EMAIL", "brief@example.com")
    monkeypatch.setattr(email_notifier, "SMTP_TO_EMAILS", "secops@example.com")
    monkeypatch.setattr(email_notifier, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(email_notifier, "WORKING_CACHE_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(email_notifier, "RANKED_CACHE_FILE", tmp_path / "missing2.json")

    fake_db_manager = MagicMock()
    fake_db_manager.get_findings_by_date.return_value = []

    with patch.dict("sys.modules", {"scripts.db_manager": fake_db_manager}), \
         patch.object(email_notifier, "send_email", return_value=True) as mock_send:
        email_notifier.main()

    mock_send.assert_called_once()
    args, _ = mock_send.call_args
    assert "Daily Security Intelligence Briefing" in args[0]
