"""SurpriseSage — Configuration, constants, and helpers."""

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict

# ── App Paths ────────────────────────────────────────────────────────────
APP_NAME = "surprisesage"
APP_DIR = Path.home() / f".{APP_NAME}"
LOG_FILE = APP_DIR / f"{APP_NAME}.log"
PROFILE_PATH = Path(__file__).parent / "user_profile.json"

# Ensure app directory exists with secure permissions
APP_DIR.mkdir(parents=True, exist_ok=True)
if APP_DIR.stat().st_mode & 0o777 != 0o700:
    os.chmod(APP_DIR, 0o700)

# ── AI Models ────────────────────────────────────────────────────────────
MODEL_NAME = "surprisesage:latest"          # Custom model created from Modelfile
EMBED_MODEL = "nomic-embed-text"
OLLAMA_BASE_URL = "http://localhost:11434"

# ── UI / Popup ───────────────────────────────────────────────────────────
POPUP_DURATION_SEC = 14          # How long the popup stays visible
POPUP_WIDTH = 420
POPUP_ALPHA = 0.96

# ── Themes ───────────────────────────────────────────────────────────────
THEMES = [
    "philosophy",
    "indian_mythology",
    "tech_innovation",
    "stoic_wisdom",
    "science_breakthroughs",
    "entrepreneurship",
]

# ── Scheduling ───────────────────────────────────────────────────────────
POISSON_MEAN_HOURS = 3.5          # Average gap between random surprises
MIN_RANDOM_GAP_MINUTES = 30       # Minimum time between random surprises
DND_DEFAULT = {"start": "00:00", "end": "07:00"}
DEFAULT_FIXED_TIMES = ["08:00", "13:00", "20:00"]

# ── Memory / RAG ─────────────────────────────────────────────────────────
MAX_MEMORY_RESULTS = 5
MEMORY_RETENTION_DAYS = 90

# ── Fallback messages (when Ollama is unavailable) ───────────────────────
FALLBACK_MESSAGES = [
    "Even the universe takes a breath sometimes. Take one with it.",
    'Marcus Aurelius wrote, "The obstacle is the way." That thing blocking you? It\'s the lesson.',
    "Arjuna hesitated before the battlefield too. Then Krishna reminded him of his duty. Your move.",
    "Every expert was once a beginner who refused to quit. Keep going.",
    "The best time to plant a tree was 20 years ago. The second best? Right now.",
    "Nikola Tesla worked alone while the world doubted him. Your quiet grind matters more than you think.",
    "The Wright brothers had no funding, no degrees, no runway. Just grit. Sound familiar?",
    "Karna never stopped training, even when the world called him low-born. Legends don't need permission.",
    "Steve Jobs got fired from his own company and came back to change the world. Bad days are setups.",
    "Chanakya built an empire from nothing but strategy and patience. Your plan is working — trust it.",
    "Rest is not the opposite of productivity — it's the fuel. Take a breather, you've earned it.",
    "Ada Lovelace saw the future of computing before anyone else. Vision always feels lonely at first.",
]

# ── Default profile (used when user_profile.json doesn't exist yet) ───────
DEFAULT_PROFILE: Dict[str, Any] = {
    "user_id": "default",
    "name": "Friend",
    "display_name": "Friend",

    "goals": [
        "Become a tech entrepreneur and build independent, impactful products",
        "Support my family and help them live a better life",
        "Stay healthy, happy, fit and focused",
    ],

    "personal_details": {
        "job": "Software Engineer",
        "location": "",
        "family": "",
        "hobbies": "building software, reading, walking",
    },

    "preferences": {
        "favorite_themes": THEMES[:],
        "sports_teams": [],
        "stocks": [],
        "news_topics": [],
    },

    "tone": "warm, slightly cheeky wise companion who feels like a fun older brother",

    "schedule": {
        "dnd": DND_DEFAULT,
        "frequency": "medium",
        "fixed_times": DEFAULT_FIXED_TIMES,
    },

    "memory_settings": {
        "max_memories_per_query": MAX_MEMORY_RESULTS,
        "default_retention_days": MEMORY_RETENTION_DAYS,
        "auto_cleanup_enabled": True,
        "run_every_days": 30,
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────

def setup_logging(level: int = logging.INFO) -> None:
    """Configure rotating file + console logging."""
    root = logging.getLogger("surprisesage")
    if root.handlers:
        return  # already configured

    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (5 MB × 3 backups)
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Console handler
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    root.addHandler(sh)


def load_profile() -> dict:
    """Load user_profile.json. Falls back to DEFAULT_PROFILE if missing."""
    if PROFILE_PATH.exists():
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.getLogger("surprisesage.config").warning(
                "Failed to load profile: %s. Using default.", e
            )
    return DEFAULT_PROFILE.copy()


def profile_exists() -> bool:
    """Return True if the user has already created a profile."""
    return PROFILE_PATH.exists()


def save_profile(profile: dict) -> None:
    """Save profile to disk (used by onboarding)."""
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)