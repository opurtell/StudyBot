from __future__ import annotations

import argparse
import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from guidelines.router import invalidate_guideline_cache
from medication.router import invalidate_medication_cache
from .orchestrator import INVESTIGATION_DIR, run_pipeline

STATUS_PATH = Path("data/cmgs/refresh_status.json")
HISTORY_PATH = Path("data/cmgs/refresh_history.json")
RECOMMENDED_CADENCE = "weekly"

_RUN_LOCK = threading.Lock()
_RUN_THREAD: threading.Thread | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_status() -> dict[str, Any]:
    return {
        "status": "idle",
        "is_running": False,
        "last_started_at": None,
        "last_completed_at": None,
        "last_successful_at": None,
        "trigger": None,
        "recommended_cadence": RECOMMENDED_CADENCE,
        "summary": None,
        "last_error": None,
    }


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_refresh_status(status_path: Path = STATUS_PATH) -> dict[str, Any]:
    status = _read_json(status_path, _default_status())
    for key, value in _default_status().items():
        status.setdefault(key, deepcopy(value))
    status["is_running"] = is_refresh_running() or bool(status.get("is_running"))
    if not is_refresh_running() and status.get("status") == "running":
        status["is_running"] = False
    return status


def _load_history(history_path: Path = HISTORY_PATH) -> list[dict[str, Any]]:
    return _read_json(history_path, [])


def _append_history(entry: dict[str, Any], history_path: Path = HISTORY_PATH) -> None:
    history = _load_history(history_path)
    history.append(entry)
    _write_json(history_path, history)


def _persist_status(status: dict[str, Any], status_path: Path = STATUS_PATH) -> None:
    _write_json(status_path, status)


def is_refresh_running() -> bool:
    return _RUN_THREAD is not None and _RUN_THREAD.is_alive()


def run_refresh(
    *,
    trigger: str = "manual",
    dry_run: bool = False,
    skip_capture: bool = False,
    investigation_dir: str = INVESTIGATION_DIR,
    status_path: Path = STATUS_PATH,
    history_path: Path = HISTORY_PATH,
) -> dict[str, Any]:
    started_at = _utc_now()
    prior_status = load_refresh_status(status_path)
    status = {
        **prior_status,
        "status": "running",
        "is_running": True,
        "last_started_at": started_at,
        "last_completed_at": None,
        "trigger": trigger,
        "recommended_cadence": RECOMMENDED_CADENCE,
        "summary": None,
        "last_error": None,
    }
    _persist_status(status, status_path)

    try:
        if not skip_capture:
            from .capture_assets import capture_all_assets

            capture_all_assets()

        pipeline_result = run_pipeline(
            stages="all",
            dry_run=dry_run,
            investigation_dir=investigation_dir,
        )
        version_summary = pipeline_result.get("version_summary") or {
            "checked_item_count": 0,
            "new_count": 0,
            "updated_count": 0,
            "unchanged_count": 0,
            "error_count": 0,
            "items": [],
        }
        summary = {
            "checked_item_count": version_summary["checked_item_count"],
            "new_count": version_summary["new_count"],
            "updated_count": version_summary["updated_count"],
            "unchanged_count": version_summary["unchanged_count"],
            "error_count": version_summary["error_count"],
            "dry_run": dry_run,
            "skip_capture": skip_capture,
        }
        completed_at = _utc_now()
        success_status = {
            **status,
            "status": "succeeded",
            "is_running": False,
            "last_completed_at": completed_at,
            "last_successful_at": completed_at,
            "summary": summary,
            "last_error": None,
        }
        _persist_status(success_status, status_path)
        _append_history(
            {
                "started_at": started_at,
                "completed_at": completed_at,
                "status": "succeeded",
                "trigger": trigger,
                "summary": summary,
                "last_error": None,
            },
            history_path,
        )
        invalidate_guideline_cache()
        invalidate_medication_cache()
        return success_status
    except Exception as exc:
        completed_at = _utc_now()
        failed_status = {
            **status,
            "status": "failed",
            "is_running": False,
            "last_completed_at": completed_at,
            "last_successful_at": prior_status.get("last_successful_at"),
            "summary": None,
            "last_error": str(exc),
        }
        _persist_status(failed_status, status_path)
        _append_history(
            {
                "started_at": started_at,
                "completed_at": completed_at,
                "status": "failed",
                "trigger": trigger,
                "summary": None,
                "last_error": str(exc),
            },
            history_path,
        )
        raise


def start_refresh_in_background(
    *,
    trigger: str = "manual",
    dry_run: bool = False,
    skip_capture: bool = False,
    investigation_dir: str = INVESTIGATION_DIR,
) -> dict[str, Any]:
    global _RUN_THREAD
    with _RUN_LOCK:
        if is_refresh_running():
            raise RuntimeError("CMG refresh already running")
        started_at = _utc_now()

        def _runner() -> None:
            try:
                run_refresh(
                    trigger=trigger,
                    dry_run=dry_run,
                    skip_capture=skip_capture,
                    investigation_dir=investigation_dir,
                )
            finally:
                global _RUN_THREAD
                with _RUN_LOCK:
                    _RUN_THREAD = None

        _RUN_THREAD = threading.Thread(target=_runner, daemon=True, name="cmg-refresh")
        _RUN_THREAD.start()
        return {
            "status": "started",
            "message": "CMG refresh started",
            "started_at": started_at,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a CMG refresh")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-capture", action="store_true")
    args = parser.parse_args()
    run_refresh(
        trigger="manual",
        dry_run=args.dry_run,
        skip_capture=args.skip_capture,
    )


if __name__ == "__main__":
    main()
