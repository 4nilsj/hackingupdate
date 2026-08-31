"""Unit tests for the log pruning module."""

from datetime import datetime, timedelta

from scripts import prune_logs


def test_parse_line_date_iso_format():
    result = prune_logs.parse_line_date("2026-07-20 03:31:57 [INFO] Starting pipeline", None)
    assert result == datetime(2026, 7, 20).date()


def test_parse_line_date_syslog_format():
    line = "Starting Daily Security Briefing Pipeline: Mon Jul 20 03:31:57 IST 2026"
    result = prune_logs.parse_line_date(line, None)
    assert result == datetime(2026, 7, 20).date()


def test_parse_line_date_no_date_carries_forward_last_date():
    last_date = datetime(2026, 7, 18).date()
    result = prune_logs.parse_line_date("no date info in this log line at all", last_date)
    assert result == last_date


def test_main_returns_when_log_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(prune_logs.config, "LOG_FILE", tmp_path / "missing.log")
    # Should not raise.
    prune_logs.main()


def test_main_prunes_lines_older_than_five_days(tmp_path, monkeypatch):
    log_file = tmp_path / "daily_brief.log"
    today = datetime.now().date()
    old_date = today - timedelta(days=10)
    recent_date = today - timedelta(days=1)

    log_file.write_text(
        f"{old_date.isoformat()} [INFO] Old pipeline run\n"
        f"{recent_date.isoformat()} [INFO] Recent pipeline run\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(prune_logs.config, "LOG_FILE", log_file)

    prune_logs.main()

    remaining = log_file.read_text(encoding="utf-8")
    assert "Old pipeline run" not in remaining
    assert "Recent pipeline run" in remaining


def test_main_handles_unreadable_log_file_gracefully(tmp_path, monkeypatch):
    # A directory in place of the expected log file makes open() raise.
    log_dir = tmp_path / "daily_brief.log"
    log_dir.mkdir()
    monkeypatch.setattr(prune_logs.config, "LOG_FILE", log_dir)

    # Should not raise.
    prune_logs.main()
