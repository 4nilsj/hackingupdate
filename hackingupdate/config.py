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
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash:free")

# Teams
TEAMS_WEBHOOK_URL: str = os.getenv("TEAMS_WEBHOOK_URL", "")

# WhatsApp (generic API)
WHATSAPP_API_URL: str = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_RECIPIENT: str = os.getenv("WHATSAPP_RECIPIENT", "")

# Twilio WhatsApp
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")
TWILIO_TO_NUMBER: str = os.getenv("TWILIO_TO_NUMBER", "")

# Email (SMTP)
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_TO_EMAILS: str = os.getenv("SMTP_TO_EMAILS", "")  # Comma-separated
SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Pipeline Tuning
# ---------------------------------------------------------------------------
ARTICLE_MAX_AGE_DAYS: int = int(os.getenv("ARTICLE_MAX_AGE_DAYS", "1"))
LLM_BATCH_DELAY: float = float(os.getenv("LLM_BATCH_DELAY", "2"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL_STR: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL: int = getattr(logging, LOG_LEVEL_STR, logging.INFO)
LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text")  # "text" or "json"

# ---------------------------------------------------------------------------
# Directory Structure Paths
# ---------------------------------------------------------------------------
CACHE_DIR: Path = BASE_DIR / "cache"
FEEDS_DIR: Path = BASE_DIR / "feeds"
REPORTS_DIR: Path = BASE_DIR / "reports"
SCRIPTS_DIR: Path = BASE_DIR / "scripts"
LOGS_DIR: Path = BASE_DIR / "logs"
DATA_DIR: Path = BASE_DIR / "data"

# Ensure all directories exist
for _directory in [CACHE_DIR, FEEDS_DIR, REPORTS_DIR, LOGS_DIR, DATA_DIR]:
    _directory.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# SQLite Database
# ---------------------------------------------------------------------------
DB_PATH: Path = DATA_DIR / "hackingupdate.db"

# ---------------------------------------------------------------------------
# Cache Files
# ---------------------------------------------------------------------------
RAW_CACHE_FILE: Path = CACHE_DIR / "articles_raw.json"
FULL_CACHE_FILE: Path = CACHE_DIR / "articles_full.json"
FINGERPRINT_CACHE_FILE: Path = CACHE_DIR / "articles_fingerprints.json"
DEDUPED_CACHE_FILE: Path = CACHE_DIR / "articles_deduped.json"
RANKED_CACHE_FILE: Path = CACHE_DIR / "articles_ranked.json"
WORKING_CACHE_FILE: Path = CACHE_DIR / "articles_working.json"

# ---------------------------------------------------------------------------
# Feed Config
# ---------------------------------------------------------------------------
FEEDS_FILE: Path = FEEDS_DIR / "feeds.txt"

# ---------------------------------------------------------------------------
# Log File
# ---------------------------------------------------------------------------
LOG_FILE: Path = LOGS_DIR / "daily_brief.log"

# ---------------------------------------------------------------------------
# Setup logging (file + console, with optional JSON format)
# ---------------------------------------------------------------------------
_log_handlers: list[logging.Handler] = [
    logging.FileHandler(LOG_FILE, encoding="utf-8"),
]

if LOG_FORMAT == "json":
    try:
        from pythonjsonlogger import jsonlogger
        _json_formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            timestamp=True,
        )
        _console_handler = logging.StreamHandler()
        _console_handler.setFormatter(_json_formatter)
        _log_handlers.append(_console_handler)
    except ImportError:
        # Fallback to text if python-json-logger not installed
        _log_handlers.append(logging.StreamHandler())
else:
    _log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_log_handlers,
)

# ---------------------------------------------------------------------------
# Standard Security Tags (merged from both config files)
# ---------------------------------------------------------------------------
PENTEST_TAGS: list[str] = [
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
    "cargo",
]


def get_logger(name: str) -> logging.Logger:
    """Return a named logger tied to the project's logging config."""
    return logging.getLogger(name)
