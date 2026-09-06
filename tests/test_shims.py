"""Unit tests verifying backward-compatibility shims in scripts/."""

import importlib
import sys

MODULE_NAMES = [
    "build_working_set",
    "cve_enrichment",
    "db_manager",
    "dedupe_fingerprints",
    "email_notifier",
    "extractor",
    "fetcher",
    "fingerprint_analyzer",
    "html_generator",
    "priority_ranker",
    "prune_logs",
    "report_formatting",
    "report_generator",
    "report_template",
    "rss_generator",
    "teams_notifier",
    "whatsapp_notifier",
]


def test_all_script_shims_resolve_to_hackingupdate_modules():
    """Verify each script shim resolves to the canonical hackingupdate module."""
    for mod_name in MODULE_NAMES:
        # Import through scripts namespace
        script_mod = importlib.import_module(f"scripts.{mod_name}")
        # Import through hackingupdate namespace
        pkg_mod = importlib.import_module(f"hackingupdate.{mod_name}")

        # Both imports should resolve to the same underlying module in sys.modules
        assert script_mod is pkg_mod, f"scripts.{mod_name} should resolve to hackingupdate.{mod_name}"
        assert sys.modules[f"scripts.{mod_name}"] is sys.modules[f"hackingupdate.{mod_name}"]


def test_script_shim_exposes_expected_attributes():
    """Verify key functions/classes are directly accessible on the shim module."""
    from scripts import cve_enrichment, db_manager, dedupe_fingerprints, priority_ranker

    assert hasattr(cve_enrichment, "enrich_articles")
    assert hasattr(cve_enrichment, "extract_cves")
    assert hasattr(db_manager, "init_db")
    assert hasattr(db_manager, "store_findings")
    assert hasattr(db_manager, "get_recent_finding_identifiers")
    assert hasattr(dedupe_fingerprints, "jaccard_similarity")
    assert hasattr(priority_ranker, "rank_batch_with_llm")
    assert hasattr(priority_ranker, "fallback_rank_and_tag")
