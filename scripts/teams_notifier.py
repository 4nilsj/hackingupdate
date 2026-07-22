import sys
import json
import re
import requests
from datetime import datetime
from pathlib import Path

from hackingupdate.config import (
    get_logger, TEAMS_WEBHOOK_URL, REPORTS_DIR, WORKING_CACHE_FILE,
)

import hackingupdate.config as config

logger = config.get_logger("teams_notifier")

def parse_executive_summary(md_path):
    if not md_path.exists():
        return "Daily intelligence report generated successfully."
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Find block between "## Executive Summary" and the next heading "##"
        match = re.search(r'## Executive Summary\n(.*?)(?=\n##|$)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
    except Exception as e:
        logger.error(f"Failed to parse executive summary from markdown: {e}")
    return "Daily intelligence report generated successfully."

def send_teams_notification(webhook_url, today_str, exec_summary, working_set):
    logger.info("Building Teams MessageCard payload...")
    
    # Select top 5 vulnerabilities to display in the card (so it remains concise)
    top_vulnerabilities = working_set[:5]
    
    facts = []
    for art in top_vulnerabilities:
        title = art.get("title", "Unknown Advisory")
        rank = art.get("rank", 5)
        source = art.get("source", "Unknown Source")
        link = art.get("link", "#")
        tags_str = ", ".join(art.get("tags", []))
        
        facts.append({
            "name": f"⭐ {title} (Rank {rank}/10)",
            "value": f"📍 Source: {source} | Tags: `{tags_str}`\n[Read Advisory]({link})"
        })

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "a855f7", # Purple theme to match secure design accent
        "summary": "Daily Security Intelligence Briefing",
        "title": f"🛡️ Daily Security Intelligence Briefing - {today_str}",
        "sections": [
            {
                "activityTitle": "Executive Intel Summary",
                "activitySubtitle": f"Analyzed {len(working_set)} high-priority updates",
                "text": exec_summary
            },
            {
                "title": "Top Actionable Threats Today",
                "facts": facts
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        logger.info(f"Sending POST request to Teams Webhook...")
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        logger.info("Teams notification sent successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to send Teams notification: {e}")
        return False

def main():
    if not config.TEAMS_WEBHOOK_URL:
        logger.info("TEAMS_WEBHOOK_URL not configured. Skipping Teams notification.")
        sys.exit(0)

    today_str = datetime.now().strftime("%Y-%m-%d")
    md_report_file = config.REPORTS_DIR / f"daily_brief_{today_str}.md"
    
    if not config.WORKING_CACHE_FILE.exists():
        logger.error(f"Working cache file not found: {config.WORKING_CACHE_FILE}")
        sys.exit(1)

    try:
        with open(config.WORKING_CACHE_FILE, "r", encoding="utf-8") as f:
            working_set = json.load(f)
    except Exception as e:
        logger.critical(f"Failed to load working set cache: {e}")
        sys.exit(1)

    logger.info("Parsing executive summary...")
    exec_summary = parse_executive_summary(md_report_file)

    send_teams_notification(config.TEAMS_WEBHOOK_URL, today_str, exec_summary, working_set)

if __name__ == "__main__":
    main()
