import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Base Directory (Project Root)
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# OpenRouter Settings
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash:free")

# Teams Integration Settings
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")

# WhatsApp Integration Settings
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_RECIPIENT = os.getenv("WHATSAPP_RECIPIENT", "")

# Twilio WhatsApp Settings
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")
TWILIO_TO_NUMBER = os.getenv("TWILIO_TO_NUMBER", "")

# Logging Level
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# Directory Structure Paths
CACHE_DIR = BASE_DIR / "cache"
FEEDS_DIR = BASE_DIR / "feeds"
REPORTS_DIR = BASE_DIR / "reports"
SCRIPTS_DIR = BASE_DIR / "scripts"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# Ensure all directories exist
for directory in [CACHE_DIR, FEEDS_DIR, REPORTS_DIR, SCRIPTS_DIR, LOGS_DIR, DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# SQLite Database
DB_PATH = DATA_DIR / "hackingupdate.db"

# Cache Files
RAW_CACHE_FILE = CACHE_DIR / "articles_raw.json"
FULL_CACHE_FILE = CACHE_DIR / "articles_full.json"
FINGERPRINT_CACHE_FILE = CACHE_DIR / "articles_fingerprints.json"
DEDUPED_CACHE_FILE = CACHE_DIR / "articles_deduped.json"
RANKED_CACHE_FILE = CACHE_DIR / "articles_ranked.json"
WORKING_CACHE_FILE = CACHE_DIR / "articles_working.json"

# Feed Config File
FEEDS_FILE = FEEDS_DIR / "feeds.txt"

# Log File Path
LOG_FILE = LOGS_DIR / "daily_brief.log"

# Setup basic logging to both file and console
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Standard Security Tags
PENTEST_TAGS = [
    "web",
    "mobile",
    "API",
    "network",
    "thickclient",
    "cloud",
    "infra",
    "news",
    "npm",
    "pypi",
    "go",
    "maven",
    "cargo"
]

def get_logger(name):
    return logging.getLogger(name)
