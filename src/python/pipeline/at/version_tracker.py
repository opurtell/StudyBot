"""Stage 7: Version Tracking for AT pipeline.

Maintains version tracking for incremental re-scraping of AT CPGs.
Tracks content hashes to detect new, modified, and unchanged guidelines.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def compute_source_hash(content: Dict) -> str:
    """Compute SHA-256 hash of content using canonical JSON representation.

    Args:
        content: Dictionary containing guideline content

    Returns:
        Hexadecimal SHA-256 hash string
    """
    # Use canonical JSON: sorted keys, no extra whitespace, deterministic
    content_str = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()


def detect_changes(
    previous: Dict[str, Dict], current: Dict[str, Dict]
) -> Tuple[List[str], List[str], List[str]]:
    """Detect new, modified, and unchanged CPGs by comparing hashes.

    Args:
        previous: Dictionary mapping CPG codes to their previous records
            (each with at least a "hash" key)
        current: Dictionary mapping CPG codes to their current records
            (each with at least a "hash" key)

    Returns:
        Tuple of (new_codes, modified_codes, unchanged_codes) as lists
    """
    new = []
    modified = []
    unchanged = []

    for cpg_code, current_record in current.items():
        current_hash = current_record.get("hash", "")

        if cpg_code not in previous:
            # New CPG
            new.append(cpg_code)
        else:
            previous_hash = previous[cpg_code].get("hash", "")
            if current_hash != previous_hash:
                # Modified CPG
                modified.append(cpg_code)
            else:
                # Unchanged CPG
                unchanged.append(cpg_code)

    return new, modified, unchanged


def update_version_tracking(
    structured_dir: str, tracker_path: str
) -> Dict[str, Any]:
    """Update version tracking by comparing current structured files to previous tracker.

    Args:
        structured_dir: Directory containing structured AT guideline JSON files
        tracker_path: Path to version tracker JSON file

    Returns:
        Summary dictionary with keys:
            - total_count: Total number of guidelines processed
            - new_count: Number of new guidelines
            - modified_count: Number of modified guidelines
            - unchanged_count: Number of unchanged guidelines
    """
    # Load existing tracker
    previous_tracker: Dict[str, Dict] = {}
    if os.path.exists(tracker_path):
        try:
            with open(tracker_path, "r", encoding="utf-8") as f:
                previous_tracker = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load previous tracker: {e}")
            previous_tracker = {}

    # Scan structured directory for current guidelines
    current_records: Dict[str, Dict] = {}
    errors = []

    if not os.path.exists(structured_dir):
        logger.error(f"Structured directory not found: {structured_dir}")
        return {
            "total_count": 0,
            "new_count": 0,
            "modified_count": 0,
            "unchanged_count": 0,
        }

    for filename in os.listdir(structured_dir):
        # Only process AT_CPG_*.json files
        if not filename.startswith("AT_CPG_") or not filename.endswith(".json"):
            continue

        file_path = os.path.join(structured_dir, filename)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except Exception as e:
            error_msg = f"Failed to read {filename}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            continue

        # Extract CPG code from guideline_id (e.g., "AT_CPG_A0201-1" -> "A0201-1")
        guideline_id = doc.get("guideline_id", "")
        if guideline_id.startswith("AT_CPG_"):
            cpg_code = guideline_id[7:]  # Remove "AT_CPG_" prefix
        else:
            # Fallback: try to extract from filename
            cpg_code = filename.replace("AT_CPG_", "").replace(".json", "")

        # Build current record
        current_records[cpg_code] = {
            "hash": doc.get("source_hash", compute_source_hash(doc)),
            "title": doc.get("title", ""),
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }

    # Detect changes
    new, modified, unchanged = detect_changes(previous_tracker, current_records)

    # Build updated tracker (merge current records with previous metadata)
    updated_tracker: Dict[str, Dict] = {}
    for cpg_code, record in current_records.items():
        # Preserve any additional metadata from previous tracker
        if cpg_code in previous_tracker:
            previous_record = previous_tracker[cpg_code]
            # Keep previous metadata but update hash and last_seen
            updated_tracker[cpg_code] = {
                **previous_record,  # Preserve old metadata
                **record,  # Override with new values
            }
        else:
            updated_tracker[cpg_code] = record

    # Write updated tracker
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
    with open(tracker_path, "w", encoding="utf-8") as f:
        json.dump(updated_tracker, f, indent=2)

    logger.info(f"Version tracking updated: {len(new)} new, {len(modified)} modified, {len(unchanged)} unchanged")

    return {
        "total_count": len(current_records),
        "new_count": len(new),
        "modified_count": len(modified),
        "unchanged_count": len(unchanged),
        "new_codes": new,
        "modified_codes": modified,
        "unchanged_codes": unchanged,
        "errors": errors,
    }
