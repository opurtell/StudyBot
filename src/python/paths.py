import os
from pathlib import Path

_USER_DATA_ENV = os.environ.get("STUDYBOT_USER_DATA")
_APP_ROOT_ENV = os.environ.get("STUDYBOT_APP_ROOT")

if _USER_DATA_ENV and _APP_ROOT_ENV:
    USER_DATA_DIR = Path(_USER_DATA_ENV)
    APP_ROOT = Path(_APP_ROOT_ENV)
    PROJECT_ROOT = USER_DATA_DIR
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    USER_DATA_DIR = PROJECT_ROOT
    APP_ROOT = PROJECT_ROOT

CONFIG_DIR = USER_DATA_DIR / "config"
DATA_DIR = USER_DATA_DIR / "data"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
EXAMPLE_SETTINGS_PATH = APP_ROOT / "config" / "settings.example.json"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"
MASTERY_DB_PATH = DATA_DIR / "mastery.db"
LOGS_DIR = USER_DATA_DIR / "logs"

CMG_STRUCTURED_DIR = APP_ROOT / "data" / "cmgs" / "structured"
REFDOCS_DIR = APP_ROOT / "docs" / "REFdocs"
CPDDOCS_DIR = APP_ROOT / "docs" / "CPDdocs"
NOTABILITY_NOTE_DOCS_DIR = APP_ROOT / "docs" / "notabilityNotes" / "noteDocs"
PERSONAL_STRUCTURED_DIR = DATA_DIR / "personal_docs" / "structured"
RAW_NOTES_DIR = DATA_DIR / "notes_md" / "raw"
CLEANED_NOTES_DIR = DATA_DIR / "notes_md" / "cleaned"

HOST = os.environ.get("STUDYBOT_HOST", "127.0.0.1")
PORT = int(os.environ.get("STUDYBOT_PORT", "7777"))
