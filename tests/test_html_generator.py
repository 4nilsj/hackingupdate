"""Unit tests for html_generator.py verifying point-wise design review box and single post card deduplication."""

import tempfile
from pathlib import Path
from scripts.html_generator import (
    format_threat_modeling_box,
    parse_markdown_to_premium_html,
)

def test_format_threat_modeling_box_point_wise():
    raw_threat = """
    - STRIDE Threat: Remote Code Execution
    - Design Flaw: Missing Input Validation
    - Secure Design Principle: Least Privilege
    - Secure Design Review Question: How does our application validate untrusted input? What sanitization is applied before query execution?
    """
    html = format_threat_modeling_box(raw_threat)
    assert '<ul class="design-review-list">' in html
    assert '<span class="review-bullet">✦</span>' in html
    assert 'How does our application validate untrusted input?' in html
    assert 'What sanitization is applied before query execution?' in html

def test_parse_markdown_to_premium_html_deduplication():
    md_content = """# Daily Security Intelligence Briefing - 2026-07-29

## Executive Summary
Test summary.

## Category: WEB
### WordPress Remote Code Execution
- **Source**: SecurityWeek
- **Priority Rank**: `9/10`
- **Link**: https://example.com/wp-rce
- **Pentester Category Tags**: web

**Description & Context**:
- Test description details.

---

## Category: API
### WordPress Remote Code Execution
- **Source**: SecurityWeek
- **Priority Rank**: `9/10`
- **Link**: https://example.com/wp-rce
- **Pentester Category Tags**: api

**Description & Context**:
- Test description details.

---
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(md_content)
        temp_path = f.name

    try:
        html = parse_markdown_to_premium_html(temp_path, "2026-07-29")
        # Should deduplicate into exactly 1 article card
        assert html.count('class="article-card') == 1
        # Should merge tags 'web' and 'api' into tag pills
        assert 'tag-web' in html
        assert 'tag-api' in html
    finally:
        Path(temp_path).unlink()

def test_format_content_to_point_cards():
    from scripts.html_generator import format_content_to_point_cards, format_article_sections

    paragraph_html = "<p>Attackers exploited CVE-2026-6875 to execute code. This is an active zero-day threat.</p>"
    points_html = format_content_to_point_cards(paragraph_html, "ttps")

    assert '<ul class="point-list ttps-list">' in points_html
    assert '<span class="point-marker ttps-marker">⚡</span>' in points_html
    assert '<span class="cve-pill">CVE-2026-6875</span>' in points_html
    assert 'Attackers exploited' in points_html
    assert 'This is an active zero-day threat.' in points_html

    rendered_body = "<p><strong>TTPs &amp; Exploitation Vectors</strong>:</p><p>Attackers exploited CVE-2026-6875. Second sentence detail.</p>"
    formatted = format_article_sections(rendered_body)
    assert '<div class="section-header ttps-hdr">⚡ TTPs & Exploitation Vectors</div>' in formatted
    assert '<ul class="point-list ttps-list">' in formatted
