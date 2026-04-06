import shutil
from pathlib import Path

from paths import (
    CHROMA_DB_DIR,
    CONFIG_DIR,
    EXAMPLE_SETTINGS_PATH,
    LOGS_DIR,
    SETTINGS_PATH,
)


def seed_user_data() -> None:
    _ensure_settings()
    _ensure_dirs()


def _ensure_settings() -> None:
    if SETTINGS_PATH.exists():
        return
    if not EXAMPLE_SETTINGS_PATH.exists():
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EXAMPLE_SETTINGS_PATH, SETTINGS_PATH)


def _ensure_dirs() -> None:
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
