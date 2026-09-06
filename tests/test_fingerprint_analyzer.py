"""Unit tests for the content fingerprinting module."""

import json

import pytest

from scripts import fingerprint_analyzer


def test_normalize_text_strips_punctuation_and_case():
    assert fingerprint_analyzer.normalize_text("Critical RCE: Apache Struts!") == "criticalrceapachestruts"


def test_normalize_text_empty_string():
    assert fingerprint_analyzer.normalize_text("") == ""


def test_get_keywords_filters_stop_words_and_short_words():
    text = "There would be a critical vulnerability in the apache struts framework today"
    keywords = fingerprint_analyzer.get_keywords(text)
    assert "would" not in keywords
    assert "there" not in keywords
    assert "vulnerability" not in keywords
    assert "apache" in keywords
    assert "struts" in keywords
    assert "framework" in keywords


def test_get_keywords_sorted_by_frequency_then_alpha():
    text = "struts struts struts apache apache framework"
    keywords = fingerprint_analyzer.get_keywords(text)
    assert keywords[0] == "struts"
    assert keywords[1] == "apache"


def test_get_keywords_respects_limit():
    import string

    letters = string.ascii_lowercase
    words = [f"word{letters[i // 26]}{letters[i % 26]}" for i in range(40)]
    keywords = fingerprint_analyzer.get_keywords(" ".join(words), num_keywords=5)
    assert len(keywords) == 5


def test_main_exits_when_full_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(fingerprint_analyzer.config, "FULL_CACHE_FILE", tmp_path / "missing.json")
    with pytest.raises(SystemExit) as exc_info:
        fingerprint_analyzer.main()
    assert exc_info.value.code == 1


def test_main_generates_fingerprints(tmp_path, monkeypatch):
    full_cache = tmp_path / "full.json"
    fp_cache = tmp_path / "fingerprints.json"
    articles = [
        {
            "id": "1",
            "title": "Critical Apache Struts RCE",
            "content_text": "A critical remote code execution flaw was found in Apache Struts framework.",
            "link": "https://example.com/1",
        }
    ]
    full_cache.write_text(json.dumps(articles), encoding="utf-8")

    monkeypatch.setattr(fingerprint_analyzer.config, "FULL_CACHE_FILE", full_cache)
    monkeypatch.setattr(fingerprint_analyzer.config, "FINGERPRINT_CACHE_FILE", fp_cache)

    fingerprint_analyzer.main()

    result = json.loads(fp_cache.read_text(encoding="utf-8"))
    assert "1" in result
    assert result["1"]["link"] == "https://example.com/1"
    assert len(result["1"]["title_hash"]) == 32
    assert "apache" in result["1"]["keywords"]
