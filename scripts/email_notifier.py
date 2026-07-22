"""
Email notification sender for HackingUpdate.

Sends HTML-formatted email notifications with the daily security briefing
executive summary and top findings via SMTP.

Configuration via environment variables:
  SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
  SMTP_FROM_EMAIL, SMTP_TO_EMAILS (comma-separated), SMTP_USE_TLS
"""

import sys
import json
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from hackingupdate.config import (
    get_logger, SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
    SMTP_FROM_EMAIL, SMTP_TO_EMAILS, SMTP_USE_TLS,
    WORKING_CACHE_FILE, RANKED_CACHE_FILE, REPORTS_DIR,
)

import hackingupdate.config as config

logger = get_logger("email_notifier")


def parse_executive_summary(md_path: Path) -> str:
    """Extract the executive summary from the Markdown report."""
    if not md_path.exists():
        return "Daily security briefing generated successfully."
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'## Executive Summary\n(.*?)(?=\n##|$)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
    except Exception as e:
        logger.error(f"Failed to parse executive summary: {e}")
    return "Daily security briefing generated successfully."


def load_working_set_with_fallback() -> list[dict]:
    """Load the working set from cache, falling back to ranked cache or DB."""
    for cache_file in [WORKING_CACHE_FILE, RANKED_CACHE_FILE]:
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data:
                        return data
            except Exception as e:
                logger.warning(f"Could not load {cache_file}: {e}")

    # Fallback to SQLite DB
    try:
        from scripts.db_manager import get_findings_by_date
        findings = get_findings_by_date()
        if findings:
            return [dict(row) if hasattr(row, 'keys') else row for row in findings]
    except Exception as e:
        logger.warning(f"Could not load findings from SQLite DB: {e}")

    return []


def _severity_badge(rank: int) -> str:
    """Return an HTML severity badge based on rank."""
    if rank >= 8:
        return '<span style="background:#dc2626;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;">CRITICAL</span>'
    elif rank >= 6:
        return '<span style="background:#ea580c;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;">HIGH</span>'
    elif rank >= 4:
        return '<span style="background:#ca8a04;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;">MEDIUM</span>'
    else:
        return '<span style="background:#16a34a;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;">LOW</span>'


def format_email_html(today_str: str, exec_summary: str, working_set: list[dict]) -> str:
    """Generate an HTML email body with the daily briefing summary."""

    # Build top findings rows
    findings_html = ""
    top_articles = working_set[:10]
    for art in top_articles:
        title = art.get("title", "Unknown Advisory")
        link = art.get("link", "#")
        rank = art.get("rank", 5)
        source = art.get("source", "Unknown")
        tags = ", ".join(art.get("tags", []))
        badge = _severity_badge(rank)

        findings_html += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid #333;">
                {badge} <strong>Rank {rank}/10</strong><br/>
                <a href="{link}" style="color:#818cf8;text-decoration:none;font-weight:bold;">{title}</a><br/>
                <span style="color:#9ca3af;font-size:12px;">Source: {source} | Tags: {tags}</span>
            </td>
        </tr>"""

    html = f"""
    <html>
    <body style="background:#1a1a2e;color:#e0e0e0;font-family:'Segoe UI',Roboto,sans-serif;padding:20px;">
        <div style="max-width:700px;margin:0 auto;background:#16213e;border-radius:12px;overflow:hidden;border:1px solid #334155;">
            <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:24px;text-align:center;">
                <h1 style="margin:0;color:#fff;font-size:22px;">🛡️ Daily Security Intelligence Briefing</h1>
                <p style="margin:4px 0 0;color:#e2e8f0;font-size:14px;">{today_str}</p>
            </div>

            <div style="padding:20px;">
                <h2 style="color:#818cf8;font-size:16px;margin-top:0;">Executive Summary</h2>
                <p style="color:#cbd5e1;font-size:14px;line-height:1.6;">{exec_summary[:500]}</p>

                <h2 style="color:#818cf8;font-size:16px;">Top Actionable Threats ({len(top_articles)})</h2>
                <table style="width:100%;border-collapse:collapse;">
                    {findings_html}
                </table>

                <p style="color:#9ca3af;font-size:12px;margin-top:20px;text-align:center;">
                    Generated by <strong>HackingUpdate</strong> — AI-powered security intelligence pipeline
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def send_email(subject: str, html_body: str) -> bool:
    """Send an HTML email via SMTP."""
    recipients = [email.strip() for email in SMTP_TO_EMAILS.split(",") if email.strip()]
    if not recipients:
        logger.warning("SMTP_TO_EMAILS is empty. No recipients to send to.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM_EMAIL
    msg["To"] = ", ".join(recipients)

    # Plain text fallback
    plain_text = f"Daily Security Intelligence Briefing - View in an HTML-capable email client."
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        logger.info(f"Connecting to SMTP server {SMTP_HOST}:{SMTP_PORT}...")
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.ehlo()

        if SMTP_USERNAME and SMTP_PASSWORD:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)

        server.sendmail(SMTP_FROM_EMAIL, recipients, msg.as_string())
        server.quit()

        logger.info(f"Email notification sent successfully to {len(recipients)} recipient(s)!")
        return True

    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False


def main():
    """Main entry point for the email notification pipeline step."""
    # Check if email is configured
    if not SMTP_HOST or not SMTP_FROM_EMAIL or not SMTP_TO_EMAILS:
        logger.info("SMTP settings not fully configured. Skipping email notification.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    md_report_file = REPORTS_DIR / f"daily_brief_{today_str}.md"

    working_set = load_working_set_with_fallback()
    if not working_set:
        logger.info("No active working set found. Using default briefing summary.")

    logger.info("Parsing report summary for email...")
    exec_summary = parse_executive_summary(md_report_file)

    logger.info("Formatting email body...")
    html_body = format_email_html(today_str, exec_summary, working_set)

    subject = f"🛡️ Daily Security Intelligence Briefing - {today_str}"
    send_email(subject, html_body)


if __name__ == "__main__":
    main()
