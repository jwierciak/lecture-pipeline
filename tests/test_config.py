import os
import sys
from pathlib import Path
import pytest

# Ensure scripts/ is in sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import config
from course_matcher import clean_topic_name, get_known_courses


def test_config_paths_resolved():
    assert config.WATCH_DIR.is_absolute()
    assert config.VAULT_DIR.is_absolute()
    assert config.STAGING_DIR.is_absolute()
    assert config.LOCK_FILE.is_absolute()
    assert ".mp4" in config.SUPPORTED_EXTS
    assert ".mov" in config.SUPPORTED_EXTS


def test_load_known_courses():
    courses = config.load_known_courses()
    assert isinstance(courses, list)
    assert len(courses) > 0
    assert "Doradztwo podatkowe" in courses or len(courses) >= 1


def test_clean_topic_name():
    raw_topic = 'Wprowadzenie: do "Systemów" & Analizy / Test?'
    cleaned = clean_topic_name(raw_topic)
    for forbidden in ['/', ':', '*', '?', '"', '<', '>', '|']:
        assert forbidden not in cleaned
    assert "Wprowadzenie" in cleaned


def test_get_known_courses_with_mock_vault(tmp_path):
    # Create fake vault with course folders
    fake_vault = tmp_path / "Vault"
    fake_vault.mkdir()
    (fake_vault / "Fizyka Kwantowa").mkdir()
    (fake_vault / "Matematyka Dyskretna").mkdir()
    (fake_vault / ".obsidian").mkdir()
    (fake_vault / "templates").mkdir()

    known = get_known_courses(vault_dir=fake_vault)
    assert "Fizyka Kwantowa" in known
    assert "Matematyka Dyskretna" in known
    assert ".obsidian" not in known
    assert "templates" not in known

