"""Unit tests for configuration management."""

from hackingupdate.config import BASE_DIR, CACHE_DIR, FEEDS_DIR, REPORTS_DIR, LOGS_DIR, DATA_DIR


def test_directories_exist():
    """Verify all required directories exist."""
    assert BASE_DIR.is_dir()
    assert CACHE_DIR.is_dir()
    assert FEEDS_DIR.is_dir()
    assert REPORTS_DIR.is_dir()
    assert LOGS_DIR.is_dir()
    assert DATA_DIR.is_dir()
