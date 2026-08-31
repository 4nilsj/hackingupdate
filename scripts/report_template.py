"""HTML report shell: page structure, CSS, and client-side search/filter JS.

Kept separate from html_generator.py so the templating/presentation layer
does not mix with the markdown parsing and content-formatting logic.
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Security Intelligence Briefing - {date}</title>
    <meta name="description" content="Technical daily briefing of security vulnerabilities, exploits, and pentester TTPs.">
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(19, 27, 46, 0.7);
            --card-hover-bg: rgba(25, 36, 62, 0.85);
            --card-border: rgba(255, 255, 255, 0.07);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-primary: #38bdf8;
            --accent-purple: #c084fc;
            --accent-danger: #ef4444;
            --accent-warning: #f59e0b;
            --accent-success: #10b981;
            
            --tag-web: #3b82f6;
            --tag-mobile: #ec4899;
            --tag-api: #f97316;
            --tag-network: #10b981;
            --tag-thickclient: #a855f7;
            --tag-cloud: #06b6d4;
            --tag-infra: #64748b;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        @keyframes pulseGlow {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(1.25); }}
        }}

        body {{
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(circle at 12% 12%, rgba(56, 189, 248, 0.07) 0px, transparent 40%),
                radial-gradient(circle at 88% 88%, rgba(192, 132, 252, 0.07) 0px, transparent 40%);
            color: var(--text-primary);
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.6;
            padding: 2.5rem 1rem;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1040px;
            margin: 0 auto;
            animation: fadeIn 0.4s ease-out;
        }}

        /* Header Styling */
        header {{
            text-align: center;
            margin-bottom: 2.5rem;
        }}

        header .header-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.4rem 1.1rem;
            background: rgba(56, 189, 248, 0.08);
            border: 1px solid rgba(56, 189, 248, 0.25);
            color: var(--accent-primary);
            border-radius: 50px;
            font-size: 0.82rem;
            font-weight: 700;
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}

        header .badge-pulse {{
            width: 8px;
            height: 8px;
            background: var(--accent-primary);
            border-radius: 50%;
            animation: pulseGlow 2s infinite ease-in-out;
        }}

        header h1 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #00f2fe 0%, #38bdf8 45%, #c084fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.4rem;
            letter-spacing: -0.03em;
            line-height: 1.15;
        }}

        header p.date {{
            font-size: 1.05rem;
            color: var(--text-secondary);
            font-weight: 500;
            letter-spacing: 0.03em;
        }}

        /* Metrics Banner */
        .metrics-banner {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2.5rem;
        }}

        .metric-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 16px;
            padding: 1.1rem 1.3rem;
            display: flex;
            align-items: center;
            gap: 1rem;
            transition: border-color 0.2s, transform 0.2s;
        }}

        .metric-card:hover {{
            border-color: rgba(56, 189, 248, 0.3);
            transform: translateY(-2px);
        }}

        .metric-icon {{
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.3rem;
            flex-shrink: 0;
        }}

        .metric-icon.critical {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .metric-icon.high {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .metric-icon.total {{ background: rgba(56, 189, 248, 0.15); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.3); }}
        .metric-icon.fresh {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}

        .metric-info .val {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.55rem;
            font-weight: 800;
            color: var(--text-primary);
            line-height: 1;
            margin-bottom: 0.2rem;
        }}

        .metric-info .lbl {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        /* Interactive Filter Bar */
        .filter-bar {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            padding: 1.3rem 1.4rem;
            border-radius: 18px;
            margin-bottom: 2.5rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        }}

        .search-wrapper {{
            position: relative;
            width: 100%;
        }}

        .search-box {{
            width: 100%;
            padding: 0.8rem 1.2rem 0.8rem 2.8rem;
            background: rgba(9, 13, 22, 0.9);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            color: var(--text-primary);
            font-size: 0.95rem;
            font-family: inherit;
            outline: none;
            transition: border-color 0.3s, box-shadow 0.3s;
        }}

        .search-icon {{
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            pointer-events: none;
        }}

        .search-shortcut {{
            position: absolute;
            right: 1rem;
            top: 50%;
            transform: translateY(-50%);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-muted);
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--card-border);
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
        }}

        .search-box:focus {{
            border-color: var(--accent-primary);
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.25);
        }}

        .filter-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            align-items: center;
        }}

        .filter-label {{
            font-size: 0.82rem;
            color: var(--text-secondary);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-right: 0.4rem;
        }}

        .btn-filter {{
            padding: 0.38rem 0.85rem;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--card-border);
            color: var(--text-secondary);
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.83rem;
            font-weight: 600;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }}

        .btn-filter:hover {{
            background: rgba(56, 189, 248, 0.15);
            color: var(--accent-primary);
            border-color: rgba(56, 189, 248, 0.4);
        }}

        .btn-filter.active {{
            background: var(--accent-primary);
            color: #090d16;
            border-color: var(--accent-primary);
            font-weight: 700;
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.35);
        }}

        .filter-status {{
            font-size: 0.83rem;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
            margin-top: 0.1rem;
        }}

        /* Executive Summary Section */
        .executive-summary {{
            background: linear-gradient(135deg, rgba(19, 27, 46, 0.95) 0%, rgba(192, 132, 252, 0.1) 100%);
            border: 1px solid rgba(192, 132, 252, 0.3);
            border-radius: 18px;
            padding: 1.8rem 2rem;
            margin-bottom: 3rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            position: relative;
            overflow: hidden;
        }}

        .executive-summary::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(180deg, var(--accent-primary), var(--accent-purple));
        }}

        .executive-summary h2 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.45rem;
            color: #e9d5ff;
            margin-bottom: 0.9rem;
            display: flex;
            align-items: center;
            gap: 0.6rem;
            letter-spacing: -0.02em;
        }}

        .executive-summary p {{
            font-size: 1.02rem;
            color: #cbd5e1;
            line-height: 1.7;
        }}

        /* Category Section */
        .category-section {{
            margin-bottom: 3rem;
        }}

        .category-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.55rem;
            color: var(--accent-primary);
            margin-bottom: 1.4rem;
            border-bottom: 1px solid rgba(56, 189, 248, 0.2);
            padding-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }}

        /* Article Card */
        .article-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 16px;
            padding: 1.6rem;
            margin-bottom: 1.5rem;
            transition: all 0.25s ease;
            position: relative;
        }}

        .article-card:hover {{
            background: var(--card-hover-bg);
            border-color: rgba(56, 189, 248, 0.35);
            transform: translateY(-2px);
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35), 0 0 16px rgba(56, 189, 248, 0.1);
        }}

        .article-card.critical-card {{
            border-left: 4px solid var(--accent-danger);
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.05) 0%, rgba(19, 27, 46, 0.75) 100%);
        }}

        .article-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1.2rem;
            margin-bottom: 0.8rem;
        }}

        .article-title-link {{
            color: var(--text-primary);
            text-decoration: none;
            font-size: 1.25rem;
            font-weight: 700;
            line-height: 1.35;
            transition: color 0.2s;
        }}

        .article-title-link:hover {{
            color: var(--accent-primary);
        }}

        .rank-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.28rem 0.7rem;
            font-size: 0.8rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            border-radius: 8px;
            white-space: nowrap;
            flex-shrink: 0;
        }}

        .rank-critical {{
            background: rgba(239, 68, 68, 0.16);
            border: 1px solid rgba(239, 68, 68, 0.45);
            color: #fca5a5;
        }}

        .rank-high {{
            background: rgba(245, 158, 11, 0.16);
            border: 1px solid rgba(245, 158, 11, 0.45);
            color: #fde047;
        }}

        .rank-medium {{
            background: rgba(56, 189, 248, 0.14);
            border: 1px solid rgba(56, 189, 248, 0.35);
            color: #7dd3fc;
        }}

        .article-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            align-items: center;
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 1.2rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .meta-source {{
            font-weight: 600;
            color: #cbd5e1;
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
        }}

        .meta-separator {{
            color: var(--text-muted);
        }}

        /* Tag Pill Styling */
        .tag-pill {{
            padding: 0.18rem 0.55rem;
            font-size: 0.72rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            border-radius: 5px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .tag-web {{ background: rgba(59, 130, 246, 0.15); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .tag-mobile {{ background: rgba(236, 72, 153, 0.15); color: #f9a8d4; border: 1px solid rgba(236, 72, 153, 0.3); }}
        .tag-api {{ background: rgba(249, 115, 22, 0.15); color: #fdba74; border: 1px solid rgba(249, 115, 22, 0.3); }}
        .tag-network {{ background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .tag-thickclient {{ background: rgba(168, 85, 247, 0.15); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.3); }}
        .tag-cloud {{ background: rgba(6, 182, 212, 0.15); color: #67e8f9; border: 1px solid rgba(6, 182, 212, 0.3); }}
        .tag-infra {{ background: rgba(100, 116, 139, 0.15); color: #cbd5e1; border: 1px solid rgba(100, 116, 139, 0.3); }}
        .tag-news {{ background: rgba(234, 179, 8, 0.15); color: #fde047; border: 1px solid rgba(234, 179, 8, 0.3); }}
        .tag-npm {{ background: rgba(203, 60, 60, 0.15); color: #f87171; border: 1px solid rgba(203, 60, 60, 0.3); }}
        .tag-pypi {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }}
        .tag-go {{ background: rgba(0, 173, 181, 0.15); color: #00adb5; border: 1px solid rgba(0, 173, 181, 0.3); }}
        .tag-maven {{ background: rgba(243, 156, 18, 0.15); color: #f39c12; border: 1px solid rgba(243, 156, 18, 0.3); }}
        .tag-cargo {{ background: rgba(230, 126, 34, 0.15); color: #e67e22; border: 1px solid rgba(230, 126, 34, 0.3); }}

        /* Ecosystem Box */
        .ecosystem-card-box {{
            background: rgba(56, 189, 248, 0.05);
            border: 1px solid rgba(56, 189, 248, 0.2);
            border-left: 4px solid var(--accent-primary);
            border-radius: 12px;
            padding: 1rem;
            margin-top: 1rem;
        }}

        .ecosystem-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 0.75rem;
        }}

        .ecosystem-item {{
            display: flex;
            flex-direction: column;
            gap: 0.2rem;
        }}

        .ecosystem-key {{
            font-size: 0.7rem;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 800;
            color: var(--accent-primary);
            text-transform: uppercase;
        }}

        .ecosystem-val {{
            font-size: 0.9rem;
            color: #cbd5e1;
            font-weight: 600;
        }}

        /* Developer PR Checklist Box */
        .dev-checklist-box {{
            background: rgba(16, 185, 129, 0.05);
            border: 1px solid rgba(16, 185, 129, 0.25);
            border-left: 4px solid var(--accent-success);
            border-radius: 12px;
            padding: 1.1rem;
            margin-top: 1.1rem;
        }}

        .dev-checklist-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.95rem;
            font-weight: 800;
            color: #a7f3d0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.6rem;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }}

        .dev-checklist-list {{
            list-style-type: none;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            margin-left: 0 !important;
        }}

        .dev-checklist-item {{
            display: flex;
            align-items: flex-start;
            gap: 0.5rem;
            font-size: 0.92rem;
            color: #cbd5e1;
            line-height: 1.4;
        }}

        .dev-checklist-checkbox {{
            margin-top: 0.25rem;
            accent-color: var(--accent-success);
            cursor: not-allowed;
        }}

        /* Article Content Section Headers & Unified Point System */
        .article-content {{
            display: flex;
            flex-direction: column;
            gap: 0.85rem;
        }}

        .section-header {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.86rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-top: 1.1rem;
            margin-bottom: 0.5rem;
            padding: 0.42rem 0.85rem;
            border-radius: 9px;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            width: fit-content;
        }}

        .section-header.desc-hdr {{
            background: rgba(56, 189, 248, 0.09);
            color: var(--accent-primary);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-left: 4px solid var(--accent-primary);
        }}

        .section-header.ttps-hdr {{
            background: rgba(245, 158, 11, 0.09);
            color: #fde047;
            border: 1px solid rgba(245, 158, 11, 0.25);
            border-left: 4px solid var(--accent-warning);
        }}

        .section-header.pentest-hdr {{
            background: rgba(192, 132, 252, 0.09);
            color: #e9d5ff;
            border: 1px solid rgba(192, 132, 252, 0.25);
            border-left: 4px solid var(--accent-purple);
        }}

        .section-header.remediation-hdr {{
            background: rgba(16, 185, 129, 0.09);
            color: #6ee7b7;
            border: 1px solid rgba(16, 185, 129, 0.25);
            border-left: 4px solid var(--accent-success);
        }}

        /* Modern Point List Container & Cards */
        .point-list {{
            list-style: none !important;
            padding: 0 !important;
            margin: 0 0 0.8rem 0 !important;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .point-item {{
            display: flex;
            align-items: flex-start;
            gap: 0.65rem;
            background: rgba(15, 23, 42, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.06);
            padding: 0.7rem 0.95rem;
            border-radius: 10px;
            font-size: 0.94rem;
            color: #cbd5e1;
            line-height: 1.6;
            transition: all 0.2s ease;
        }}

        .point-item:hover {{
            background: rgba(15, 23, 42, 0.8);
            border-color: rgba(255, 255, 255, 0.14);
            transform: translateX(3px);
        }}

        .point-marker {{
            flex-shrink: 0;
            font-size: 0.9rem;
            font-weight: 800;
            line-height: 1.5;
        }}

        .point-marker.desc-marker {{ color: var(--accent-primary); }}
        .point-marker.ttps-marker {{ color: var(--accent-warning); }}
        .point-marker.pentest-marker {{ color: var(--accent-purple); }}
        .point-marker.remediation-marker {{ color: var(--accent-success); }}

        .point-text {{
            color: #e2e8f0;
            flex: 1;
        }}

        .point-text code {{
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: #38bdf8;
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
        }}

        .point-text strong {{
            color: #f8fafc;
            font-weight: 700;
        }}

        .cve-pill {{
            background: rgba(239, 68, 68, 0.16);
            border: 1px solid rgba(239, 68, 68, 0.38);
            color: #fca5a5;
            padding: 0.1rem 0.45rem;
            border-radius: 5px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.82rem;
            font-weight: 700;
            display: inline-block;
            margin: 0 0.15rem;
        }}

        .article-content p {{
            font-size: 0.96rem;
            color: #cbd5e1;
            line-height: 1.65;
        }}

        .article-content ul {{
            margin-left: 0;
            padding: 0;
            color: #cbd5e1;
            font-size: 0.95rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            list-style: none;
        }}


        /* Sleek Threat Modeling Box */
        .threat-card-box {{
            background: rgba(192, 132, 252, 0.06);
            border: 1px solid rgba(192, 132, 252, 0.25);
            border-left: 4px solid var(--accent-purple);
            border-radius: 14px;
            padding: 1.3rem;
            margin-top: 1.2rem;
            margin-bottom: 0.4rem;
        }}

        .threat-card-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.95rem;
            font-weight: 800;
            color: #e9d5ff;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .threat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 0.85rem;
        }}

        .threat-item {{
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            background: rgba(9, 13, 22, 0.45);
            border: 1px solid rgba(255, 255, 255, 0.06);
            padding: 0.85rem 1rem;
            border-radius: 10px;
        }}

        .threat-item.full-width {{
            grid-column: 1 / -1;
            background: rgba(192, 132, 252, 0.08);
            border-color: rgba(192, 132, 252, 0.25);
        }}

        .threat-key {{
            font-size: 0.74rem;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 800;
            color: #c084fc;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }}

        .threat-val {{
            font-size: 0.93rem;
            color: #f1f5f9;
            line-height: 1.5;
        }}

        .stride-badge {{
            display: inline-block;
            padding: 0.2rem 0.6rem;
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.35);
            color: #fca5a5;
            border-radius: 6px;
            font-size: 0.82rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }}

        .review-quote {{
            font-style: italic;
            color: #e9d5ff;
            font-size: 0.95rem;
            line-height: 1.5;
        }}

        /* Point-wise Design Review Questions List */
        .design-review-list {{
            margin-top: 0.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
            list-style: none;
            padding: 0;
        }}

        .design-review-list li {{
            display: flex;
            align-items: flex-start;
            gap: 0.6rem;
            background: rgba(192, 132, 252, 0.06);
            border: 1px solid rgba(192, 132, 252, 0.18);
            padding: 0.55rem 0.85rem;
            border-radius: 8px;
            font-size: 0.91rem;
            color: #f1f5f9;
            line-height: 1.5;
        }}

        .review-bullet {{
            color: #c084fc;
            font-weight: 800;
            font-size: 0.95rem;
            line-height: 1.4;
            flex-shrink: 0;
        }}

        .review-text {{
            color: #f1f5f9;
            font-size: 0.91rem;
        }}

        /* References / Footer */
        .references {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 18px;
            padding: 1.8rem 2rem;
            margin-top: 4rem;
        }}

        .references h2 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.35rem;
            color: var(--accent-primary);
            margin-bottom: 1.1rem;
        }}

        .references ul {{
            list-style-type: none;
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
        }}

        .references li {{
            font-size: 0.94rem;
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
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            color: var(--text-muted);
            font-size: 0.88rem;
        }}

        footer a {{
            color: var(--accent-primary);
            text-decoration: none;
        }}

        /* Floating back-to-top button */
        .back-to-top {{
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: rgba(56, 189, 248, 0.2);
            border: 1px solid rgba(56, 189, 248, 0.4);
            color: var(--accent-primary);
            width: 44px;
            height: 44px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            backdrop-filter: blur(12px);
            transition: all 0.2s ease;
            opacity: 0;
            pointer-events: none;
            z-index: 100;
        }}

        .back-to-top.visible {{
            opacity: 1;
            pointer-events: auto;
        }}

        .back-to-top:hover {{
            background: var(--accent-primary);
            color: #090d16;
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.5);
        }}

        /* Responsive Breakpoints */
        @media (max-width: 768px) {{
            body {{
                padding: 1.2rem 0.6rem;
            }}
            header h1 {{
                font-size: 2.1rem;
            }}
            .metrics-banner {{
                grid-template-columns: 1fr 1fr;
            }}
            .article-header {{
                flex-direction: column;
                gap: 0.6rem;
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
            <div class="header-badge">
                <span class="badge-pulse"></span>
                Security Intelligence Briefing
            </div>
            <h1>Daily Vulnerability & Exploit Digest</h1>
            <p class="date">📅 {date} &nbsp;•&nbsp; Curated for Penetration Testers & SecOps</p>
        </header>

        <!-- Metrics Banner -->
        <div class="metrics-banner">
            <div class="metric-card">
                <div class="metric-icon critical">🚨</div>
                <div class="metric-info">
                    <div class="val" id="metric-critical">{critical_count}</div>
                    <div class="lbl">Critical Threats</div>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon high">⚡</div>
                <div class="metric-info">
                    <div class="val" id="metric-high">{high_count}</div>
                    <div class="lbl">High Severity</div>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon total">🛡️</div>
                <div class="metric-info">
                    <div class="val" id="metric-total">{total_count}</div>
                    <div class="lbl">Total Findings</div>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon fresh">⏳</div>
                <div class="metric-info">
                    <div class="val">24 Hours</div>
                    <div class="lbl">Feed Window</div>
                </div>
            </div>
        </div>

        <!-- Interactive Filtering and Search -->
        <div class="filter-bar">
            <div class="search-wrapper">
                <svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input type="text" id="searchInput" class="search-box" placeholder="Search vulnerabilities, CVEs, TTPs, or keywords...">
                <span class="search-shortcut">/</span>
            </div>
            <div class="filter-group">
                <span class="filter-label">Severity:</span>
                <button class="btn-filter active" onclick="filterSeverity('all')">All</button>
                <button class="btn-filter" onclick="filterSeverity('critical')">🚨 Critical</button>
                <button class="btn-filter" onclick="filterSeverity('high')">⚡ High</button>
                <button class="btn-filter" onclick="filterSeverity('medium')">🛡️ Medium</button>
            </div>
            <div class="filter-group">
                <span class="filter-label">Focus Area:</span>
                <button class="btn-filter active" onclick="filterTag('all')">All</button>
                <button class="btn-filter" onclick="filterTag('web')">Web</button>
                <button class="btn-filter" onclick="filterTag('mobile')">Mobile</button>
                <button class="btn-filter" onclick="filterTag('api')">API</button>
                <button class="btn-filter" onclick="filterTag('network')">Network</button>
                <button class="btn-filter" onclick="filterTag('thickclient')">Thick Client</button>
                <button class="btn-filter" onclick="filterTag('cloud')">Cloud</button>
                <button class="btn-filter" onclick="filterTag('infra')">Infra</button>
                <button class="btn-filter" onclick="filterTag('news')">📰 News</button>
                <button class="btn-filter" onclick="filterTag('dependencies')">📦 Dependencies</button>
            </div>
            <div class="filter-status" id="filterStatus">Showing {total_count} of {total_count} findings</div>
        </div>

        {content}

        <footer>
            <p>Powered by <strong>HackingUpdate AI Engine v1.0.0</strong> &nbsp;•&nbsp; Automated Daily Intelligence</p>
        </footer>
    </div>

    <button class="back-to-top" id="backToTop" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})">↑</button>

    <!-- Client-side Interactive Filter Script -->
    <script>
        const searchInput = document.getElementById('searchInput');
        const backToTop = document.getElementById('backToTop');
        const filterStatus = document.getElementById('filterStatus');
        const totalCount = {total_count};

        let currentTag = 'all';
        let currentSeverity = 'all';

        document.addEventListener('keydown', (e) => {{
            if (e.key === '/' && document.activeElement !== searchInput) {{
                e.preventDefault();
                searchInput.focus();
            }}
        }});

        window.addEventListener('scroll', () => {{
            if (window.scrollY > 400) {{
                backToTop.classList.add('visible');
            }} else {{
                backToTop.classList.remove('visible');
            }}
        }});

        searchInput.addEventListener('input', () => {{
            filterItems();
        }});

        function filterSeverity(sev) {{
            const buttons = document.querySelectorAll('.filter-group:nth-child(2) .btn-filter');
            buttons.forEach(btn => {{
                const btnText = btn.textContent.toLowerCase();
                if ((sev === 'all' && btnText.includes('all')) || btnText.includes(sev)) {{
                    btn.classList.add('active');
                }} else {{
                    btn.classList.remove('active');
                }}
            }});
            currentSeverity = sev;
            filterItems();
        }}

        function filterTag(tag) {{
            const buttons = document.querySelectorAll('.filter-group:nth-child(3) .btn-filter');
            buttons.forEach(btn => {{
                const btnText = btn.textContent.toLowerCase();
                if (btnText === tag.toLowerCase() || (tag === 'all' && btnText === 'all')) {{
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
            let visibleCount = 0;

            cards.forEach(card => {{
                const title = card.querySelector('.article-title-link').textContent.toLowerCase();
                const content = card.textContent.toLowerCase();
                const tags = Array.from(card.querySelectorAll('.tag-pill')).map(t => t.textContent.toLowerCase());
                
                const rankBadge = card.querySelector('.rank-badge');
                let cardSeverity = 'medium';
                if (rankBadge.classList.contains('rank-critical')) cardSeverity = 'critical';
                else if (rankBadge.classList.contains('rank-high')) cardSeverity = 'high';

                const matchesSearch = title.includes(query) || content.includes(query);
                const depTags = ['npm', 'pypi', 'go', 'maven', 'cargo'];
                const matchesTag = currentTag === 'all' || 
                                   (currentTag === 'dependencies' ? tags.some(t => depTags.includes(t)) : tags.includes(currentTag.toLowerCase()));
                const matchesSeverity = currentSeverity === 'all' || cardSeverity === currentSeverity.toLowerCase();

                if (matchesSearch && matchesTag && matchesSeverity) {{
                    card.style.display = 'block';
                    visibleCount++;
                }} else {{
                    card.style.display = 'none';
                }}
            }});

            const sections = document.querySelectorAll('.category-section');
            sections.forEach(section => {{
                const visibleCardsInSec = section.querySelectorAll('.article-card[style="display: block;"], .article-card:not([style*="display: none"])');
                if (visibleCardsInSec.length === 0) {{
                    section.style.display = 'none';
                }} else {{
                    section.style.display = 'block';
                }}
            }});

            filterStatus.textContent = `Showing ${{visibleCount}} of ${{totalCount}} findings`;
        }}
    </script>
</body>
</html>
"""
