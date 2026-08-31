"""Content formatting and sanitization utilities for the HTML report.

Article content (title, source, links, body) originates from public RSS
feeds and LLM output -- both untrusted -- so the sanitizers here are the
last line of defense before that content is embedded in the generated
report. The box/point-card formatters below are regex-based repairs that
turn loosely-structured LLM markdown into the report's fixed visual
sections (Threat Modeling, Dependency Ecosystem, PR Checklist, TTPs, etc).
"""

import re
from html import escape as html_escape

import bleach

# Article content originates from public RSS feeds and LLM output -- both
# untrusted -- so everything derived from it is sanitized before being
# embedded in the generated report.
_ALLOWED_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "blockquote", "code", "pre", "a", "span",
    "div", "table", "thead", "tbody", "tr", "th", "td", "hr",
]
_ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel"],
    "span": ["class"],
    "div": ["class"],
    "code": ["class"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}
_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def _sanitize_html(raw_html: str) -> str:
    """Strip any tag/attribute/protocol not on the allowlist."""
    if not raw_html:
        return raw_html
    return bleach.clean(
        raw_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )


def _safe_link(url: str) -> str:
    """Only allow http(s) links; anything else (javascript:, data:, etc.) becomes '#'."""
    url = (url or "").strip()
    if re.match(r'^https?://', url, re.IGNORECASE):
        return html_escape(url, quote=True)
    return "#"


def _safe_slug(text: str) -> str:
    """Collapse to a safe id/class token: lowercase alnum + hyphen only."""
    slug = re.sub(r'[^a-z0-9]+', '-', (text or "").lower()).strip('-')
    return slug or "misc"


def format_threat_modeling_box(raw_threat):
    """Transform raw threat modeling text into a clean point-wise key-value grid box."""
    # Strip HTML tags
    clean = re.sub(r'</?[^>]+>', ' ', raw_threat)
    clean = re.sub(r'\s+', ' ', clean).strip()

    # Search for the 4 key sections
    m_stride = re.search(r'(?:STRIDE\s*Threat|STRIDE)\s*:?\s*(.*?)(?=(?:Design\s*Flaw|Secure\s*Design\s*Principle|Secure\s*Design\s*Review\s*Question|$))', clean, re.IGNORECASE)
    m_flaw = re.search(r'(?:Design\s*Flaw)\s*:?\s*(.*?)(?=(?:Secure\s*Design\s*Principle|Secure\s*Design\s*Review\s*Question|$))', clean, re.IGNORECASE)
    m_principle = re.search(r'(?:Secure\s*Design\s*Principle)\s*:?\s*(.*?)(?=(?:Secure\s*Design\s*Review\s*Question|$))', clean, re.IGNORECASE)
    m_question = re.search(r'(?:Secure\s*Design\s*Review\s*Question|Review\s*Question)\s*:?\s*(.*)', clean, re.IGNORECASE)

    def extract_val(match):
        if not match:
            return ""
        val = match.group(1).strip()
        val = re.sub(r'^[*_`:\s-]+|[*_`"\s]+$', '', val).strip()
        return val

    stride_val = extract_val(m_stride)
    flaw_val = extract_val(m_flaw)
    principle_val = extract_val(m_principle)
    question_val = extract_val(m_question)

    grid_items = []
    if stride_val:
        grid_items.append(f"""
            <div class="threat-item">
                <span class="threat-key">STRIDE Threat</span>
                <span class="threat-val"><span class="stride-badge">{stride_val}</span></span>
            </div>""")
    if flaw_val:
        grid_items.append(f"""
            <div class="threat-item">
                <span class="threat-key">Design Flaw</span>
                <span class="threat-val">{flaw_val}</span>
            </div>""")
    if principle_val:
        grid_items.append(f"""
            <div class="threat-item">
                <span class="threat-key">Secure Design Principle</span>
                <span class="threat-val">{principle_val}</span>
            </div>""")
    if question_val:
        # Format question_val cleanly as point-wise bullet list items
        q_clean = re.sub(r'&(?:ldquo|rdquo|quot);', '"', question_val)
        q_clean = re.sub(r'^["`\s-]+|["`\s]+$', '', q_clean).strip()
        
        # Split into individual questions or points
        raw_points = re.split(r'(?:\r?\n|[-*•]\s+|\s*\?\s+|\s*;\s*)', q_clean)
        points = []
        for p in raw_points:
            p_strip = p.strip().strip('"`*_ ')
            if not p_strip:
                continue
            if not p_strip.endswith('?') and not p_strip.endswith('.'):
                p_strip += '?'
            if len(p_strip) > 5 and p_strip not in points:
                points.append(p_strip)
        
        if not points and q_clean:
            points = [q_clean]
            
        list_lis = "".join([f'<li><span class="review-bullet">✦</span><span class="review-text">{pt}</span></li>' for pt in points])
        
        grid_items.append(f"""
            <div class="threat-item full-width design-review-item">
                <span class="threat-key">📋 Secure Design Review Questions</span>
                <ul class="design-review-list">
                    {list_lis}
                </ul>
            </div>""")

    # Fallback to point-wise list if key regex matching was empty
    if not grid_items:
        sentences = [s.strip().strip('*_- ') for s in clean.split('.') if s.strip()]
        list_items = "".join([f'<li><span class="review-bullet">✦</span><span class="review-text">{s}.</span></li>' for s in sentences])
        box_content = f'<ul class="design-review-list">{list_items}</ul>'
    else:
        box_content = f'<div class="threat-grid">{"".join(grid_items)}</div>'

    box_html = f"""
    <div class="threat-card-box">
        <div class="threat-card-title">🛡️ Threat Modeling & Secure Design Lesson</div>
        {box_content}
    </div>
    """
    return box_html

def format_ecosystem_box(raw_ecosystem):
    """Format raw ecosystem details into a clean box."""
    clean = re.sub(r'</?[^>]+>', ' ', raw_ecosystem)
    clean = re.sub(r'\s+', ' ', clean).strip()

    m_package = re.search(r'(?:Package\s*Name|Package)\s*:?\s*(.*?)(?=(?:Ecosystem|Patched\s*Version|Advisory\s*Identifier|$))', clean, re.IGNORECASE)
    m_eco = re.search(r'(?:Ecosystem)\s*:?\s*(.*?)(?=(?:Patched\s*Version|Advisory\s*Identifier|$))', clean, re.IGNORECASE)
    m_patch = re.search(r'(?:Patched\s*Version|Patched)\s*:?\s*(.*?)(?=(?:Advisory\s*Identifier|$))', clean, re.IGNORECASE)
    m_advisory = re.search(r'(?:Advisory\s*Identifier|Advisory|Identifier)\s*:?\s*(.*)', clean, re.IGNORECASE)

    def extract_val(match):
        if not match:
            return ""
        val = match.group(1).strip()
        val = re.sub(r'^[*_`:\s-]+|[*_`"\s]+$', '', val).strip()
        return val

    pkg_val = extract_val(m_package)
    eco_val = extract_val(m_eco)
    patch_val = extract_val(m_patch)
    adv_val = extract_val(m_advisory)

    grid_items = []
    if pkg_val:
        grid_items.append(f"""
            <div class="ecosystem-item">
                <span class="ecosystem-key">Package Name</span>
                <span class="ecosystem-val"><code>{pkg_val}</code></span>
            </div>""")
    if eco_val:
        grid_items.append(f"""
            <div class="ecosystem-item">
                <span class="ecosystem-key">Ecosystem</span>
                <span class="ecosystem-val"><span class="tag-pill tag-{eco_val.lower().replace(' ', '')}">{eco_val}</span></span>
            </div>""")
    if patch_val:
        grid_items.append(f"""
            <div class="ecosystem-item">
                <span class="ecosystem-key">Patched Version</span>
                <span class="ecosystem-val"><code>{patch_val}</code></span>
            </div>""")
    if adv_val:
        grid_items.append(f"""
            <div class="ecosystem-item">
                <span class="ecosystem-key">Advisory Ref</span>
                <span class="ecosystem-val">{adv_val}</span>
            </div>""")

    if not grid_items:
        return ""

    box_html = f"""
    <div class="ecosystem-card-box">
        <div class="ecosystem-grid">
            {"".join(grid_items)}
        </div>
    </div>
    """
    return box_html

def format_dev_checklist_box(raw_checklist):
    """Format developer PR checklist into checkbox list items."""
    items = re.findall(r'(?:[-*•]\s+)?\[\s*[xX]?\s*\]\s*(.*?)(?=\n|$)', raw_checklist)
    if not items:
        lines = [line.strip().strip('*-• ') for line in raw_checklist.split('\n') if line.strip()]
        items = [line for line in lines if len(line) > 5]

    list_items = []
    for idx, item in enumerate(items):
        item_clean = re.sub(r'^[*_`:\s-]+|[*_`"\s]+$', '', item).strip()
        if item_clean:
            list_items.append(f"""
                <li class="dev-checklist-item">
                    <input type="checkbox" class="dev-checklist-checkbox" id="chk-{idx}" disabled checked>
                    <span>{item_clean}</span>
                </li>""")

    if not list_items:
        return ""

    box_html = f"""
    <div class="dev-checklist-box">
        <div class="dev-checklist-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-success);"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
            Developer PR Review Checklist
        </div>
        <ul class="dev-checklist-list">
            {"".join(list_items)}
        </ul>
    </div>
    """
    return box_html

def format_content_to_point_cards(content_snippet, key_type):
    """
    Transform raw section HTML (whether markdown ul/li or paragraph <p>)
    into structured point cards with themed bullet markers and CVE highlights.
    """
    if not content_snippet or not content_snippet.strip():
        return ""

    marker_info = {
        "desc": ("desc-marker", "📌"),
        "ttps": ("ttps-marker", "⚡"),
        "pentest": ("pentest-marker", "🎯"),
        "remediation": ("remediation-marker", "🔧")
    }
    marker_cls, default_icon = marker_info.get(key_type, ("desc-marker", "▸"))

    items = []
    
    # 1. Check for <li> elements in content
    li_matches = re.findall(r'<li>(.*?)</li>', content_snippet, re.DOTALL | re.IGNORECASE)
    if li_matches:
        for li in li_matches:
            c = li.strip()
            c = re.sub(r'</?p>', '', c).strip()
            if c:
                items.append(c)
    else:
        # 2. Extract paragraph text or split by sentences
        p_matches = re.findall(r'<p>(.*?)</p>', content_snippet, re.DOTALL | re.IGNORECASE)
        raw_text = " ".join(p_matches) if p_matches else content_snippet
        clean_text = re.sub(r'</?(?!strong|b|code|em|i)[^>]+>', '', raw_text).strip()
        
        # Split sentences cleanly without breaking CVE-xxxx or decimals
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"])', clean_text)
        for s in sentences:
            s_clean = s.strip()
            if len(s_clean) > 8:
                items.append(s_clean)

    if not items:
        clean_fallback = re.sub(r'</?(?!strong|b|code|em|i)[^>]+>', '', content_snippet).strip()
        items = [clean_fallback] if clean_fallback else [content_snippet.strip()]

    point_lis = []
    for item in items:
        # Auto-highlight CVEs with styled badge pill if present
        item_formatted = re.sub(
            r'\b(CVE-\d{4}-\d{4,7})\b',
            r'<span class="cve-pill">\1</span>',
            item
        )
        point_lis.append(
            f'<li class="point-item">'
            f'<span class="point-marker {marker_cls}">{default_icon}</span>'
            f'<span class="point-text">{item_formatted}</span>'
            f'</li>'
        )

    return f'<ul class="point-list {key_type}-list">{"".join(point_lis)}</ul>'


def format_article_sections(rendered_body):
    """
    Parse all standard markdown headers in article body and format them into
    consistent, theme-accented point cards.
    """
    sections = [
        ("Description &amp; Context", "📌 Description & Context", "desc", "desc-hdr"),
        ("Description & Context", "📌 Description & Context", "desc", "desc-hdr"),
        ("TTPs &amp; Exploitation Vectors", "⚡ TTPs & Exploitation Vectors", "ttps", "ttps-hdr"),
        ("TTPs & Exploitation Vectors", "⚡ TTPs & Exploitation Vectors", "ttps", "ttps-hdr"),
        ("Pentesting Value &amp; Testing Method", "🎯 Pentesting Value & Testing Method", "pentest", "pentest-hdr"),
        ("Pentesting Value & Testing Method", "🎯 Pentesting Value & Testing Method", "pentest", "pentest-hdr"),
        ("Remediation &amp; Mitigations", "🔧 Remediation & Mitigations", "remediation", "remediation-hdr"),
        ("Remediation", "🔧 Remediation & Mitigations", "remediation", "remediation-hdr"),
    ]

    for key, display_title, key_type, hdr_cls in sections:
        # Pattern 1: Header alone in <p><strong>Key</strong>:</p> followed by HTML content snippet
        pattern1 = r'<p><strong>' + re.escape(key) + r'</strong>(?::|\s)*</p>\s*(.*?)(?=<p><strong>|<div class="section-header">|<div class="threat-card-box">|<div class="ecosystem-card-box">|<div class="dev-checklist-box">|$)'
        
        def repl1(m):
            snippet = m.group(1).strip()
            points_html = format_content_to_point_cards(snippet, key_type)
            return f'<div class="section-header {hdr_cls}">{display_title}</div>{points_html}'

        new_body, count = re.subn(pattern1, repl1, rendered_body, flags=re.IGNORECASE | re.DOTALL)
        if count > 0:
            rendered_body = new_body
        else:
            # Pattern 2: Header inline inside <p><strong>Key</strong>: Content...</p>
            pattern2 = r'<p><strong>' + re.escape(key) + r'</strong>(?::|\s)*\s*(.*?)</p>'
            def repl2(m):
                snippet = m.group(1).strip()
                points_html = format_content_to_point_cards(snippet, key_type)
                return f'<div class="section-header {hdr_cls}">{display_title}</div>{points_html}'
            
            rendered_body = re.sub(pattern2, repl2, rendered_body, flags=re.IGNORECASE | re.DOTALL)

    return rendered_body

