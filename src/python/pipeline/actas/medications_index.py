"""
Medication Denormalisation Index Builder.

Reads all structured JSON files in a service's structured directory,
extracts every medication from ``dose_lookup`` dicts, aggregates all dose
entries by medication name across all guidelines, and writes one JSON file
per medication to the output directory.

Usage::

    python3 -m src.python.pipeline.actas.medications_index \\
        data/services/actas/structured \\
        data/services/actas/medications
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


def _sanitise_name(name: str) -> str:
    """Lowercase, spaces to hyphens, strip non-alphanumeric/hyphen chars."""
    name = name.lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9\-]", "", name)


def build_medication_index(
    structured_dir: Path,
    output_dir: Path,
) -> dict[str, int]:
    """Build per-medication denormalised index files.

    Parameters
    ----------
    structured_dir:
        Directory containing structured service JSON files (each with a
        ``dose_lookup`` key).
    output_dir:
        Directory to write per-medication JSON files into.  Created
        automatically if it does not exist.

    Returns
    -------
    dict[str, int]
        Mapping of ``{medication_name: total_dose_entries}``.
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

        dose_lookup: dict[str, list[dict[str, Any]]] | None = data.get("dose_lookup")
        if not dose_lookup:
            continue

        guideline_id: str = data.get("guideline_id", "")
        cmg_number: str = data.get("cmg_number", "")
        title: str = data.get("title", "")
        service: str = data.get("service", "actas")
        # Top-level qualifications (guideline-wide default)
        top_level_quals: list[str] = data.get("qualifications_required", [])

        for med_name, entries in dose_lookup.items():
            if med_name not in index:
                index[med_name] = []

            for entry in entries:
                # Per-entry qualifications take precedence if present;
                # fall back to top-level guideline qualifications.
                quals: list[str] = entry.get("qualifications_required", top_level_quals)
                if not isinstance(quals, list):
                    quals = top_level_quals

                index[med_name].append({
                    "guideline_id": guideline_id,
                    "cmg_number": cmg_number,
                    "source_title": title,
                    "text": entry.get("text", ""),
                    "dose_values": entry.get("dose_values", []),
                    "qualifications_required": quals,
                    "service": service,
                })

    # Write output
    output_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, int] = {}
    for med_name, entries in sorted(index.items()):
        sources = sorted({e["guideline_id"] for e in entries if e["guideline_id"]})
        out = {
            "medication": med_name,
            "service": "actas",
            "dose_entries": entries,
            "total_entries": len(entries),
            "sources": sources,
        }
        safe_name = _sanitise_name(med_name)
        out_path = output_dir / f"{safe_name}.json"
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result[med_name] = len(entries)

    return result


def main() -> None:
    """CLI entrypoint."""
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <structured_dir> <output_dir>", file=sys.stderr)
        sys.exit(1)

    structured_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    result = build_medication_index(structured_dir, output_dir)
    total_meds = len(result)
    total_entries = sum(result.values())
    print(f"Generated {total_meds} medication files ({total_entries} total dose entries)")
    for name, count in sorted(result.items()):
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
