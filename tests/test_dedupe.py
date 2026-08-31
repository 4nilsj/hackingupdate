"""Unit tests for deduplication module."""

import json

import pytest

from scripts import dedupe_fingerprints
from scripts.dedupe_fingerprints import jaccard_similarity


def _write_cache_files(tmp_path, monkeypatch, articles, fingerprints):
    full_cache = tmp_path / "full.json"
    fp_cache = tmp_path / "fingerprints.json"
    deduped_cache = tmp_path / "deduped.json"

    full_cache.write_text(json.dumps(articles), encoding="utf-8")
    fp_cache.write_text(json.dumps(fingerprints), encoding="utf-8")

    monkeypatch.setattr(dedupe_fingerprints.config, "FULL_CACHE_FILE", full_cache)
    monkeypatch.setattr(dedupe_fingerprints.config, "FINGERPRINT_CACHE_FILE", fp_cache)
    monkeypatch.setattr(dedupe_fingerprints.config, "DEDUPED_CACHE_FILE", deduped_cache)
    return deduped_cache


def test_main_exits_when_full_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(dedupe_fingerprints.config, "FULL_CACHE_FILE", tmp_path / "missing.json")
    with pytest.raises(SystemExit) as exc_info:
        dedupe_fingerprints.main()
    assert exc_info.value.code == 1


def test_main_exits_when_fingerprint_cache_missing(tmp_path, monkeypatch):
    full_cache = tmp_path / "full.json"
    full_cache.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(dedupe_fingerprints.config, "FULL_CACHE_FILE", full_cache)
    monkeypatch.setattr(dedupe_fingerprints.config, "FINGERPRINT_CACHE_FILE", tmp_path / "missing.json")
    with pytest.raises(SystemExit) as exc_info:
        dedupe_fingerprints.main()
    assert exc_info.value.code == 1


def test_main_keeps_article_with_no_fingerprint(tmp_path, monkeypatch):
    articles = [{"id": "1", "title": "Unfingerprinted"}]
    deduped_cache = _write_cache_files(tmp_path, monkeypatch, articles, fingerprints={})
    dedupe_fingerprints.main()
    result = json.loads(deduped_cache.read_text(encoding="utf-8"))
    assert [a["id"] for a in result] == ["1"]


def test_main_discards_exact_title_hash_duplicate(tmp_path, monkeypatch):
    articles = [
        {"id": "1", "title": "Original"},
        {"id": "2", "title": "Republished Copy"},
    ]
    fingerprints = {
        "1": {"title_hash": "samehash", "keywords": ["a", "b"]},
        "2": {"title_hash": "samehash", "keywords": ["c", "d"]},
    }
    deduped_cache = _write_cache_files(tmp_path, monkeypatch, articles, fingerprints)
    dedupe_fingerprints.main()
    result = json.loads(deduped_cache.read_text(encoding="utf-8"))
    assert [a["id"] for a in result] == ["1"]


def test_main_discards_near_duplicate_by_keyword_similarity(tmp_path, monkeypatch):
    articles = [
        {"id": "1", "title": "Kept"},
        {"id": "2", "title": "Near duplicate"},
    ]
    fingerprints = {
        "1": {"title_hash": "hash1", "keywords": ["alpha", "beta", "gamma", "delta"]},
        "2": {"title_hash": "hash2", "keywords": ["alpha", "beta", "gamma", "epsilon"]},
    }
    deduped_cache = _write_cache_files(tmp_path, monkeypatch, articles, fingerprints)
    dedupe_fingerprints.main()
    result = json.loads(deduped_cache.read_text(encoding="utf-8"))
    assert [a["id"] for a in result] == ["1"]


def test_main_keeps_dissimilar_articles(tmp_path, monkeypatch):
    articles = [
        {"id": "1", "title": "First"},
        {"id": "2", "title": "Second"},
    ]
    fingerprints = {
        "1": {"title_hash": "hash1", "keywords": ["alpha", "beta"]},
        "2": {"title_hash": "hash2", "keywords": ["gamma", "delta"]},
    }
    deduped_cache = _write_cache_files(tmp_path, monkeypatch, articles, fingerprints)
    dedupe_fingerprints.main()
    result = json.loads(deduped_cache.read_text(encoding="utf-8"))
    assert sorted(a["id"] for a in result) == ["1", "2"]


def test_jaccard_similarity_identical():
    list1 = ["vulnerability", "auth", "bypass", "cve"]
    list2 = ["vulnerability", "auth", "bypass", "cve"]
    assert jaccard_similarity(list1, list2) == 1.0


def test_jaccard_similarity_partial():
    list1 = ["vulnerability", "auth", "bypass", "cve"]
    list2 = ["vulnerability", "auth", "injection", "sqli"]
    # Intersection: vulnerability, auth (2). Union: vulnerability, auth, bypass, cve, injection, sqli (6).
    # 2/6 = 0.333...
    sim = jaccard_similarity(list1, list2)
    assert 0.3 < sim < 0.4


def test_jaccard_similarity_empty():
    assert jaccard_similarity([], ["test"]) == 0.0
    assert jaccard_similarity([], []) == 0.0
