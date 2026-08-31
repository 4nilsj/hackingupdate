"""Unit tests for the working-set builder (CVE + semantic dedup, rank thresholding)."""

import json

import pytest

from scripts import build_working_set


def _write_ranked(tmp_path, monkeypatch, articles, fingerprints=None):
    ranked_file = tmp_path / "ranked.json"
    working_file = tmp_path / "working.json"
    fp_file = tmp_path / "fingerprints.json"

    ranked_file.write_text(json.dumps(articles), encoding="utf-8")
    if fingerprints is not None:
        fp_file.write_text(json.dumps(fingerprints), encoding="utf-8")

    monkeypatch.setattr(build_working_set.config, "RANKED_CACHE_FILE", ranked_file)
    monkeypatch.setattr(build_working_set.config, "FINGERPRINT_CACHE_FILE", fp_file)
    monkeypatch.setattr(build_working_set.config, "WORKING_CACHE_FILE", working_file)
    return working_file


def _load_result(working_file):
    return json.loads(working_file.read_text(encoding="utf-8"))


def test_main_exits_when_ranked_cache_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(build_working_set.config, "RANKED_CACHE_FILE", tmp_path / "missing.json")
    with pytest.raises(SystemExit) as exc_info:
        build_working_set.main()
    assert exc_info.value.code == 1


def test_main_dedupes_repeated_cve_coverage(tmp_path, monkeypatch):
    articles = [
        {"id": "1", "title": "First report", "description": "", "content_text": "Exploit for CVE-2026-1111", "rank": 6},
        {"id": "2", "title": "Rehash", "description": "", "content_text": "Also about CVE-2026-1111", "rank": 7},
    ]
    working_file = _write_ranked(tmp_path, monkeypatch, articles, fingerprints={})
    build_working_set.main()
    result = _load_result(working_file)
    assert [a["id"] for a in result] == ["1"]


def test_main_dedupes_semantic_near_duplicates(tmp_path, monkeypatch):
    articles = [
        {"id": "1", "title": "Kept Article", "description": "", "content_text": "", "rank": 6},
        {"id": "2", "title": "Semantic Duplicate", "description": "", "content_text": "", "rank": 6},
    ]
    fingerprints = {
        "1": {"keywords": ["alpha", "beta", "gamma", "delta"]},
        "2": {"keywords": ["alpha", "beta", "gamma", "epsilon"]},
    }
    working_file = _write_ranked(tmp_path, monkeypatch, articles, fingerprints=fingerprints)
    build_working_set.main()
    result = _load_result(working_file)
    assert [a["id"] for a in result] == ["1"]


def test_main_falls_back_to_top_eight_when_too_few_pass_threshold(tmp_path, monkeypatch):
    articles = [
        {"id": str(i), "title": f"Low rank {i}", "description": "", "content_text": "", "rank": 3}
        for i in range(10)
    ]
    working_file = _write_ranked(tmp_path, monkeypatch, articles, fingerprints={})
    build_working_set.main()
    result = _load_result(working_file)
    assert len(result) == 8
    assert [a["id"] for a in result] == [str(i) for i in range(8)]


def test_main_caps_working_set_at_twenty_five(tmp_path, monkeypatch):
    articles = [
        {"id": str(i), "title": f"High rank {i}", "description": "", "content_text": "", "rank": 6}
        for i in range(30)
    ]
    working_file = _write_ranked(tmp_path, monkeypatch, articles, fingerprints={})
    build_working_set.main()
    result = _load_result(working_file)
    assert len(result) == 25


def test_main_survives_missing_fingerprint_cache(tmp_path, monkeypatch):
    articles = [{"id": "1", "title": "Solo", "description": "", "content_text": "", "rank": 6}]
    working_file = _write_ranked(tmp_path, monkeypatch, articles, fingerprints=None)
    build_working_set.main()
    result = _load_result(working_file)
    assert [a["id"] for a in result] == ["1"]
