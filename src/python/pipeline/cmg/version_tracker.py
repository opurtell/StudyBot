"""
Stage 7: Version Tracking
Maintains a CSV file tracing checksums of extracted CMGs over time.
"""

import csv
import glob
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def update_version_tracking(
    structured_dir: str = "data/cmgs/structured/",
    tracking_csv: str = "data/cmgs/version_tracking.csv",
)-> dict[str, Any]:
    """Update version tracking CSV against structured CMGs."""
    json_files = glob.glob(os.path.join(structured_dir, "*.json"))
    json_files.extend(glob.glob(os.path.join(structured_dir, "med", "*.json")))
    json_files.extend(glob.glob(os.path.join(structured_dir, "csm", "*.json")))

    # Load existing tracking
    existing_records = {}
    if os.path.exists(tracking_csv):
        with open(tracking_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_records[row["id"]] = row

    new_records = []

    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            continue

        cmg_id = data.get("id")
        title = data.get("title")
        version_date = data.get("version_date", "")
        checksum = data.get("checksum", "")
        last_extracted = datetime.now(timezone.utc).isoformat()

        status = "new"
        if cmg_id in existing_records:
            old_record = existing_records[cmg_id]
            if old_record["checksum"] == checksum:
                status = "unchanged"
            else:
                status = "updated"

        new_records.append(
            {
                "id": cmg_id,
                "title": title,
                "version_date": version_date,
                "checksum": checksum,
                "status": status,
                "last_extracted": last_extracted,
            }
        )

    # Write back
    os.makedirs(os.path.dirname(tracking_csv), exist_ok=True)
    with open(tracking_csv, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "id",
            "title",
            "version_date",
            "checksum",
            "status",
            "last_extracted",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        for rec in new_records:
            writer.writerow(rec)

    logger.info(f"Version tracking updated at {tracking_csv}")
    summary = {
        "checked_item_count": len(new_records),
        "new_count": sum(1 for rec in new_records if rec["status"] == "new"),
        "updated_count": sum(1 for rec in new_records if rec["status"] == "updated"),
        "unchanged_count": sum(
            1 for rec in new_records if rec["status"] == "unchanged"
        ),
        "error_count": 0,
        "items": new_records,
    }
    return summary
