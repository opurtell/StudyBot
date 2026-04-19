"""One-shot, idempotent migration script for the multi-service foundation.

Migrates data from the legacy single-service layout to the per-service layout
introduced in Phase 2b.  Safe to rerun — all steps are no-ops if already done.

Usage (standalone)::

    python3 scripts/migrate_to_multi_service.py

Or from tests::

    from migrate_to_multi_service import run_migration
    run_migration(repo_root=Path("/path/to/repo"))
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

# The service that legacy ACTAS data belongs to.
_SERVICE = "actas"

# Regex for deriving guideline_id: match 'CMG_<digits>' at the start of the stem.
_CMG_PREFIX_RE = re.compile(r"^(CMG_\d+)")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_migration(repo_root: Path) -> None:
    """Run all migration steps against *repo_root*.

    Steps:
    1. Move ``data/cmgs/structured/*.json`` → ``data/services/actas/structured/``
       enriching each document with ``service``, ``guideline_id``, and ``extra``.
    2. Move ``data/uploads/`` contents → ``data/services/actas/uploads/``
    3. Inject ``service`` and ``scope`` YAML front-matter into every file under
       ``data/personal_docs/structured/``.
    4. Write ``active_service: "actas"`` to ``config/settings.json`` if unset.
    5. Rewrite legacy ``skill_level`` to ``base_qualification`` + ``endorsements``.
    """
    _migrate_cmg_files(repo_root)
    _migrate_uploads(repo_root)
    _inject_personal_doc_front_matter(repo_root)
    _update_settings(repo_root)


# ---------------------------------------------------------------------------
# Step 1: CMG structured JSON files
# ---------------------------------------------------------------------------


def _derive_guideline_id(stem: str) -> str:
    """Return the ``CMG_<n>`` prefix from a filename stem.

    Examples::

        CMG_14_Anaphylaxis → CMG_14
        CMG_3_Chest_Pain   → CMG_3
    """
    match = _CMG_PREFIX_RE.match(stem)
    if match:
        return match.group(1)
    # Fallback: use the full stem (handles non-standard names gracefully)
    return stem


def _migrate_cmg_files(repo_root: Path) -> None:
    """Move and enrich CMG JSON files from the legacy location."""
    src_dir = repo_root / "data" / "cmgs" / "structured"
    dest_dir = repo_root / "data" / "services" / _SERVICE / "structured"

    if not src_dir.exists():
        log.info("CMG source dir %s does not exist — skipping CMG migration.", src_dir)
        return

    dest_dir.mkdir(parents=True, exist_ok=True)

    for json_file in src_dir.glob("*.json"):
        dest_file = dest_dir / json_file.name

        if dest_file.exists():
            # Already migrated — check idempotency guard on the destination file.
            doc = json.loads(dest_file.read_text(encoding="utf-8"))
            if doc.get("service") == _SERVICE:
                log.debug("Skipping already-migrated %s.", json_file.name)
                # Clean up orphaned source file from an interrupted previous run.
                if json_file.exists():
                    json_file.unlink()
                continue

        doc = json.loads(json_file.read_text(encoding="utf-8"))

        # Enrich document.
        doc["service"] = _SERVICE
        doc["guideline_id"] = _derive_guideline_id(json_file.stem)

        # Preserve legacy cmg_number in extra sub-dict.
        if "cmg_number" in doc:
            if "extra" not in doc:
                doc["extra"] = {}
            if "cmg_number" not in doc.get("extra", {}):
                doc["extra"]["cmg_number"] = doc["cmg_number"]

        dest_file.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Migrated %s → %s", json_file, dest_file)

        # Remove source file after successful write.
        json_file.unlink()

    # Remove the now-empty source directory if all files have been moved.
    try:
        src_dir.rmdir()
    except OSError:
        pass  # Not empty — leave it; not our problem.


# ---------------------------------------------------------------------------
# Step 2: Uploads
# ---------------------------------------------------------------------------


def _migrate_uploads(repo_root: Path) -> None:
    """Move all files from data/uploads/ to data/services/actas/uploads/."""
    src_dir = repo_root / "data" / "uploads"
    dest_dir = repo_root / "data" / "services" / _SERVICE / "uploads"

    if not src_dir.exists():
        log.info("Uploads source dir %s does not exist — skipping.", src_dir)
        return

    dest_dir.mkdir(parents=True, exist_ok=True)

    for item in src_dir.iterdir():
        if item.is_dir():
            dest_item = dest_dir / item.name
            if dest_item.exists():
                log.debug("Upload dir %s already migrated.", item.name)
                continue
            shutil.copytree(item, dest_item)
            shutil.rmtree(item)
        else:
            dest_item = dest_dir / item.name
            if dest_item.exists():
                log.debug("Upload file %s already migrated.", item.name)
                item.unlink()
                continue
            shutil.move(str(item), str(dest_item))
            log.info("Migrated upload %s → %s", item, dest_item)

    # Remove empty source directory.
    try:
        src_dir.rmdir()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Step 3: Personal docs YAML front-matter injection
# ---------------------------------------------------------------------------

_FRONT_MATTER_FENCE = "---"
_SERVICE_KEY = "service"
_SCOPE_KEY = "scope"
_SERVICE_VALUE = _SERVICE
_SCOPE_VALUE = "service-specific"


def _inject_personal_doc_front_matter(repo_root: Path) -> None:
    """Add service and scope keys to YAML front-matter of personal docs."""
    structured_dir = repo_root / "data" / "personal_docs" / "structured"
    if not structured_dir.exists():
        log.info("Personal docs dir %s does not exist — skipping.", structured_dir)
        return

    for md_file in structured_dir.glob("*.md"):
        _patch_front_matter(md_file)


def _patch_front_matter(md_file: Path) -> None:
    """Inject service/scope into the YAML front-matter of *md_file* (idempotent)."""
    content = md_file.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # Detect whether the file starts with a front-matter block.
    if lines and lines[0].rstrip() == _FRONT_MATTER_FENCE:
        # Find the closing fence.
        close_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.rstrip() == _FRONT_MATTER_FENCE:
                close_idx = i
                break

        if close_idx is not None:
            # Extract existing front-matter lines (between fences).
            fm_lines = lines[1:close_idx]
            body_lines = lines[close_idx + 1:]

            fm_text = "".join(fm_lines)

            # Check if keys already present.
            service_present = re.search(
                rf"^{_SERVICE_KEY}\s*:", fm_text, re.MULTILINE
            ) is not None
            scope_present = re.search(
                rf"^{_SCOPE_KEY}\s*:", fm_text, re.MULTILINE
            ) is not None

            if service_present and scope_present:
                return  # Nothing to do.

            # Insert missing keys just before the closing fence.
            new_fm_lines = list(fm_lines)
            if not service_present:
                new_fm_lines.append(f"{_SERVICE_KEY}: {_SERVICE_VALUE}\n")
            if not scope_present:
                new_fm_lines.append(f"{_SCOPE_KEY}: {_SCOPE_VALUE}\n")

            new_content = (
                _FRONT_MATTER_FENCE + "\n"
                + "".join(new_fm_lines)
                + _FRONT_MATTER_FENCE + "\n"
                + "".join(body_lines)
            )
            md_file.write_text(new_content, encoding="utf-8")
            log.info("Patched front-matter in %s.", md_file.name)
            return

    # No front-matter block — prepend a new one.
    new_front_matter = (
        f"{_FRONT_MATTER_FENCE}\n"
        f"{_SERVICE_KEY}: {_SERVICE_VALUE}\n"
        f"{_SCOPE_KEY}: {_SCOPE_VALUE}\n"
        f"{_FRONT_MATTER_FENCE}\n"
    )
    md_file.write_text(new_front_matter + content, encoding="utf-8")
    log.info("Injected front-matter into %s.", md_file.name)


# ---------------------------------------------------------------------------
# Step 4 & 5: Settings updates
# ---------------------------------------------------------------------------


def _update_settings(repo_root: Path) -> None:
    """Update config/settings.json with active_service and qualification fields."""
    settings_path = repo_root / "config" / "settings.json"
    if not settings_path.exists():
        log.info("settings.json not found at %s — skipping settings update.", settings_path)
        return

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    changed = False

    # Step 4: Set active_service if unset.
    if "active_service" not in data:
        data["active_service"] = _SERVICE
        changed = True
        log.info("Set active_service=%s in settings.json.", _SERVICE)

    # Step 5: Rewrite legacy skill_level.
    if "skill_level" in data:
        skill_level = data.pop("skill_level")
        data["base_qualification"] = skill_level
        data["endorsements"] = []
        changed = True
        log.info(
            "Rewrote skill_level=%s → base_qualification=%s, endorsements=[].",
            skill_level,
            skill_level,
        )

    if changed:
        settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_migration(Path.cwd())
    print("Migration complete.")
