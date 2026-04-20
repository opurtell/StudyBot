"""
Medication Denormalisation Index Builder for AT Pipeline.

Reads all structured JSON files in AT's structured directory,
extracts every medication from guideline ``medications`` lists,
aggregates all dose entries by medication name across all guidelines,
and writes one JSON file per medication to the output directory.

Usage::

    python3 -m src.python.pipeline.at.medications_index \\
        data/services/at/structured \\
        data/services/at/medications
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _sanitise_name(name: str) -> str:
    """Lowercase, spaces to hyphens, strip non-alphanumeric/hyphen chars.

    Args:
        name: Medicine name (e.g. "Adrenaline", "Ipratropium Bromide")

    Returns:
        Sanitised slug (e.g. "adrenaline", "ipratropium-bromide")
    """
    name = name.lower().replace(" ", "-")
    # Remove special characters like parentheses, commas, etc.
    return re.sub(r"[^a-z0-9\-]", "", name)


def build_medications_index(
    structured_dir: str | Path,
    output_dir: str | Path,
) -> int:
    """Build per-medication denormalised index files for AT.

    Iterates all AT guideline JSON files (both medicine monographs and
    clinical guidelines with medications), extracts all MedicationDose
    entries, and aggregates them into one file per medicine.

    Parameters
    ----------
    structured_dir:
        Directory containing structured AT JSON files (each with a
        ``medications`` key).
    output_dir:
        Directory to write per-medication JSON files into. Created
        automatically if it does not exist.

    Returns
    -------
    int
        Count of unique medicine index files produced.
    """
    structured_dir = Path(structured_dir)
    output_dir = Path(output_dir)

    # Aggregate entries keyed by medication name
    index: dict[str, list[dict[str, Any]]] = {}

    for json_file in sorted(structured_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        medications: list[dict[str, Any]] | None = data.get("medications")
        if not medications:
            # Skip guidelines with no medications
            continue

        guideline_id: str = data.get("guideline_id", "")
        service: str = data.get("service", "at")

        for med_entry in medications:
            med_name = med_entry.get("medication", "")
            if not med_name:
                continue

            if med_name not in index:
                index[med_name] = []

            # Build enriched entry with all MedicationDose fields plus metadata
            enriched_entry = {
                # All MedicationDose fields
                "medication": med_entry.get("medication", ""),
                "indication": med_entry.get("indication", ""),
                "dose": med_entry.get("dose", ""),
                "route": med_entry.get("route", ""),
                "qualifications_required": med_entry.get("qualifications_required", []),
                # Metadata fields
                "service": service,
                "guideline_id": guideline_id,
                "source_file": json_file.name,
            }

            index[med_name].append(enriched_entry)

    # Write output files
    output_dir.mkdir(parents=True, exist_ok=True)

    for med_name, entries in sorted(index.items()):
        # Collect unique source guideline IDs
        sources = sorted({e["guideline_id"] for e in entries if e["guideline_id"]})

        out = {
            "medication": med_name,
            "service": "at",
            "entries": entries,
            "total_entries": len(entries),
            "sources": sources,
        }

        safe_name = _sanitise_name(med_name)
        out_path = output_dir / f"{safe_name}.json"
        out_path.write_text(
            json.dumps(out, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )

    return len(index)


def main() -> None:
    """CLI entrypoint."""
    import sys

    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <structured_dir> <output_dir>", file=sys.stderr)
        sys.exit(1)

    structured_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    count = build_medications_index(structured_dir, output_dir)

    # Calculate total entries across all medicines
    total_entries = sum(
        json.loads((output_dir / f).read_text()).get("total_entries", 0)
        for f in output_dir.glob("*.json")
    )

    print(f"Generated {count} medication files ({total_entries} total dose entries)")
    for med_file in sorted(output_dir.glob("*.json")):
        data = json.loads(med_file.read_text())
        print(f"  {data['medication']}: {data['total_entries']}")


if __name__ == "__main__":
    main()
