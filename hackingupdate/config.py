"""
Centralized configuration for HackingUpdate.

Supports two modes:
  1. Project-local: Reads .env and uses dirs relative to the project root.
  2. Installed package: Uses XDG-style paths (~/.config/hackingupdate/).

All paths and secrets are resolved at import time.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Resolve project root (works whether run from package or from scripts/)
# ---------------------------------------------------------------------------
def _find_project_root() -> Path:
    """Walk up from this file to find the project root (directory containing feeds/ or pyproject.toml)."""
    candidate = Path(__file__).resolve().parent.parent  # hackingupdate/ -> project root
    if (candidate / "feeds").is_dir() or (candidate / "pyproject.toml").is_file():
        return candidate
    # Fallback: current working directory
    cwd = Path.cwd()
    if (cwd / "feeds").is_dir() or (cwd / "pyproject.toml").is_file():
        return cwd
    return candidate

BASE_DIR = _find_project_root()

# ---------------------------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------------------------
_env_path = Path(os.getenv("HACKINGUPDATE_ENV", str(BASE_DIR / ".env")))
if _env_path.is_file():
    load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# API Keys & Secrets
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash:free")

# Teams
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")

# WhatsApp (generic API)
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_RECIPIENT = os.getenv("WHATSAPP_RECIPIENT", "")

# Twilio WhatsApp
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")
TWILIO_TO_NUMBER = os.getenv("TWILIO_TO_NUMBER", "")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# ---------------------------------------------------------------------------
# Directory Structure Paths
# ---------------------------------------------------------------------------
CACHE_DIR = BASE_DIR / "cache"
FEEDS_DIR = BASE_DIR / "feeds"
REPORTS_DIR = BASE_DIR / "reports"
SCRIPTS_DIR = BASE_DIR / "scripts"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# Ensure all directories exist
for _directory in [CACHE_DIR, FEEDS_DIR, REPORTS_DIR, LOGS_DIR, DATA_DIR]:
    _directory.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# SQLite Database
# ---------------------------------------------------------------------------
DB_PATH = DATA_DIR / "hackingupdate.db"

# ---------------------------------------------------------------------------
# Cache Files
# ---------------------------------------------------------------------------
RAW_CACHE_FILE = CACHE_DIR / "articles_raw.json"
FULL_CACHE_FILE = CACHE_DIR / "articles_full.json"
FINGERPRINT_CACHE_FILE = CACHE_DIR / "articles_fingerprints.json"
DEDUPED_CACHE_FILE = CACHE_DIR / "articles_deduped.json"
RANKED_CACHE_FILE = CACHE_DIR / "articles_ranked.json"
WORKING_CACHE_FILE = CACHE_DIR / "articles_working.json"

# ---------------------------------------------------------------------------
# Feed Config
# ---------------------------------------------------------------------------
FEEDS_FILE = FEEDS_DIR / "feeds.txt"

# ---------------------------------------------------------------------------
# Log File
# ---------------------------------------------------------------------------
LOG_FILE = LOGS_DIR / "daily_brief.log"

# ---------------------------------------------------------------------------
# Setup logging (file + console)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# ---------------------------------------------------------------------------
# Standard Security Tags
# ---------------------------------------------------------------------------
PENTEST_TAGS = [
    "web",
    "mobile",
    "API",
    "network",
    "thickclient",
    "cloud",
    "infra",
]


def get_logger(name: str) -> logging.Logger:
    """Return a named logger tied to the project's logging config."""
    return logging.getLogger(name)
