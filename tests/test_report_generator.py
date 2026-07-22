"""Unit tests for report generator and fallback template logic."""

from scripts.report_generator import (
    format_readable_description,
    generate_local_fallback_report,
)


def test_format_readable_description_cve():
    text = "Critical flaw identified in Fortinet software. View CSAF Summary. Affected CVE-2026-1234 and CVE-2026-5678."
    formatted = format_readable_description(text)
    assert "CVE-2026-1234" in formatted
    assert "CVE-2026-5678" in formatted
    assert "View CSAF Summary" not in formatted


def test_generate_local_fallback_report():
    sample_working_set = [
        {
            "id": "1",
            "title": "Critical RCE Flaw",
            "source": "CISA",
            "link": "https://cisa.gov/alert-1",
            "rank": 9,
            "tags": ["web"],
            "rank_reason": "High severity RCE",
            "content_text": "Details about remote code execution flaw in web application."
        }
    ]

    report_md = generate_local_fallback_report(sample_working_set, "2026-07-22")
    assert "# Daily Security Intelligence Briefing - 2026-07-22" in report_md
    assert "Critical RCE Flaw" in report_md
    assert "Priority Rank" in report_md
    assert "9/10" in report_md
    assert "STRIDE Threat" in report_md
