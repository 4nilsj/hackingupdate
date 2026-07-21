import sys
import json
import re
import requests
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

logger = config.get_logger("whatsapp_notifier")

def parse_executive_summary(md_path):
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

def load_working_set_with_fallback(today_str):
    if config.WORKING_CACHE_FILE.exists():
        try:
            with open(config.WORKING_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    return data
        except Exception as e:
            logger.warning(f"Could not load working cache file: {e}")

    if config.RANKED_CACHE_FILE.exists():
        try:
            with open(config.RANKED_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    return data
        except Exception as e:
            logger.warning(f"Could not load ranked cache file: {e}")

    # Fallback to SQLite DB
    try:
        from scripts.db_manager import get_findings_by_date
        findings = get_findings_by_date()
        if findings:
            # Convert DB row objects to dicts
            return [dict(row) if hasattr(row, 'keys') else row for row in findings]
    except Exception as e:
        logger.warning(f"Could not load findings from SQLite DB: {e}")

    return []

def format_whatsapp_message(today_str, exec_summary, working_set):
    msg = f"🛡️ *Daily Security Intelligence Briefing - {today_str}*\n\n"
    msg += f"🔥 *Top Actionable Threats Today:*\n"
    
    if not working_set:
        msg += "\n• *Daily Security Digest Available*\n  🔗 Link: https://briefing.appsecexpert.com/\n"
        return msg

    top_articles = working_set[:10]
    for art in top_articles:
        title = art.get("title", "Unknown Advisory")
        link = art.get("link", "#")
        
        art_block = f"\n• *{title}*\n"
        art_block += f"  🔗 Link: {link}\n"
        
        if len(msg) + len(art_block) > 1520:
            msg += "\n_(Remaining advisories truncated to fit character limits)_"
            break
            
        msg += art_block
        
    if len(msg) > 1580:
        msg = msg[:1570] + "\n...(truncated)"
        
    return msg

def send_twilio_notification(account_sid, auth_token, from_number, to_number, message_text):
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"
        
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    
    payload = {
        "From": from_number,
        "To": to_number,
        "Body": message_text
    }
    
    try:
        logger.info(f"Posting to Twilio API endpoint for account: {account_sid}...")
        response = requests.post(url, data=payload, auth=(account_sid, auth_token), timeout=15)
        response.raise_for_status()
        logger.info("Twilio WhatsApp notification sent successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to send Twilio WhatsApp notification: {e}")
        if 'response' in locals() and hasattr(response, 'text') and response.text:
            logger.error(f"Twilio API error response details: {response.text}")
        return False

def send_whatsapp_notification(api_url, token, recipient, message_text):
    logger.info("Sending WhatsApp message via gateway...")
    
    if "callmebot.com" in api_url.lower():
        logger.info("Detected CallMeBot API gateway. Sending GET request...")
        params = {
            "phone": recipient,
            "text": message_text,
            "apikey": token
        }
        try:
            response = requests.get(api_url, params=params, timeout=15)
            response.raise_for_status()
            logger.info("CallMeBot notification sent successfully!")
            return True
        except Exception as e:
            logger.error(f"Failed to send CallMeBot notification: {e}")
            return False
    else:
        logger.info("Sending POST request to WhatsApp gateway API...")
        payload = {
            "token": token,
            "to": recipient,
            "body": message_text
        }
        
        try:
            response = requests.post(api_url, data=payload, timeout=15)
            if response.status_code == 415 or response.status_code == 400:
                logger.info("Retrying with JSON payload header...")
                headers = {"Content-Type": "application/json"}
                response = requests.post(api_url, json=payload, headers=headers, timeout=15)
                
            response.raise_for_status()
            logger.info("WhatsApp notification sent successfully!")
            return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp notification: {e}")
            return False

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    md_report_file = config.REPORTS_DIR / f"daily_brief_{today_str}.md"
    
    working_set = load_working_set_with_fallback(today_str)
    if not working_set:
        logger.info("No active working set cache or DB findings found. Using default briefing summary.")

    logger.info("Parsing report summary...")
    exec_summary = parse_executive_summary(md_report_file)
    
    logger.info("Formatting WhatsApp message...")
    message_text = format_whatsapp_message(today_str, exec_summary, working_set)
    
    if config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN and config.TWILIO_TO_NUMBER:
        logger.info("Twilio settings detected. Initiating Twilio WhatsApp delivery...")
        send_twilio_notification(
            config.TWILIO_ACCOUNT_SID,
            config.TWILIO_AUTH_TOKEN,
            config.TWILIO_FROM_NUMBER,
            config.TWILIO_TO_NUMBER,
            message_text
        )
    elif config.WHATSAPP_API_URL and config.WHATSAPP_TOKEN and config.WHATSAPP_RECIPIENT:
        logger.info("Gateway settings detected. Initiating WhatsApp gateway delivery...")
        send_whatsapp_notification(config.WHATSAPP_API_URL, config.WHATSAPP_TOKEN, config.WHATSAPP_RECIPIENT, message_text)
    else:
        logger.info("Neither Twilio nor generic WhatsApp notification settings are fully configured. Skipping WhatsApp notification.")

if __name__ == "__main__":
    main()
