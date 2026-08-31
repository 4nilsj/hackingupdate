"""Markdown-to-HTML report orchestration.

Parses the daily markdown briefing, delegates content repair/sanitization
to report_formatting.py and page structure to report_template.py, and
assembles the final report.
"""

import re
import sys
from datetime import datetime
from html import escape as html_escape
from pathlib import Path

import markdown

import hackingupdate.config as config
from scripts.report_formatting import (
    _safe_link,
    _safe_slug,
    _sanitize_html,
    format_article_sections,
    format_dev_checklist_box,
    format_ecosystem_box,
    format_threat_modeling_box,
)
from scripts.report_template import HTML_TEMPLATE

logger = config.get_logger("html_generator")

def parse_markdown_to_premium_html(md_path, today_str):
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Clean executive summary
    exec_summary_match = re.search(r'## Executive Summary\n(.*?)(?=\n##|$)', md_content, re.DOTALL)
    exec_summary_html = ""
    if exec_summary_match:
        summary_text = exec_summary_match.group(1).strip()
        exec_summary_html = f"""
        <div class="executive-summary">
            <h2>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-purple);"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                Executive Intelligence Summary
            </h2>
            <p>{html_escape(summary_text)}</p>
        </div>
        """
        md_content = md_content.replace(exec_summary_match.group(0), "")

    # Clean main title
    md_content = re.sub(r'^#\s+Daily Security Intelligence Briefing.*?\n', '', md_content, flags=re.IGNORECASE)

    # Clean references
    ref_match = re.search(r'## References\n(.*?)$', md_content, re.DOTALL)
    ref_html = ""
    if ref_match:
        ref_text = ref_match.group(1).strip()
        ref_lines = [line.strip() for line in ref_text.split('\n') if line.strip()]
        ref_items = []
        for line in ref_lines:
            link_match = re.search(r'\[(.*?)\]\((.*?)\)', line)
            if link_match:
                title, url = link_match.groups()
                ref_items.append(f'<li><a href="{_safe_link(url)}" target="_blank">🔗 {html_escape(title)}</a></li>')
            elif line.startswith("-") or line.startswith("*"):
                ref_items.append(f'<li>{html_escape(line[1:].strip())}</li>')
            else:
                ref_items.append(f'<li>{html_escape(line)}</li>')
        
        ref_html = f"""
        <div class="references">
            <h2>🔗 References & Advisory Links</h2>
            <ul>
                {"".join(ref_items)}
            </ul>
        </div>
        """
        md_content = md_content.replace(ref_match.group(0), "")

    # Split exclusively by Category sections (## Category: WEB)
    sections = re.split(r'\n##\s+Category:\s*', '\n' + md_content, flags=re.IGNORECASE)
    
    body_html_parts = []
    
    if exec_summary_html:
        body_html_parts.append(exec_summary_html)

    critical_count = 0
    high_count = 0
    total_count = 0

    seen_articles = {}  # key: norm_key -> dict of article metadata & rendered content
    article_keys_order = []

    for section in sections:
        if not section.strip():
            continue
        
        lines = section.strip().split('\n')
        raw_cat = lines[0].strip()
        category_name = re.sub(r'^(#+|\s*category:|\s*)+', '', raw_cat, flags=re.IGNORECASE).strip().upper()
        
        if not category_name or len(category_name) > 30:
            continue

        category_content = "\n".join(lines[1:])
        articles = re.split(r'\n###\s+', '\n' + category_content)
        
        for art in articles:
            if not art.strip():
                continue
            
            art_lines = art.strip().split('\n')
            art_title = art_lines[0].strip()
            art_body = "\n".join(art_lines[1:])
            
            source_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?Source(?:\*\*)?:\s*(.*)', art_body, re.IGNORECASE)
            rank_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?(?:Priority\s+)?Rank(?:\*\*)?:\s*`?(\d+)/10`?', art_body, re.IGNORECASE)
            link_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?Link(?:\*\*)?:\s*(?:\[.*?\]\()?([^\s)]+)', art_body, re.IGNORECASE)
            tags_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?(?:Pentester\s+)?Category(?:\s+Tags)?(?:\*\*)?:\s*(.*)', art_body, re.IGNORECASE)
            if not tags_match:
                tags_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?Tags(?:\*\*)?:\s*(.*)', art_body, re.IGNORECASE)
            
            source = source_match.group(1).strip().strip('*_` ') if source_match else "Security Advisory"
            rank_str = rank_match.group(1).strip() if rank_match else "5"
            rank_num = int(rank_str) if rank_str.isdigit() else 5
            link = link_match.group(1).strip().strip('*_`()[] ') if link_match else "#"

            tags = []
            if tags_match:
                tags = [t.strip().strip('`#_* ').lower() for t in re.split(r'[,\s]+', tags_match.group(1)) if t.strip()]
            else:
                tags = [category_name.lower()]

            norm_key = (art_title.strip().lower(), link.strip().lower())
            if norm_key in seen_articles:
                # Merge secondary tags into existing post card
                for t in tags:
                    if t not in seen_articles[norm_key]["tags"]:
                        seen_articles[norm_key]["tags"].append(t)
                continue

            cleaned_art_body = art_body
            for m_match in [source_match, rank_match, link_match, tags_match]:
                if m_match:
                    cleaned_art_body = cleaned_art_body.replace(m_match.group(0), "")
            
            cleaned_art_body = re.sub(r'^\s*[-*]\s*\n', '', cleaned_art_body, flags=re.MULTILINE).strip()

            headers_list = [
                "Description & Context",
                "TTPs & Exploitation Vectors",
                "Pentesting Value & Testing Method",
                "Threat Modeling & Secure Design Lesson",
                "Remediation"
            ]
            for h in headers_list:
                pattern = r'\*\*' + re.escape(h) + r'\*\*:\s*(\S)'
                cleaned_art_body = re.sub(pattern, r'**' + h + r'**:\n\n\1', cleaned_art_body, flags=re.IGNORECASE)

            # Extract Threat Modeling block cleanly
            threat_block_match = re.search(r'\*\*Threat Modeling & Secure Design Lesson\*\*:\s*(.*?)(?=\*\*Dependency & Package Ecosystem Details\*\*|\*\*Developer PR Review Checklist\*\*|\*\*Remediation\*\*|$)', cleaned_art_body, re.DOTALL | re.IGNORECASE)
            threat_box_html = ""
            if threat_block_match:
                raw_threat = threat_block_match.group(1).strip()
                threat_box_html = format_threat_modeling_box(raw_threat)
                if threat_box_html:
                    cleaned_art_body = cleaned_art_body.replace(threat_block_match.group(0), "")

            # Extract Dependency Ecosystem Details block
            eco_block_match = re.search(r'\*\*Dependency & Package Ecosystem Details\*\*:\s*(.*?)(?=\*\*Developer PR Review Checklist\*\*|\*\*Remediation\*\*|$)', cleaned_art_body, re.DOTALL | re.IGNORECASE)
            eco_box_html = ""
            if eco_block_match:
                raw_eco = eco_block_match.group(1).strip()
                eco_box_html = format_ecosystem_box(raw_eco)
                if eco_box_html:
                    cleaned_art_body = cleaned_art_body.replace(eco_block_match.group(0), "")

            # Extract Developer PR Review Checklist block
            checklist_block_match = re.search(r'\*\*Developer PR Review Checklist\*\*:\s*(.*?)(?=\*\*Remediation\*\*|$)', cleaned_art_body, re.DOTALL | re.IGNORECASE)
            checklist_box_html = ""
            if checklist_block_match:
                raw_checklist = checklist_block_match.group(1).strip()
                checklist_box_html = format_dev_checklist_box(raw_checklist)
                if checklist_box_html:
                    cleaned_art_body = cleaned_art_body.replace(checklist_block_match.group(0), "")

            rendered_body = markdown.markdown(cleaned_art_body)
            rendered_body = format_article_sections(rendered_body)

            # FALLBACK POST-MARKDOWN CHECK: If Threat Modeling wasn't caught pre-markdown, catch it post-markdown!
            if not threat_box_html:
                post_threat_match = re.search(r'(?:<p><strong>|<div[^>]*>)Threat Modeling &amp; Secure Design Lesson.*?(?:<\/strong><\/p>|<\/div>)(.*?)(?=<div class="section-header">|<h2>|<h3|<\/div>\s*<\/div>|$)', rendered_body, re.DOTALL | re.IGNORECASE)
                if post_threat_match:
                    raw_post_threat = post_threat_match.group(1).strip()
                    threat_box_html = format_threat_modeling_box(raw_post_threat)
                    if threat_box_html:
                        rendered_body = rendered_body.replace(post_threat_match.group(0), "")

            # Store unique article details (sanitized -- everything above comes from
            # untrusted RSS feed / LLM output)
            seen_articles[norm_key] = {
                "title": html_escape(art_title),
                "source": html_escape(source),
                "rank_num": rank_num,
                "link": _safe_link(link),
                "tags": tags,
                "category": category_name,
                "rendered_body": _sanitize_html(rendered_body),
                "threat_box_html": _sanitize_html(threat_box_html),
                "eco_box_html": _sanitize_html(eco_box_html),
                "checklist_box_html": _sanitize_html(checklist_box_html)
            }
            article_keys_order.append(norm_key)

    # Group unique articles by category and build HTML cards
    category_grouped_html = {}
    for key in article_keys_order:
        art_info = seen_articles[key]
        rank_num = art_info["rank_num"]
        
        total_count += 1
        if rank_num >= 8:
            critical_count += 1
        elif rank_num >= 6:
            high_count += 1

        tags_html = "".join([f'<span class="tag-pill tag-{_safe_slug(t)}">{html_escape(t)}</span>' for t in art_info["tags"]])
        
        if rank_num >= 8:
            rank_class = "rank-critical"
            card_extra_class = "critical-card"
        elif rank_num >= 6:
            rank_class = "rank-high"
            card_extra_class = ""
        else:
            rank_class = "rank-medium"
            card_extra_class = ""

        full_body = art_info["rendered_body"]
        if art_info["threat_box_html"]:
            full_body += art_info["threat_box_html"]
        if art_info["eco_box_html"]:
            full_body += art_info["eco_box_html"]
        if art_info["checklist_box_html"]:
            full_body += art_info["checklist_box_html"]

        card_html = f"""
        <div class="article-card {card_extra_class}">
            <div class="article-header">
                <a href="{art_info['link']}" class="article-title-link" target="_blank">{art_info['title']}</a>
                <span class="rank-badge {rank_class}">Rank {rank_num}/10</span>
            </div>
            <div class="article-meta">
                <span class="meta-source">📍 {art_info['source']}</span>
                <span class="meta-separator">•</span>
                <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                    {tags_html}
                </div>
            </div>
            <div class="article-content">
                {full_body}
            </div>
        </div>
        """
        cat = art_info["category"]
        if cat not in category_grouped_html:
            category_grouped_html[cat] = []
        category_grouped_html[cat].append(card_html)

    for cat_name, cards_list in category_grouped_html.items():
        section_html = f"""
        <section class="category-section" id="category-{_safe_slug(cat_name)}">
            <h2 class="category-title">🎯 {html_escape(cat_name)} Focus</h2>
            {"".join(cards_list)}
        </section>
        """
        body_html_parts.append(section_html)

    if ref_html:
        body_html_parts.append(ref_html)

    complete_body_html = "\n".join(body_html_parts)
    
    if len(body_html_parts) <= 1:
        logger.info("Direct markdown conversion (no categories found).")
        direct_html = _sanitize_html(markdown.markdown(md_content))
        complete_body_html = (exec_summary_html if exec_summary_html else "") + f'<div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 18px; padding: 2rem;">{direct_html}</div>' + (ref_html if ref_html else "")

    return HTML_TEMPLATE.format(
        date=today_str,
        content=complete_body_html,
        critical_count=critical_count,
        high_count=high_count,
        total_count=total_count
    )

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    md_report_file = config.REPORTS_DIR / f"daily_brief_{today_str}.md"

    if not md_report_file.exists():
        # Fallback to the latest markdown briefing in REPORTS_DIR
        md_files = sorted(list(config.REPORTS_DIR.glob("daily_brief_*.md")), reverse=True)
        if md_files:
            md_report_file = md_files[0]
            today_str = md_report_file.stem.replace("daily_brief_", "")
            logger.info(f"Today's brief not found. Falling back to latest brief: {md_report_file}")
        else:
            logger.error(f"No Markdown report files found in {config.REPORTS_DIR}")
            sys.exit(1)

    html_report_file = config.REPORTS_DIR / f"daily_brief_{today_str}.html"

    logger.info(f"Loading Markdown report from {md_report_file}...")
    try:
        html_content = parse_markdown_to_premium_html(md_report_file, today_str)
        with open(html_report_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        index_report_file = config.REPORTS_DIR / "index.html"
        with open(index_report_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Successfully generated HTML report at: {html_report_file} and {index_report_file}")
    except Exception as e:
        logger.critical(f"Failed to generate HTML report: {e}")
        sys.exit(1)

    scripts_html_gen = config.BASE_DIR / "scripts" / "html_generator.py"
    if scripts_html_gen.exists() and str(Path(__file__).resolve()) != str(scripts_html_gen):
        try:
            with open(scripts_html_gen, "w", encoding="utf-8") as f:
                with open(__file__, "r", encoding="utf-8") as current:
                    f.write(current.read())
        except Exception:
            pass

if __name__ == "__main__":
    main()
