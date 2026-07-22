"""Unit tests for deduplication module."""

from scripts.dedupe_fingerprints import jaccard_similarity


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
