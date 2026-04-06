"""Validate and normalise cleaned markdown files before chunking.

Checks that YAML front matter has all required fields and normalises
body whitespace. Does not modify semantic content.
"""

import re
from pathlib import Path

import yaml

REQUIRED_FIELDS = [
    "title",
    "subject",
    "categories",
    "source_file",
    "last_modified",
    "review_flags",
]


def validate_and_normalise(md_path: Path) -> dict:
    """Validate front matter and normalise body of a cleaned .md file.

    Returns a dict with validation result and parsed metadata.
    Writes the normalised file back in-place if valid.
    """
    content = md_path.read_text()

    # Split front matter from body
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {
            "valid": False,
            "error": "No YAML front matter found",
            "file": str(md_path),
        }

    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return {"valid": False, "error": f"Invalid YAML: {e}", "file": str(md_path)}

    if not isinstance(meta, dict):
        return {
            "valid": False,
            "error": "Front matter is not a dict",
            "file": str(md_path),
        }

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field == "review_flags":
            continue
        if field not in meta:
            return {
                "valid": False,
                "error": f"Missing field: {field}",
                "file": str(md_path),
            }

    if "review_flags" not in meta:
        meta["review_flags"] = []

    # Normalise body — collapse 3+ newlines to 2
    body = parts[2]
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = body.strip() + "\n"

    # Write back normalised version
    fm_str = yaml.dump(meta, default_flow_style=False, allow_unicode=True)
    md_path.write_text(f"---\n{fm_str}---\n{body}")

    review_flags = meta.get("review_flags", [])
    return {
        "valid": True,
        "file": str(md_path),
        "title": meta["title"],
        "source_file": meta["source_file"],
        "categories": meta["categories"],
        "last_modified": meta["last_modified"],
        "has_review_flag": bool(review_flags),
        "review_flags": review_flags,
    }
