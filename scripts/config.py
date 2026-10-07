#!/usr/bin/env python3
"""
Central configuration module for lecture-pipeline.
Resolves directory paths dynamically from environment variables (.env)
with sensible defaults based on macOS user directory.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load variables from .env if present
load_dotenv(PROJECT_ROOT / ".env")

# Default paths
DEFAULT_WATCH_DIR = Path.home() / "Documents" / "Wykłady"
DEFAULT_VAULT_DIR = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Studia" / "Notatki"
DEFAULT_STAGING_DIR = PROJECT_ROOT / ".staging"
DEFAULT_LOCK_FILE = Path("/tmp/lecture_pipeline.lock")
DEFAULT_COURSES_FILE = PROJECT_ROOT / "courses.json"

# Configured paths (expanded and resolved)
WATCH_DIR = Path(os.getenv("LECTURE_WATCH_DIR", str(DEFAULT_WATCH_DIR))).expanduser().resolve()
VAULT_DIR = Path(os.getenv("OBSIDIAN_VAULT_DIR", str(DEFAULT_VAULT_DIR))).expanduser().resolve()
STAGING_DIR = Path(os.getenv("LECTURE_STAGING_DIR", str(DEFAULT_STAGING_DIR))).expanduser().resolve()
LOCK_FILE = Path(os.getenv("LECTURE_LOCK_FILE", str(DEFAULT_LOCK_FILE))).expanduser().resolve()
COURSES_FILE = Path(os.getenv("LECTURE_COURSES_FILE", str(DEFAULT_COURSES_FILE))).expanduser().resolve()

SUPPORTED_EXTS = {".mov", ".mp4", ".m4a", ".wav", ".m4v"}

# Fallback course list if courses.json is missing
DEFAULT_COURSES = [
    "Rachunkowość Zarządcza",
    "Doradztwo podatkowe",
    "Audyt systemów zarządzania",
    "Analiza Danych Biznesowych",
    "Transformacja cyfrowa przedsiębiorstw",
    "Zarządzanie startupem",
    "Zwinne zarządzanie",
]


def load_known_courses() -> list[str]:
    """Loads baseline known courses from COURSES_FILE, falling back to defaults."""
    if COURSES_FILE.exists():
        try:
            with open(COURSES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return [str(c).strip() for c in data if str(c).strip()]
        except Exception:
            pass
    return list(DEFAULT_COURSES)

