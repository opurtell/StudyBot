"""Idempotent backfill script: add ``qualifications_required`` to every
structured JSON file in ``data/services/actas/structured/``.

Two levels are tagged:

1. **Document level** (root ``qualifications_required`` key):
   - ``is_icp_only: True``  →  ``["ICP"]``
   - otherwise              →  ``["AP"]``

2. **Medicine level** (each dose-entry dict inside ``dose_lookup``):
   - medicine name in ICP_DRUGS  →  ``["ICP"]``
   - otherwise                   →  ``["AP"]``

The script is idempotent — re-running on already-tagged files is a no-op.

Usage (from the repo root)::

    python scripts/backfill_actas_qualifications.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Authoritative ICP-only drug list (user-signed-off, do not modify without
# explicit user instruction).
# ---------------------------------------------------------------------------
ICP_DRUGS: frozenset[str] = frozenset(
    {
        "Adenosine",
        "Amiodarone",
        "Heparin",
        "Hydrocortisone",
        "Lignocaine",
        "Sodium Bicarbonate",
        "Suxamethonium",
        "Levetiracetam",
    }
)

# Default path relative to repo root.
_DEFAULT_DIR = Path(__file__).parent.parent / "data" / "services" / "actas" / "structured"


def _qualification_for_medicine(medicine_name: str) -> list[str]:
    """Return the qualification list for a given medicine name."""
    return ["ICP"] if medicine_name in ICP_DRUGS else ["AP"]


def _qualification_for_document(doc: dict) -> list[str]:
    """Return the qualification list for a document based on is_icp_only."""
    return ["ICP"] if doc.get("is_icp_only") else ["AP"]


def backfill_file(path: Path, *, dry_run: bool = False) -> bool:
    """Backfill a single JSON file.  Returns True if the file was modified."""
    data: dict = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    # --- Document level ---
    expected_doc_qual = _qualification_for_document(data)
    if data.get("qualifications_required") != expected_doc_qual:
        data["qualifications_required"] = expected_doc_qual
        changed = True

    # --- Medicine level ---
    dose_lookup: dict = data.get("dose_lookup") or {}
    for medicine_name, entries in dose_lookup.items():
        expected_med_qual = _qualification_for_medicine(medicine_name)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("qualifications_required") != expected_med_qual:
                entry["qualifications_required"] = expected_med_qual
                changed = True

    if changed and not dry_run:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    return changed


def backfill_directory(
    directory: Path | str, *, dry_run: bool = False
) -> dict[str, bool]:
    """Backfill all ``*.json`` files in *directory*.

    Returns a mapping of filename → changed (bool).
    """
    directory = Path(directory)
    results: dict[str, bool] = {}
    for json_file in sorted(directory.glob("*.json")):
        results[json_file.name] = backfill_file(json_file, dry_run=dry_run)
    return results


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill qualifications_required on ACTAS structured JSON files."
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=_DEFAULT_DIR,
        help="Path to the structured JSON directory (default: %(default)s).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    directory: Path = args.directory
    dry_run: bool = args.dry_run

    if not directory.is_dir():
        print(f"ERROR: directory does not exist: {directory}", file=sys.stderr)
        return 1

    results = backfill_directory(directory, dry_run=dry_run)
    modified = [name for name, changed in results.items() if changed]
    unchanged = [name for name, changed in results.items() if not changed]

    prefix = "[DRY-RUN] " if dry_run else ""
    if modified:
        print(f"{prefix}Modified {len(modified)} file(s):")
        for name in modified:
            print(f"  {name}")
    if unchanged:
        print(f"{prefix}Unchanged: {len(unchanged)} file(s) already up to date.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
