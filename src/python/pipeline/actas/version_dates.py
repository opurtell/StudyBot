"""Copy guideline version dates from the CMG list-page crawl onto structured files."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from paths import service_structured_dir

logger = logging.getLogger(__name__)

DISCOVERY_PATH = "data/cmgs/raw/discovery_metadata.json"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _keys(doc: dict) -> set[str]:
    title = _norm(doc.get("title", ""))
    number = str(doc.get("cmg_number", "")).strip()
    keys = {title}
    if number:
        keys.add(_norm(f"{number} {title}"))
        keys.add(_norm(f"cmg {number} {title}"))
    return keys


def _structured_files(structured_dir: Path) -> list[Path]:
    files = sorted(structured_dir.glob("*.json"))
    for sub in ("csm", "med"):
        files.extend(sorted((structured_dir / sub).glob("*.json")))
    return [f for f in files if "index" not in f.name and not f.name.startswith(".")]


def apply_version_dates(
    discovery_path: str = DISCOVERY_PATH,
    structured_dir: str = str(service_structured_dir("actas")),
) -> dict[str, Any]:
    with open(discovery_path, "r", encoding="utf-8") as f:
        discovered = json.load(f).get("guidelines", [])

    by_key: dict[str, str] = {}
    for g in discovered:
        if g.get("date"):
            by_key[_norm(g.get("title", ""))] = f"{g['date']} Version {g.get('version', '')}".strip()

    updated, unchanged, missing = [], 0, []
    for path in _structured_files(Path(structured_dir)):
        data = json.loads(path.read_text(encoding="utf-8"))
        version = next((by_key[k] for k in _keys(data) if k in by_key), None)
        if version is None:
            missing.append(path.name)
            continue
        if data.get("version_date") == version:
            unchanged += 1
            continue
        data["version_date"] = version
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        updated.append(path.name)

    if missing:
        logger.warning("No version date found for %d file(s): %s", len(missing), ", ".join(missing))
    return {"updated": updated, "unchanged": unchanged, "missing": missing}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = apply_version_dates(
        os.environ.get("ACTAS_DISCOVERY_PATH", DISCOVERY_PATH),
    )
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in summary.items()}))
