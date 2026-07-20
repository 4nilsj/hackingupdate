import sys
import re
from datetime import datetime
from pathlib import Path
import markdown

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

logger = config.get_logger("html_generator")

# Premium HTML Dark Mode Template with glassmorphism and interactive tag/search filtering
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Security Intelligence Briefing - {date}</title>
    <meta name="description" content="Technical daily briefing of security vulnerabilities, exploits, and pentester techniques.">
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;500;700&family=Fira+Code:wght@400;600&display=swap" rel="stylesheet">
    
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 31, 56, 0.6);
            --card-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-glow: #00f2fe;
            --accent-primary: #38bdf8;
            --accent-purple: #a855f7;
            --accent-danger: #ef4444;
            --tag-web: #3b82f6;
            --tag-mobile: #ec4899;
            --tag-api: #f97316;
            --tag-network: #10b981;
            --tag-thickclient: #8b5cf6;
            --tag-cloud: #06b6d4;
            --tag-infra: #64748b;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(at 10% 20%, rgba(56, 189, 248, 0.05) 0px, transparent 50%),
                radial-gradient(at 90% 80%, rgba(168, 85, 247, 0.05) 0px, transparent 50%);
            color: var(--text-primary);
            font-family: 'Outfit', sans-serif;
            line-height: 1.6;
            padding: 2rem 1rem;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}

        /* Header Styling */
        header {{
            text-align: center;
            margin-bottom: 3rem;
            position: relative;
        }}

        header h1 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 50%, #a855f7 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
            letter-spacing: -0.05em;
        }}

        header p.date {{
            font-size: 1.2rem;
            color: var(--text-secondary);
            font-weight: 400;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}

        header .badge {{
            display: inline-block;
            padding: 0.35rem 1rem;
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.3);
            color: var(--accent-primary);
            border-radius: 50px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-top: 1rem;
            text-transform: uppercase;
        }}

        /* Interactive Filter Bar */
        .filter-bar {{
            background: rgba(22, 31, 56, 0.4);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            padding: 1.2rem;
            border-radius: 16px;
            margin-bottom: 2.5rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}

        .search-box {{
            width: 100%;
            padding: 0.8rem 1.2rem;
            background: rgba(11, 15, 25, 0.8);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            color: var(--text-primary);
            font-size: 1rem;
            font-family: inherit;
            outline: none;
            transition: border-color 0.3s, box-shadow 0.3s;
        }}

        .search-box:focus {{
            border-color: var(--accent-primary);
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.2);
        }}

        .tags-filter {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            align-items: center;
        }}

        .filter-label {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            margin-right: 0.5rem;
            font-weight: 600;
        }}

        .btn-filter {{
            padding: 0.4rem 0.9rem;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
            color: var(--text-secondary);
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 500;
            transition: all 0.2s ease;
        }}

        .btn-filter:hover, .btn-filter.active {{
            background: var(--accent-primary);
            color: #0b0f19;
            border-color: var(--accent-primary);
            font-weight: 600;
        }}

        /* Executive Summary Section */
        .executive-summary {{
            background: linear-gradient(135deg, rgba(22, 31, 56, 0.8) 0%, rgba(168, 85, 247, 0.1) 100%);
            border: 1px solid rgba(168, 85, 247, 0.25);
            border-radius: 20px;
            padding: 2rem;
            margin-bottom: 3rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }}

        .executive-summary h2 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.6rem;
            color: #d8b4fe;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .executive-summary p {{
            font-size: 1.1rem;
            color: #e5e7eb;
        }}

        /* Category Card Styling */
        .category-section {{
            margin-bottom: 3rem;
        }}

        .category-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.8rem;
            color: var(--accent-primary);
            margin-bottom: 1.5rem;
            border-bottom: 2px solid rgba(56, 189, 248, 0.2);
            padding-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        /* Article Card */
        .article-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
            position: relative;
            overflow: hidden;
        }}

        .article-card:hover {{
            transform: translateY(-2px);
            border-color: rgba(56, 189, 248, 0.3);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        }}

        .article-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
            margin-bottom: 1rem;
        }}

        .article-title-link {{
            color: var(--text-primary);
            text-decoration: none;
            font-size: 1.3rem;
            font-weight: 700;
            line-height: 1.3;
            transition: color 0.2s;
        }}

        .article-title-link:hover {{
            color: var(--accent-primary);
        }}

        .rank-badge {{
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #f87171;
            padding: 0.25rem 0.6rem;
            font-size: 0.8rem;
            font-weight: 700;
            border-radius: 6px;
            white-space: nowrap;
        }}

        .rank-high {{
            background: rgba(239, 68, 68, 0.2);
            border-color: #ef4444;
            color: #fca5a5;
        }}

        .article-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.8rem;
            align-items: center;
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 1rem;
        }}

        .meta-source {{
            font-weight: 600;
            color: #d1d5db;
        }}

        /* Tag Pill Styling */
        .tag-pill {{
            padding: 0.15rem 0.5rem;
            font-size: 0.75rem;
            font-weight: 700;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .tag-web {{ background: rgba(59, 130, 246, 0.15); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .tag-mobile {{ background: rgba(236, 72, 153, 0.15); color: #f9a8d4; border: 1px solid rgba(236, 72, 153, 0.3); }}
        .tag-api {{ background: rgba(249, 115, 22, 0.15); color: #fdba74; border: 1px solid rgba(249, 115, 22, 0.3); }}
        .tag-network {{ background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .tag-thickclient {{ background: rgba(139, 92, 246, 0.15); color: #c4b5fd; border: 1px solid rgba(139, 92, 246, 0.3); }}
        .tag-cloud {{ background: rgba(6, 182, 212, 0.15); color: #67e8f9; border: 1px solid rgba(6, 182, 212, 0.3); }}
        .tag-infra {{ background: rgba(100, 116, 139, 0.15); color: #cbd5e1; border: 1px solid rgba(100, 116, 139, 0.3); }}

        /* Collapsible Section Layout */
        .article-content {{
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-top: 1rem;
            margin-top: 1rem;
        }}

        .section-header {{
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--accent-primary);
            text-transform: uppercase;
            margin-top: 1rem;
            margin-bottom: 0.4rem;
            letter-spacing: 0.05em;
        }}

        .article-content p {{
            font-size: 0.95rem;
            color: #d1d5db;
            margin-bottom: 1rem;
        }}

        /* References / Footer */
        .references {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 1.5rem 2rem;
            margin-top: 4rem;
        }}

        .references h2 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.4rem;
            color: var(--accent-primary);
            margin-bottom: 1rem;
        }}

        .references ul {{
            list-style-type: none;
        }}

        .references li {{
            margin-bottom: 0.6rem;
            font-size: 0.9rem;
        }}

        .references a {{
            color: var(--text-secondary);
            text-decoration: none;
            transition: color 0.2s;
        }}

        .references a:hover {{
            color: var(--accent-primary);
            text-decoration: underline;
        }}

        footer {{
            text-align: center;
            margin-top: 4rem;
            padding-top: 2rem;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}

        footer a {{
            color: var(--accent-primary);
            text-decoration: none;
        }}

        /* Responsive Breakpoints */
        @media (max-width: 768px) {{
            body {{
                padding: 1rem 0.5rem;
            }}
            header h1 {{
                font-size: 2.2rem;
            }}
            .article-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 0.5rem;
            }}
            .rank-badge {{
                align-self: flex-start;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="badge">Threat Intelligence</div>
            <h1>Daily Security Intelligence Briefing</h1>
            <p class="date">{date}</p>
        </header>

        <!-- Interactive Filtering and Search -->
        <div class="filter-bar">
            <input type="text" id="searchInput" class="search-box" placeholder="Search by title, description, keywords, or TTPs...">
            <div class="tags-filter">
                <span class="filter-label">Filter by Focus:</span>
                <button class="btn-filter active" onclick="filterTag('all')">All</button>
                <button class="btn-filter" onclick="filterTag('web')">Web</button>
                <button class="btn-filter" onclick="filterTag('mobile')">Mobile</button>
                <button class="btn-filter" onclick="filterTag('api')">API</button>
                <button class="btn-filter" onclick="filterTag('network')">Network</button>
                <button class="btn-filter" onclick="filterTag('thickclient')">Thick Client</button>
                <button class="btn-filter" onclick="filterTag('cloud')">Cloud</button>
                <button class="btn-filter" onclick="filterTag('infra')">Infra</button>
            </div>
        </div>

        {content}

        <footer>
            <p>Generated by <strong>HackingUpdate AI Agent</strong>. Curated for Security Professionals.</p>
        </footer>
    </div>

    <!-- Client-side Interactive Filter Script -->
    <script>
        const searchInput = document.getElementById('searchInput');
        let currentTag = 'all';

        searchInput.addEventListener('input', () => {{
            filterItems();
        }});

        function filterTag(tag) {{
            // Update active state of buttons
            const buttons = document.querySelectorAll('.btn-filter');
            buttons.forEach(btn => {{
                if (btn.textContent.toLowerCase() === tag.toLowerCase() || (tag === 'all' && btn.textContent.toLowerCase() === 'all')) {{
                    btn.classList.add('active');
                }} else {{
                    btn.classList.remove('active');
                }}
            }});
            currentTag = tag;
            filterItems();
        }}

        function filterItems() {{
            const query = searchInput.value.toLowerCase();
            const cards = document.querySelectorAll('.article-card');

            cards.forEach(card => {{
                const title = card.querySelector('.article-title-link').textContent.toLowerCase();
                const content = card.textContent.toLowerCase();
                const tags = Array.from(card.querySelectorAll('.tag-pill')).map(t => t.textContent.toLowerCase());
                
                const matchesSearch = title.includes(query) || content.includes(query);
                const matchesTag = currentTag === 'all' || tags.includes(currentTag.toLowerCase());

                if (matchesSearch && matchesTag) {{
                    card.style.display = 'block';
                    // If card is inside a category section, ensure the category section is visible
                    const section = card.closest('.category-section');
                    if (section) section.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});

            // Hide category sections that have no visible cards
            const sections = document.querySelectorAll('.category-section');
            sections.forEach(section => {{
                const visibleCards = section.querySelectorAll('.article-card[style="display: block;"], .article-card:not([style*="display: none"])');
                if (visibleCards.length === 0) {{
                    section.style.display = 'none';
                }} else {{
                    section.style.display = 'block';
                }}
            }});
        }}
    </script>
</body>
</html>
"""

def parse_markdown_to_premium_html(md_path, today_str):
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # We need to parse structural parts of markdown:
    # 1. Executive summary block:
    # Let's extract any content between "## Executive Summary" and the next "##" heading.
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
            <p>{summary_text}</p>
        </div>
        """
        # Remove executive summary from md_content to avoid duplicate rendering
        md_content = md_content.replace(exec_summary_match.group(0), "")

    # Clean the first H1 title from content as it is in the header template
    md_content = re.sub(r'^#\s+Daily Security Intelligence Briefing.*?\n', '', md_content, flags=re.IGNORECASE)

    # Let's extract References section
    ref_match = re.search(r'## References\n(.*?)$', md_content, re.DOTALL)
    ref_html = ""
    if ref_match:
        ref_text = ref_match.group(1).strip()
        # Convert links to li tags
        ref_lines = [line.strip() for line in ref_text.split('\n') if line.strip()]
        ref_items = []
        for line in ref_lines:
            # Parse markdown link formats: - [Title](url) or * [Title](url) or [Title](url)
            link_match = re.search(r'\[(.*?)\]\((.*?)\)', line)
            if link_match:
                title, url = link_match.groups()
                ref_items.append(f'<li><a href="{url}" target="_blank">🔗 {title}</a></li>')
            elif line.startswith("-") or line.startswith("*"):
                ref_items.append(f'<li>{line[1:].strip()}</li>')
            else:
                ref_items.append(f'<li>{line}</li>')
        
        ref_html = f"""
        <div class="references">
            <h2>References & Advisory Links</h2>
            <ul>
                {"".join(ref_items)}
            </ul>
        </div>
        """
        md_content = md_content.replace(ref_match.group(0), "")

    # Now, let's extract sections for categories (## Category: WEB) and their subheadings
    # We will segment the markdown into Category Sections, and parse each article block.
    # To do this cleanly, let's split by "## Category:" or "##" lines.
    sections = re.split(r'##\s+Category:\s*', md_content, flags=re.IGNORECASE)
    
    body_html_parts = []
    
    # Add Executive summary
    if exec_summary_html:
        body_html_parts.append(exec_summary_html)

    for section in sections:
        if not section.strip():
            continue
        
        # The section starts with the category name on the first line
        lines = section.strip().split('\n')
        category_name = lines[0].strip()
        category_content = "\n".join(lines[1:])
        
        # Let's split category_content by articles (marked by "###")
        articles = re.split(r'###\s+', category_content)
        
        category_html_cards = []
        
        for art in articles:
            if not art.strip():
                continue
            
            art_lines = art.strip().split('\n')
            art_title = art_lines[0].strip()
            art_body = "\n".join(art_lines[1:])
            
            # Extract metadata bullet points
            # e.g., - Source: PortSwigger
            # - Rank: 8/10
            # - Link: http://...
            # - Tags: web, API
            # Robust metadata extraction supporting both bold/plain text and hyphen/asterisk markers
            source_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?Source(?:\*\*)?:\s*(.*)', art_body, re.IGNORECASE)
            rank_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?(?:Priority\s+)?Rank(?:\*\*)?:\s*`?(\d+)/10`?', art_body, re.IGNORECASE)
            link_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?Link(?:\*\*)?:\s*(?:\[.*?\]\()?([^\s)]+)', art_body, re.IGNORECASE)
            
            # Robust tag matching (supporting Tags, Category, Pentester Category Tags, etc.)
            tags_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?(?:Pentester\s+)?Category(?:\s+Tags)?(?:\*\*)?:\s*(.*)', art_body, re.IGNORECASE)
            if not tags_match:
                tags_match = re.search(r'(?:[-*]\s+)?(?:\*\*)?Tags(?:\*\*)?:\s*(.*)', art_body, re.IGNORECASE)
            
            source = source_match.group(1).strip().strip('*_` ') if source_match else "Unknown Source"
            rank_str = rank_match.group(1).strip() if rank_match else "5"
            rank_num = int(rank_str) if rank_str.isdigit() else 5
            link = link_match.group(1).strip().strip('*_`()[] ') if link_match else "#"
            
            tags = []
            if tags_match:
                # Extract words/tags, stripping punctuation
                tags = [t.strip().strip('`#_* ').lower() for t in re.split(r'[,\s]+', tags_match.group(1)) if t.strip()]
            else:
                # Default tag from category name
                tags = [category_name.lower()]

            # Clean metadata block out of the article body to avoid displaying it raw
            cleaned_art_body = art_body
            for m_match in [source_match, rank_match, link_match, tags_match]:
                if m_match:
                    cleaned_art_body = cleaned_art_body.replace(m_match.group(0), "")
            
            # Clean up remaining empty markdown list items (hyphens or asterisks) or spacing
            cleaned_art_body = re.sub(r'^\s*[-*]\s*\n', '', cleaned_art_body, flags=re.MULTILINE)
            cleaned_art_body = cleaned_art_body.strip()

            # Programmatically guarantee double newlines before lists/text under headers
            headers_list = [
                "Description & Context",
                "TTPs & Exploitation Vectors",
                "Pentesting Value & Testing Method",
                "Threat Modeling & Secure Design Lesson",
                "Remediation"
            ]
            for h in headers_list:
                # Match: **h**: followed by a single newline, then optional spaces and a non-newline character
                pattern = r'\*\*' + re.escape(h) + r'\*\*:\s*\n\s*(\S)'
                cleaned_art_body = re.sub(pattern, r'**' + h + r'**:\n\n\1', cleaned_art_body, flags=re.IGNORECASE)

            # Render HTML for article body using Python markdown
            rendered_body = markdown.markdown(cleaned_art_body)
            
            # Insert styled details section headers dynamically
            headers_to_style = {
                "Description &amp; Context": "Description & Context",
                "TTPs &amp; Exploitation Vectors": "TTPs & Exploitation Vectors",
                "Pentesting Value &amp; Testing Method": "Pentesting Value & Testing Method",
                "Threat Modeling &amp; Secure Design Lesson": "Threat Modeling & Secure Design Lesson",
                "Remediation": "Remediation"
            }
            
            for key, val in headers_to_style.items():
                header_style = ' style="color: var(--accent-purple); border-bottom: 1px solid rgba(168, 85, 247, 0.3); margin-top: 1.5rem;"' if "Threat" in val else ""
                
                # Match inline text in same paragraph (captured text must start with non-colon, non-whitespace character)
                rendered_body = re.sub(
                    r'<p><strong>' + key + r'</strong>(?::|\s)*\s*([^:\s].*?)</p>',
                    r'<div class="section-header"' + header_style + r'>' + val + r'</div><p>\1</p>',
                    rendered_body,
                    flags=re.IGNORECASE
                )
                # Match headers followed directly by nested tags (lists)
                rendered_body = re.sub(
                    r'<p><strong>' + key + r'</strong>(?::|\s)*\s*</p>',
                    r'<div class="section-header"' + header_style + r'>' + val + r'</div>',
                    rendered_body,
                    flags=re.IGNORECASE
                )
            
            # Setup tags pill HTML
            tags_html = "".join([f'<span class="tag-pill tag-{t}">{t}</span>' for t in tags])
            
            # Add Rank Styling class
            rank_class = "rank-high" if rank_num >= 8 else ""

            # Build article card
            card_html = f"""
            <div class="article-card">
                <div class="article-header">
                    <a href="{link}" class="article-title-link" target="_blank">{art_title}</a>
                    <span class="rank-badge {rank_class}">Rank {rank_num}/10</span>
                </div>
                <div class="article-meta">
                    <span class="meta-source">📍 {source}</span>
                    <span class="meta-separator">•</span>
                    <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
                        {tags_html}
                    </div>
                </div>
                <div class="article-content">
                    {rendered_body}
                </div>
            </div>
            """
            category_html_cards.append(card_html)
            
        if category_html_cards:
            section_html = f"""
            <section class="category-section" id="category-{category_name.lower()}">
                <h2 class="category-title">{category_name} Focus</h2>
                {"".join(category_html_cards)}
            </section>
            """
            body_html_parts.append(section_html)

    # Add References
    if ref_html:
        body_html_parts.append(ref_html)

    complete_body_html = "\n".join(body_html_parts)
    
    # If no structured categories were parsed (e.g., in fallback local report), just render the direct markdown
    if len(body_html_parts) <= 1:
        logger.info("Direct markdown conversion (no categories found).")
        direct_html = markdown.markdown(md_content)
        complete_body_html = (exec_summary_html if exec_summary_html else "") + f'<div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 16px; padding: 2rem;">{direct_html}</div>' + (ref_html if ref_html else "")

    return HTML_TEMPLATE.format(date=today_str, content=complete_body_html)

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    md_report_file = config.REPORTS_DIR / f"daily_brief_{today_str}.md"
    html_report_file = config.REPORTS_DIR / f"daily_brief_{today_str}.html"

    if not md_report_file.exists():
        logger.error(f"Markdown report file not found: {md_report_file}")
        sys.exit(1)

    logger.info(f"Loading Markdown report from {md_report_file}...")
    try:
        html_content = parse_markdown_to_premium_html(md_report_file, today_str)
        with open(html_report_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Successfully generated HTML report at: {html_report_file}")
    except Exception as e:
        logger.critical(f"Failed to generate HTML report: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
