import sys
import re
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

logger = config.get_logger("prune_logs")

def parse_line_date(line, last_date):
    # Regex to find YYYY-MM-DD
    match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', line)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
            
    # Check for syslog style dates like "Mon Jul 20" or "Jul 20"
    # E.g. "Starting Daily Security Briefing Pipeline: Mon Jul 20 03:31:57 IST 2026"
    match_year = re.search(r'\b([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d+\s+.*?\s+(\d{4}))\b', line)
    if match_year:
        try:
            # Matches format "Mon Jul 20 ... 2026" -> parse as date
            # We can extract the year and the date string
            # Mon Jul 20 03:31:57 IST 2026 -> Mon Jul 20 2026
            parts = line.split()
            # Find the index of the year (usually at the end of date string)
            for part in parts:
                if len(part) == 4 and part.isdigit() and int(part) >= 2020:
                    year = part
                    # Find day and month
                    # E.g. "Jul" and "20"
                    for idx, p in enumerate(parts):
                        if p in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]:
                            month = p
                            day = parts[idx+1].strip(",")
                            dt = datetime.strptime(f"{year} {month} {day}", "%Y %b %d")
                            return dt.date()
        except Exception:
            pass
            
    return last_date

def main():
    log_file = config.LOG_FILE
    if not log_file.exists():
        logger.warning(f"Log file not found: {log_file}")
        return

    logger.info(f"Pruning older log history in {log_file} (keeping last 5 days)...")
    
    # Define threshold (keep last 5 days including today)
    today = datetime.now().date()
    threshold_date = today - timedelta(days=4)  # 4 days ago to today = 5 days total
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        return

    kept_lines = []
    current_line_date = None
    
    # First pass: read log file in reverse or forward to associate lines with dates
    # Since logs are written forward, we scan forward.
    for line in lines:
        current_line_date = parse_line_date(line, current_line_date)
        
        # If we haven't found any date yet, keep the line by default (e.g. startup banners)
        if current_line_date is None:
            kept_lines.append(line)
        # If the line belongs to a date >= threshold, keep it
        elif current_line_date >= threshold_date:
            kept_lines.append(line)
        else:
            # Line is older than 5 days, discard it
            pass

    # Save kept lines back to log file
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.writelines(kept_lines)
        logger.info(f"Pruned log file successfully. Kept {len(kept_lines)} of {len(lines)} lines.")
    except Exception as e:
        logger.critical(f"Failed to write pruned log file: {e}")

if __name__ == "__main__":
    main()
