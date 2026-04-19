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
BUNDLED_CHROMA_DB_DIR = APP_ROOT / "data" / "chroma_db"
MASTERY_DB_PATH = DATA_DIR / "mastery.db"
LOGS_DIR = USER_DATA_DIR / "logs"

# DEPRECATED: Use service-aware helpers below (resolve_service_structured_dir, etc.)
# These legacy constants are kept for backward compatibility during migration.
# Task 13 will migrate their callers to the new service-aware functions.
CMG_STRUCTURED_DIR = APP_ROOT / "data" / "cmgs" / "structured"
USER_CMG_STRUCTURED_DIR = DATA_DIR / "cmgs" / "structured"


def resolve_cmg_structured_dir() -> Path:
    """DEPRECATED: Use resolve_service_structured_dir("actas") instead."""
    if USER_CMG_STRUCTURED_DIR.exists() and any(USER_CMG_STRUCTURED_DIR.glob("*.json")):
        return USER_CMG_STRUCTURED_DIR
    return CMG_STRUCTURED_DIR


# Service-aware helpers for multi-service architecture
def service_structured_dir(service_id: str) -> Path:
    """Returns the bundled structured data directory for a service.

    Args:
        service_id: Service identifier (e.g. "actas", "ambulance_tas")

    Returns:
        Path to APP_ROOT/data/services/{service_id}/structured
    """
    return APP_ROOT / "data" / "services" / service_id / "structured"


def user_service_structured_dir(service_id: str) -> Path:
    """Returns the user-local structured data directory for a service.

    Args:
        service_id: Service identifier (e.g. "actas", "ambulance_tas")

    Returns:
        Path to USER_DATA_ROOT/services/{service_id}/structured
    """
    return USER_DATA_DIR / "services" / service_id / "structured"


def resolve_service_structured_dir(service_id: str) -> Path:
    """Resolves the structured data directory for a service, preferring user data.

    If user-local data exists and contains JSON files, returns user directory.
    Otherwise returns bundled app directory.

    Args:
        service_id: Service identifier (e.g. "actas", "ambulance_tas")

    Returns:
        Path to either user_service_structured_dir or service_structured_dir
    """
    user = user_service_structured_dir(service_id)
    if user.exists() and any(user.glob("*.json")):
        return user
    return service_structured_dir(service_id)


def service_uploads_dir(service_id: str) -> Path:
    """Returns the user-local uploads directory for a service.

    Args:
        service_id: Service identifier (e.g. "actas", "ambulance_tas")

    Returns:
        Path to USER_DATA_ROOT/services/{service_id}/uploads
    """
    return USER_DATA_DIR / "services" / service_id / "uploads"


def user_service_uploads_dir(service_id: str) -> Path:
    """Alias for service_uploads_dir. Returns user-local uploads directory for a service.

    Args:
        service_id: Service identifier (e.g. "actas", "ambulance_tas")

    Returns:
        Path to USER_DATA_ROOT/services/{service_id}/uploads
    """
    return service_uploads_dir(service_id)


def service_medications_dir(service_id: str) -> Path:
    """Returns the user-local medications directory for a service.

    Args:
        service_id: Service identifier (e.g. "actas", "ambulance_tas")

    Returns:
        Path to USER_DATA_ROOT/services/{service_id}/medications
    """
    return USER_DATA_DIR / "services" / service_id / "medications"


def bundled_service_structured_dir(service_id: str) -> Path:
    """Alias for service_structured_dir. Returns bundled structured data directory.

    Args:
        service_id: Service identifier (e.g. "actas", "ambulance_tas")

    Returns:
        Path to APP_ROOT/data/services/{service_id}/structured
    """
    return service_structured_dir(service_id)
REFDOCS_DIR = APP_ROOT / "docs" / "REFdocs"
CPDDOCS_DIR = APP_ROOT / "docs" / "CPDdocs"
NOTABILITY_NOTE_DOCS_DIR = APP_ROOT / "docs" / "notabilityNotes" / "noteDocs"
PERSONAL_STRUCTURED_DIR = DATA_DIR / "personal_docs" / "structured"
RAW_NOTES_DIR = DATA_DIR / "notes_md" / "raw"
CLEANED_NOTES_DIR = DATA_DIR / "notes_md" / "cleaned"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_STRUCTURED_DIR = DATA_DIR / "uploads" / "structured"

HOST = os.environ.get("STUDYBOT_HOST", "127.0.0.1")
PORT = int(os.environ.get("STUDYBOT_PORT", "7777"))
