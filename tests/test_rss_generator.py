"""Unit tests for the RSS 2.0 feed generator."""

import json

import pytest

from scripts import rss_generator


def _article(**overrides):
    art = {
        "title": "Critical Apache Struts RCE",
        "link": "https://example.com/advisory-1",
        "rank": 9,
        "source": "CISA",
        "tags": ["web", "rce"],
        "rank_reason": "Actively exploited in the wild.",
        "content_text": "Full advisory details go here.",
    }
    art.update(overrides)
    return art


def test_generate_rss_xml_includes_core_fields():
    xml = rss_generator.generate_rss_xml([_article()], "2026-08-30")
    assert "<title>[Rank 9/10 - CRITICAL] Critical Apache Struts RCE</title>" in xml
    assert "<link>https://example.com/advisory-1</link>" in xml
    assert '<guid isPermaLink="true">https://example.com/advisory-1</guid>' in xml
    assert "<category>web</category>" in xml
    assert "<category>rce</category>" in xml
    assert "<rss version=\"2.0\"" in xml


@pytest.mark.parametrize(
    "rank,expected_severity",
    [(9, "CRITICAL"), (8, "CRITICAL"), (6, "HIGH"), (4, "MEDIUM"), (1, "LOW")],
)
def test_generate_rss_xml_severity_labels(rank, expected_severity):
    xml = rss_generator.generate_rss_xml([_article(rank=rank)], "2026-08-30")
    assert f"- {expected_severity}]" in xml


def test_generate_rss_xml_escapes_html_in_title():
    xml = rss_generator.generate_rss_xml([_article(title="<script>alert(1)</script>")], "2026-08-30")
    assert "<script>alert(1)</script>" not in xml
    assert "&lt;script&gt;" in xml


def test_generate_rss_xml_handles_empty_article_list():
    xml = rss_generator.generate_rss_xml([], "2026-08-30")
    assert "<channel>" in xml
    assert "<item>" not in xml


def test_main_returns_when_working_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(rss_generator.config, "WORKING_CACHE_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(rss_generator.config, "REPORTS_DIR", tmp_path)
    # Should not raise.
    rss_generator.main()
    assert not (tmp_path / "rss.xml").exists()


def test_main_exits_on_malformed_json(tmp_path, monkeypatch):
    working_cache = tmp_path / "working.json"
    working_cache.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(rss_generator.config, "WORKING_CACHE_FILE", working_cache)
    monkeypatch.setattr(rss_generator.config, "REPORTS_DIR", tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        rss_generator.main()
    assert exc_info.value.code == 1


def test_main_writes_rss_and_feed_files(tmp_path, monkeypatch):
    working_cache = tmp_path / "working.json"
    working_cache.write_text(json.dumps([_article()]), encoding="utf-8")
    monkeypatch.setattr(rss_generator.config, "WORKING_CACHE_FILE", working_cache)
    monkeypatch.setattr(rss_generator.config, "REPORTS_DIR", tmp_path)

    rss_generator.main()

    rss_content = (tmp_path / "rss.xml").read_text(encoding="utf-8")
    feed_content = (tmp_path / "feed.xml").read_text(encoding="utf-8")
    assert rss_content == feed_content
    assert "Critical Apache Struts RCE" in rss_content
