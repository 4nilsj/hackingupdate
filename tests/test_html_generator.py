"""Unit tests for html_generator.py verifying point-wise design review box and single post card deduplication."""

import re
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

def test_parse_markdown_to_premium_html_sanitizes_malicious_article():
    """Article title, link, source, and body come from untrusted RSS/LLM content;
    a malicious payload in any of them must not survive into the rendered HTML."""
    md_content = """# Daily Security Intelligence Briefing - 2026-07-29

## Executive Summary
Test summary.

## Category: WEB
### <img src=x onerror=alert(1)>Fake Advisory
- **Source**: <script>alert('src')</script>Evil Corp
- **Priority Rank**: `9/10`
- **Link**: javascript:alert(document.cookie)
- **Pentester Category Tags**: web

**Description & Context**:
- Normal text <script>alert('body')</script> more text.

---
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(md_content)
        temp_path = f.name

    try:
        html = parse_markdown_to_premium_html(temp_path, "2026-07-29")

        # Isolate the injected article card from the page's own trusted
        # template chrome (which legitimately has a <script> and onclick=
        # handlers for the search/filter UI) before asserting on it.
        card_start = html.index('<div class="article-card')
        card_end = html.index('</section>', card_start)
        card_html = html[card_start:card_end]

        # bleach/html.escape neutralize markup by stripping tags or turning
        # them into inert escaped text (e.g. "&lt;img ...&gt;"), so the raw
        # substrings ("alert(1)", "onerror=", "javascript:") may still appear
        # as harmless text. What actually matters is that no *live* markup
        # construct survives within the injected content: no real <script>
        # tag, no element carrying an event handler, no javascript: URI.
        assert not re.search(r"<script[^>]*>\s*alert", card_html, re.IGNORECASE)
        assert not re.search(r"<[a-z]+[^>]*\son\w+\s*=", card_html, re.IGNORECASE)
        assert not re.search(r'href\s*=\s*"javascript:', card_html, re.IGNORECASE)
        assert 'href="#"' in card_html  # unsafe link neutralized
    finally:
        Path(temp_path).unlink()

def test_format_content_to_point_cards():
    from scripts.html_generator import format_article_sections, format_content_to_point_cards

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
