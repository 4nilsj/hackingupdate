import sys
import json
import requests
from datetime import datetime
import re

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import hackingupdate.config as config

logger = config.get_logger("report_generator")

def format_readable_description(text):
    if not text:
        return "- No description available."

    # Strip common boilerplate phrases and remnants
    boilerplate_patterns = [
        r"(?i)view csaf summary",
        r"(?i)critical infrastructure sectors:.*?(?=\.|\n|$)",
        r"(?i)countries/areas deployed:.*?(?=\.|\n|$)",
        r"(?i)company headquarters location:.*?(?=\.|\n|$)",
        r"(?i)cvss vendor equipment vulnerabilities.*?(?=\.|\n|$)",
        r"(?i)vulnerabilities expand all \+",
        r"(?i)background\s*$"
    ]

    cleaned = text
    for pattern in boilerplate_patterns:
        cleaned = re.sub(pattern, "", cleaned)

    # Clean up multiple spaces and newlines
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Extract CVEs
    cves = re.findall(r'CVE-\d{4}-\d{4,7}', cleaned)
    cves = sorted(list(set(cves)))

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', cleaned)

    # Filter out empty or extremely short sentences
    valid_sentences = []
    for s in sentences:
        s_strip = s.strip()
        if len(s_strip) < 20:
            continue
        # Avoid sentences that are just lists of metadata or titles
        if s_strip.lower().startswith("cve-") or s_strip.lower().startswith("cvss"):
            continue
        valid_sentences.append(s_strip)

    # Build list
    bullets = []
    if cves:
        bullets.append(f"**Identified CVEs**: {', '.join(cves)}")

    # Take first 3 valid sentences as core details
    details = valid_sentences[:3]
    if details:
        for idx, d in enumerate(details):
            d = d.strip("- ").strip()
            bullets.append(f"**Detail {idx+1}**: {d}")
    else:
        bullets.append(f"**Details**: {cleaned[:350]}...")

    return "\n".join([f"- {b}" for b in bullets])

def generate_local_fallback_report(working_set, today_str):
    # Basic Markdown generator if LLM is unavailable
    md = []
    md.append(f"# Daily Security Intelligence Briefing - {today_str}\n")
    md.append("> **Note**: This report was generated using fallback template heuristics because OPENROUTER_API_KEY is not configured.\n")
    md.append("## Executive Summary\n")
    md.append(f"Today's feed collection yielded **{len(working_set)}** high-priority items. Here is a categorized breakdown of active security alerts, exploits, and technical updates.\n")
    
    # Track output articles to guarantee single post output
    seen_ids = set()
    categorized = {tag: [] for tag in config.PENTEST_TAGS}
    uncategorized = []
    
    for art in working_set:
        art_id = art.get("id", art["title"])
        if art_id in seen_ids:
            continue
        seen_ids.add(art_id)

        placed = False
        for tag in art.get("tags", []):
            if tag in categorized:
                categorized[tag].append(art)
                placed = True
                break  # Place in primary category only to prevent duplicate post cards
        if not placed:
            uncategorized.append(art)

    # Output categorized items
    for tag in config.PENTEST_TAGS:
        items = categorized[tag]
        if not items:
            continue
        md.append(f"## Category: {tag.upper()}\n")
        for art in items:
            tags_str = ", ".join(art.get("tags", [tag]))
            md.append(f"### {art['title']}")
            md.append(f"- **Source**: {art['source']}")
            md.append(f"- **Priority Rank**: `{art.get('rank', 5)}/10`")
            md.append(f"- **Link**: [{art['link']}]({art['link']})")
            md.append(f"- **Pentester Category Tags**: {tags_str}")
            md.append(f"- **Reasoning**: {art.get('rank_reason', 'N/A')}\n")
            
            if art.get('rank', 5) >= 7:
                md.append("**Threat Modeling & Secure Design Lesson**:\n\n"
                          "- *STRIDE Threat*: [Configure OPENROUTER_API_KEY to activate AI STRIDE threat classification]\n"
                          "- *Design Flaw*: [Configure OPENROUTER_API_KEY to map the underlying architectural design flaw]\n"
                          "- *Secure Design Principle*: [Configure OPENROUTER_API_KEY to specify the secure design defense principle]\n"
                          "- *Secure Design Review Question*: How does our system validate untrusted inputs before execution?\n")
                          
            readable_desc = format_readable_description(art['content_text'])
            md.append(f"**Description & Context**:\n\n{readable_desc}\n")
            md.append("---\n")

    if uncategorized:
        md.append("## General Security Updates\n")
        for art in uncategorized:
            tags_str = ", ".join(art.get("tags", ["news"]))
            md.append(f"### {art['title']}")
            md.append(f"- **Source**: {art['source']}")
            md.append(f"- **Priority Rank**: `{art.get('rank', 5)}/10`")
            md.append(f"- **Link**: [{art['link']}]({art['link']})")
            md.append(f"- **Pentester Category Tags**: {tags_str}")
            
            readable_desc = format_readable_description(art['content_text'])
            md.append(f"**Description & Context**:\n\n{readable_desc}\n")
            md.append("---\n")
            
    return "\n".join(md)

def generate_llm_report(working_set, today_str):
    if not config.OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY is not set. Generating fallback template report.")
        return generate_local_fallback_report(working_set, today_str)

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/google/antigravity",
        "X-Title": "HackingUpdate Agent"
    }

    # Format working set entries for prompt context
    serialized_articles = []
    for art in working_set:
        serialized_articles.append({
            "title": art["title"],
            "link": art["link"],
            "source": art["source"],
            "rank": art["rank"],
            "tags": art["tags"],
            "rank_reason": art["rank_reason"],
            "content": art["content_text"][:1200]  # first 1200 chars is sufficient for summary
        })

    prompt = f"""
You are a senior penetration tester and cyber threat intelligence analyst.
Compile a detailed, high-quality Markdown intelligence briefing using the following security articles.
Date: {today_str}

Articles list:
{json.dumps(serialized_articles, indent=2)}

Structure of your output report:
1. Title: "# Daily Security Intelligence Briefing - {today_str}"
2. Executive Summary: A 1-paragraph summary highlighting the most critical threats/tactics observed today.
3. Category Headings: Write headings for each of the matching tags: {config.PENTEST_TAGS} (only write categories that have articles). Note: Include top high-impact general security news stories (e.g. breach disclosures, APT campaign alerts, ransomware attacks) under Category: NEWS alongside technical zero-day vulnerabilities.
4. Article Summaries: Under each category heading (place each unique article in EXACTLY ONE primary category section):
   - "### [Title]"
   - Metadata bullet points: Source, Rank (X/10), Link, and Pentester Category Tags (list all matching tags, e.g. web, api).
   - **Description & Context**: A short bulleted list (2-3 items maximum) summarizing what the vulnerability is, the affected software versions, and core triggering conditions. Avoid walls of text; keep it punchy and clear.
   - **TTPs & Exploitation Vectors**: A short bulleted list (2-3 items maximum) detailing technical exploitation mechanics, tools used, or attack vectors.
   - **Pentesting Value & Testing Method**: A short bulleted list (2-3 items maximum) advising a pentester step-by-step how to identify, verify, or exploit this vulnerability in an assessment.
   - **Threat Modeling & Secure Design Lesson**: (Only include this section for articles with a Priority Rank >= 7. Otherwise, skip/omit it.)
     Write a short block containing:
     - *STRIDE Threat*: [e.g., Elevation of Privilege / Information Disclosure / Tampering]
     - *Design Flaw*: [State the architectural design-level root cause]
     - *Secure Design Principle*: [e.g., Least Privilege / Defense in Depth / Fail-Safe Defaults]
     - *Secure Design Review Question*: [1-2 specific point-wise questions for engineers/reviewers to ask during architecture design reviews to prevent this bug]
   - **Dependency & Package Ecosystem Details**: (Only include this if the vulnerability is in a library, package, or third-party dependency. Otherwise, skip/omit it.)
     Write a short block containing:
     - *Package Name*: [e.g., `express`, `requests`, `spring-web`]
     - *Ecosystem*: [e.g., npm / PyPI / Go / Java Maven / Cargo]
     - *Patched Version*: [e.g., `>= 4.19.2`, `>= 2.31.0`]
     - *Advisory Identifier*: [e.g., GHSA ID / CVE ID]
   - **Developer PR Review Checklist**: (Only include this section for articles with a Priority Rank >= 7. Otherwise, skip/omit it.)
     Write 2 to 3 actionable checkpoints for pull request reviewers:
     - `[ ]` [Specific code check or sanitization verification detail]
     - `[ ]` [Check configuration default or dependency update verification]
   - **Remediation**: A short bulleted list or 1-2 sentences on how organizations should patch or mitigate the risk.
5. End with a list of References (Titles and Links).

Keep the tone highly professional, precise, and practical for ethical hackers and product security engineers. 

CRITICAL SINGLE-POST & DEDUPLICATION RULES:
1. Output EXACTLY ONE summary post (card) per unique article/vulnerability. Do NOT output duplicate posts or repeat the same article under multiple category headings.
2. If an article matches multiple pentest categories (e.g. both Web and API), place it under its primary category section and list ALL applicable tags in its metadata line (e.g. `- **Pentester Category Tags**: web, api`).
3. If the input list contains multiple articles covering the exact same vulnerability or security event, consolidate them into a single authoritative post card and omit duplicate entries entirely.


CRITICAL FORMATTING RULES:
1. Do NOT prefix the bold section headers (like **Description & Context**, **TTPs & Exploitation Vectors**, **Pentesting Value & Testing Method**, **Threat Modeling & Secure Design Lesson**, and **Remediation**) with bullet points (like * or -). Write them on their own lines as plain text headers, e.g., '**TTPs & Exploitation Vectors**:'.
2. Insert a double newline (blank line) after each section header and before its contents or bullet list, to ensure markdown compiles lists cleanly.
3. Return ONLY the markdown output. Do not wrap in extra chat markup like triple backticks (e.g. ```markdown), just return the raw markdown string.
4. When writing about multiple CVEs or explaining individual CVEs, always list each CVE on a new line as a bullet point (using '*') rather than embedding them in a paragraph or as a single inline sentence.

"""

    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a cybersecurity expert who compiles executive and technical reports for security teams."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        content = _call_openrouter_report_with_retry(headers, payload)
        # Clean potential LLM markdown wrapper lines
        if content.startswith("```markdown"):
            content = content[11:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    except Exception as e:
        logger.error(f"OpenRouter report generation failed after retries: {e}. Falling back to template-based generator.")
        return generate_local_fallback_report(working_set, today_str)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type((requests.exceptions.HTTPError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
    before_sleep=lambda retry_state: logger.warning(
        f"Report LLM API request failed, retrying in {retry_state.next_action.sleep:.0f}s... "
        f"(attempt {retry_state.attempt_number}/3)"
    ),
)
def _call_openrouter_report_with_retry(headers: dict, payload: dict) -> str:
    """Make an OpenRouter API call for report generation with automatic retry."""
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )
    response.raise_for_status()
    res_data = response.json()
    choices = res_data.get("choices", [])
    if not choices:
        raise ValueError(f"Empty choices in OpenRouter response: {res_data}")
    
    return choices[0]["message"]["content"].strip()

def main():
    if not config.WORKING_CACHE_FILE.exists():
        logger.error(f"Working set cache file not found: {config.WORKING_CACHE_FILE}")
        sys.exit(1)

    try:
        with open(config.WORKING_CACHE_FILE, "r", encoding="utf-8") as f:
            working_set = json.load(f)
    except Exception as e:
        logger.critical(f"Failed to load working set cache: {e}")
        sys.exit(1)

    today_str = datetime.now().strftime("%Y-%m-%d")
    report_file = config.REPORTS_DIR / f"daily_brief_{today_str}.md"

    logger.info(f"Generating Daily Brief for {today_str}...")
    report_content = generate_llm_report(working_set, today_str)

    try:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_content)
        logger.info(f"Successfully generated Markdown report at: {report_file}")
    except Exception as e:
        logger.critical(f"Failed to save Markdown report file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
