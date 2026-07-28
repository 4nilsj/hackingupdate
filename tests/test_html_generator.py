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
        assert 'Showing 1 of 1 findings' in html or 'total' in html
    finally:
        Path(temp_path).unlink()
