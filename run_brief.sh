#!/usr/bin/env bash

# Exit immediately if any command exits with a non-zero status
set -e

# Resolve the project root directory (directory where this script is located)
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

LOG_FILE="logs/daily_brief.log"
mkdir -p logs

echo "==================================================" >> "$LOG_FILE"
echo "Starting Daily Security Briefing Pipeline: $(date)" >> "$LOG_FILE"
echo "==================================================" >> "$LOG_FILE"

# Log to console and file helper
log_step() {
    local message="[$(date +'%Y-%m-%d %H:%M:%S')] $1"
    echo "$message"
    echo "$message" >> "$LOG_FILE"
}

# 1. Virtual Environment Setup
if [ ! -d "venv" ]; then
    log_step "Creating Python virtual environment (venv)..."
    python3 -m venv venv >> "$LOG_FILE" 2>&1
fi

log_step "Activating virtual environment..."
source venv/bin/activate

log_step "Installing/updating dependencies from requirements.txt..."
pip install --upgrade pip >> "$LOG_FILE" 2>&1
pip install -r requirements.txt >> "$LOG_FILE" 2>&1

# 2. Clear previous cache to ensure fresh data
log_step "Clearing previous cache for a fresh fetch..."
if [ -d "cache" ]; then
    rm -f cache/*.json
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] run_brief: Cleared all cached JSON files in cache/" >> "$LOG_FILE"
fi

# 3. Execute Python Scripts
log_step "Step 1/8: Fetching security feeds (fetcher.py)..."
python scripts/fetcher.py >> "$LOG_FILE" 2>&1

log_step "Step 2/8: Extracting and cleaning content (extractor.py)..."
python scripts/extractor.py >> "$LOG_FILE" 2>&1

log_step "Step 3/8: Generating content fingerprints (fingerprint_analyzer.py)..."
python scripts/fingerprint_analyzer.py >> "$LOG_FILE" 2>&1

log_step "Step 4/8: Running deduplication engine (dedupe_fingerprints.py)..."
python scripts/dedupe_fingerprints.py >> "$LOG_FILE" 2>&1

log_step "Step 5/8: Tagging & ranking articles (priority_ranker.py)..."
python scripts/priority_ranker.py >> "$LOG_FILE" 2>&1

log_step "Step 6/9: Compiling working set (build_working_set.py)..."
python scripts/build_working_set.py >> "$LOG_FILE" 2>&1

log_step "Step 7/9: Storing findings to SQLite (db_manager.py)..."
python scripts/db_manager.py >> "$LOG_FILE" 2>&1

log_step "Step 8/9: Generating Markdown daily brief (report_generator.py)..."
python scripts/report_generator.py >> "$LOG_FILE" 2>&1

log_step "Step 9/10: Rendering HTML brief (html_generator.py)..."
python scripts/html_generator.py >> "$LOG_FILE" 2>&1

log_step "Step 10/10: Generating RSS 2.0 XML feed (rss_generator.py)..."
python scripts/rss_generator.py >> "$LOG_FILE" 2>&1

log_step "Sending Microsoft Teams notifications (teams_notifier.py)..."
python scripts/teams_notifier.py >> "$LOG_FILE" 2>&1

log_step "Sending WhatsApp notifications (whatsapp_notifier.py)..."
python scripts/whatsapp_notifier.py >> "$LOG_FILE" 2>&1

log_step "Pipeline execution finished successfully!"
echo "==================================================" >> "$LOG_FILE"
echo "Finished Daily Security Briefing Pipeline: $(date)" >> "$LOG_FILE"
echo "==================================================" >> "$LOG_FILE"

# Run log pruner to clean up logs older than 5 days
python scripts/prune_logs.py

echo ""
echo "Daily briefs generated successfully in reports/ directory:"
ls -la reports/
