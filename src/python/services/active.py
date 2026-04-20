import json
from pathlib import Path

from services.registry import get_service, REGISTRY, Service


def active_service_from_path(path: Path) -> Service:
    """Read active service ID from a settings.json file.

    Falls back to the first service in the registry if:
    - The file doesn't exist
    - The file is empty or has no "active_service" key

    Args:
        path: Path to settings.json file

    Returns:
        Service instance for the active service

    Raises:
        KeyError: If active_service ID is unknown
    """
    data = json.loads(path.read_text()) if path.is_file() else {}
    svc_id = data.get("active_service")
    if not svc_id:
        return REGISTRY[0]
    return get_service(svc_id)


def active_service() -> Service:
    """Get the currently active service from the default settings path.

    Returns:
        Service instance for the active service
    """
    from paths import SETTINGS_PATH, EXAMPLE_SETTINGS_PATH
    if SETTINGS_PATH.is_file():
        return active_service_from_path(SETTINGS_PATH)
    return active_service_from_path(EXAMPLE_SETTINGS_PATH)
