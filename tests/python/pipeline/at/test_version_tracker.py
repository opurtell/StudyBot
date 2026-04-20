"""Tests for AT pipeline version tracking."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.python.pipeline.at.version_tracker import (
    compute_source_hash,
    detect_changes,
    update_version_tracking,
)


def test_compute_source_hash_deterministic():
    """Hash computation should be deterministic for identical content."""
    content = {"cpg_code": "A0201-1", "body": "Cardiac arrest management."}
    h1 = compute_source_hash(content)
    h2 = compute_source_hash(content)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 produces 64 hex characters
    assert isinstance(h1, str)


def test_compute_source_hash_different_content():
    """Different content should produce different hashes."""
    content1 = {"cpg_code": "A0201-1", "body": "Cardiac arrest management."}
    content2 = {"cpg_code": "A0201-1", "body": "Cardiac arrest management updated."}
    h1 = compute_source_hash(content1)
    h2 = compute_source_hash(content2)
    assert h1 != h2


def test_compute_source_hash_order_independent():
    """Hash should be independent of key order (canonical JSON)."""
    content1 = {"cpg_code": "A0201-1", "body": "Cardiac arrest management."}
    content2 = {"body": "Cardiac arrest management.", "cpg_code": "A0201-1"}
    h1 = compute_source_hash(content1)
    h2 = compute_source_hash(content2)
    assert h1 == h2


def test_compute_source_hash_with_nested_structures():
    """Hash should handle nested dictionaries and lists."""
    content = {
        "cpg_code": "A0201-1",
        "sections": [
            {"heading": "Assessment", "body": "ABCDE approach"},
            {"heading": "Management", "body": " CPR and defibrillation"},
        ],
        "medications": [
            {"medication": "Adrenaline", "dose": "1 mg IV"}
        ],
    }
    h = compute_source_hash(content)
    assert len(h) == 64
    assert isinstance(h, str)


def test_detect_changes_identifies_new_and_modified():
    """Change detection should correctly identify new, modified, and unchanged CPGs."""
    previous = {
        "A0201-1": {"hash": "abc123"},
        "A0300": {"hash": "def456"},
    }
    current = {
        "A0201-1": {"hash": "abc123"},  # Unchanged
        "A0300": {"hash": "xyz789"},    # Modified
        "A0401": {"hash": "new123"},    # New
    }

    new, modified, unchanged = detect_changes(previous, current)

    assert new == ["A0401"]
    assert modified == ["A0300"]
    assert unchanged == ["A0201-1"]


def test_detect_changes_all_new():
    """When all CPGs are new, only new list should be populated."""
    previous = {}
    current = {
        "A0201-1": {"hash": "abc123"},
        "A0300": {"hash": "def456"},
    }

    new, modified, unchanged = detect_changes(previous, current)

    assert set(new) == {"A0201-1", "A0300"}
    assert modified == []
    assert unchanged == []


def test_detect_changes_all_unchanged():
    """When no CPGs changed, only unchanged list should be populated."""
    previous = {
        "A0201-1": {"hash": "abc123"},
        "A0300": {"hash": "def456"},
    }
    current = {
        "A0201-1": {"hash": "abc123"},
        "A0300": {"hash": "def456"},
    }

    new, modified, unchanged = detect_changes(previous, current)

    assert new == []
    assert modified == []
    assert set(unchanged) == {"A0201-1", "A0300"}


def test_detect_changes_deleted_cpgs():
    """Deleted CPGs should appear in neither list (they're not in current)."""
    previous = {
        "A0201-1": {"hash": "abc123"},
        "A0300": {"hash": "def456"},
        "DELETED": {"hash": "gone"},
    }
    current = {
        "A0201-1": {"hash": "abc123"},
        "A0300": {"hash": "def456"},
    }

    new, modified, unchanged = detect_changes(previous, current)

    assert new == []
    assert modified == []
    assert set(unchanged) == {"A0201-1", "A0300"}
    assert "DELETED" not in unchanged


def test_update_version_tracking_new_structured_dir(tmp_path):
    """Version tracking should handle new structured directory (no previous tracker)."""
    # Create test structured files
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Create test guideline files
    guideline1 = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "qualifications_required": [],
        "content_sections": [{"heading": "Assessment", "body": "ABCDE"}],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_url": "https://example.com/A0201-1",
        "source_hash": "hash1",
        "last_modified": "2026-04-20",
        "extra": {},
    }

    guideline2 = {
        "service": "at",
        "guideline_id": "AT_CPG_D003",
        "title": "Adrenaline",
        "categories": ["Medication Guidelines"],
        "qualifications_required": [],
        "content_sections": [{"heading": "Indications", "body": "Cardiac arrest"}],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_url": "https://example.com/D003",
        "source_hash": "hash2",
        "last_modified": "2026-04-20",
        "extra": {},
    }

    with open(structured_dir / "AT_CPG_A0201-1.json", "w") as f:
        json.dump(guideline1, f)

    with open(structured_dir / "AT_CPG_D003.json", "w") as f:
        json.dump(guideline2, f)

    # Create tracker path
    tracker_path = tmp_path / "version_tracker.json"

    # Run version tracking
    summary = update_version_tracking(
        structured_dir=str(structured_dir),
        tracker_path=str(tracker_path),
    )

    # Verify summary
    assert summary["total_count"] == 2
    assert summary["new_count"] == 2
    assert summary["modified_count"] == 0
    assert summary["unchanged_count"] == 0

    # Verify tracker file was created
    assert tracker_path.exists()

    with open(tracker_path, "r") as f:
        tracker = json.load(f)

    assert "A0201-1" in tracker
    assert "D003" in tracker
    assert tracker["A0201-1"]["hash"] == "hash1"
    assert tracker["D003"]["hash"] == "hash2"


def test_update_version_tracking_detects_modifications(tmp_path):
    """Version tracking should detect modified guidelines."""
    # Create structured directory
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Create existing tracker
    tracker_path = tmp_path / "version_tracker.json"
    existing_tracker = {
        "A0201-1": {"hash": "old_hash1", "title": "Cardiac Arrest"},
        "D003": {"hash": "hash2", "title": "Adrenaline"},
    }

    with open(tracker_path, "w") as f:
        json.dump(existing_tracker, f)

    # Create test guideline files (one modified, one unchanged)
    guideline1 = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "qualifications_required": [],
        "content_sections": [{"heading": "Assessment", "body": "ABCDE updated"}],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_url": "https://example.com/A0201-1",
        "source_hash": "new_hash1",  # Modified
        "last_modified": "2026-04-20",
        "extra": {},
    }

    guideline2 = {
        "service": "at",
        "guideline_id": "AT_CPG_D003",
        "title": "Adrenaline",
        "categories": ["Medication Guidelines"],
        "qualifications_required": [],
        "content_sections": [{"heading": "Indications", "body": "Cardiac arrest"}],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_url": "https://example.com/D003",
        "source_hash": "hash2",  # Unchanged
        "last_modified": "2026-04-20",
        "extra": {},
    }

    with open(structured_dir / "AT_CPG_A0201-1.json", "w") as f:
        json.dump(guideline1, f)

    with open(structured_dir / "AT_CPG_D003.json", "w") as f:
        json.dump(guideline2, f)

    # Run version tracking
    summary = update_version_tracking(
        structured_dir=str(structured_dir),
        tracker_path=str(tracker_path),
    )

    # Verify summary
    assert summary["total_count"] == 2
    assert summary["new_count"] == 0
    assert summary["modified_count"] == 1
    assert summary["unchanged_count"] == 1

    # Verify tracker was updated
    with open(tracker_path, "r") as f:
        tracker = json.load(f)

    assert tracker["A0201-1"]["hash"] == "new_hash1"
    assert tracker["D003"]["hash"] == "hash2"


def test_update_version_tracking_with_new_additions(tmp_path):
    """Version tracking should detect new guidelines added to existing tracker."""
    # Create structured directory
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Create existing tracker
    tracker_path = tmp_path / "version_tracker.json"
    existing_tracker = {
        "A0201-1": {"hash": "hash1", "title": "Cardiac Arrest"},
    }

    with open(tracker_path, "w") as f:
        json.dump(existing_tracker, f)

    # Create test guideline files
    guideline1 = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "qualifications_required": [],
        "content_sections": [{"heading": "Assessment", "body": "ABCDE"}],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_url": "https://example.com/A0201-1",
        "source_hash": "hash1",
        "last_modified": "2026-04-20",
        "extra": {},
    }

    guideline2 = {
        "service": "at",
        "guideline_id": "AT_CPG_D003",
        "title": "Adrenaline",
        "categories": ["Medication Guidelines"],
        "qualifications_required": [],
        "content_sections": [{"heading": "Indications", "body": "Cardiac arrest"}],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_url": "https://example.com/D003",
        "source_hash": "hash2",
        "last_modified": "2026-04-20",
        "extra": {},
    }

    with open(structured_dir / "AT_CPG_A0201-1.json", "w") as f:
        json.dump(guideline1, f)

    with open(structured_dir / "AT_CPG_D003.json", "w") as f:
        json.dump(guideline2, f)

    # Run version tracking
    summary = update_version_tracking(
        structured_dir=str(structured_dir),
        tracker_path=str(tracker_path),
    )

    # Verify summary
    assert summary["total_count"] == 2
    assert summary["new_count"] == 1
    assert summary["modified_count"] == 0
    assert summary["unchanged_count"] == 1

    # Verify tracker was updated
    with open(tracker_path, "r") as f:
        tracker = json.load(f)

    assert "A0201-1" in tracker
    assert "D003" in tracker


def test_update_version_tracking_empty_structured_dir(tmp_path):
    """Version tracking should handle empty structured directory."""
    # Create empty structured directory
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Create existing tracker
    tracker_path = tmp_path / "version_tracker.json"
    existing_tracker = {
        "A0201-1": {"hash": "hash1", "title": "Cardiac Arrest"},
    }

    with open(tracker_path, "w") as f:
        json.dump(existing_tracker, f)

    # Run version tracking
    summary = update_version_tracking(
        structured_dir=str(structured_dir),
        tracker_path=str(tracker_path),
    )

    # Verify summary
    assert summary["total_count"] == 0
    assert summary["new_count"] == 0
    assert summary["modified_count"] == 0
    assert summary["unchanged_count"] == 0

    # Verify tracker is now empty
    with open(tracker_path, "r") as f:
        tracker = json.load(f)

    assert tracker == {}


def test_update_version_tracking_handles_missing_files(tmp_path):
    """Version tracking should handle structured files that don't match expected pattern."""
    # Create structured directory
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Create tracker
    tracker_path = tmp_path / "version_tracker.json"

    # Create non-JSON file (should be ignored)
    with open(structured_dir / "README.txt", "w") as f:
        f.write("This is not a JSON file")

    # Create JSON file without AT_CPG_ prefix (should be ignored)
    with open(structured_dir / "other.json", "w") as f:
        json.dump({"not": "a guideline"}, f)

    # Run version tracking
    summary = update_version_tracking(
        structured_dir=str(structured_dir),
        tracker_path=str(tracker_path),
    )

    # Verify summary - no valid guidelines found
    assert summary["total_count"] == 0
    assert summary["new_count"] == 0
    assert summary["modified_count"] == 0
    assert summary["unchanged_count"] == 0


def test_update_version_tracking_malformed_json(tmp_path, caplog):
    """Version tracking should handle malformed JSON gracefully."""
    # Create structured directory
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Create tracker
    tracker_path = tmp_path / "version_tracker.json"

    # Create malformed JSON file
    with open(structured_dir / "AT_CPG_A0201-1.json", "w") as f:
        f.write("{ invalid json }")

    # Run version tracking - should not raise exception
    summary = update_version_tracking(
        structured_dir=str(structured_dir),
        tracker_path=str(tracker_path),
    )

    # Verify summary - no valid guidelines processed
    assert summary["total_count"] == 0

    # Verify error was logged
    assert any("Failed to read" in record.message for record in caplog.records)


def test_update_version_tracking_preserves_metadata(tmp_path):
    """Version tracking should preserve title and other metadata."""
    # Create structured directory
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Create tracker
    tracker_path = tmp_path / "version_tracker.json"

    # Create guideline with rich metadata
    guideline = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Cardiac Arrest - Adult",
        "categories": ["Clinical Guidelines"],
        "qualifications_required": ["Paramedic", "Intensive Care Paramedic"],
        "content_sections": [{"heading": "Assessment", "body": "ABCDE"}],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_url": "https://example.com/A0201-1",
        "source_hash": "hash1",
        "last_modified": "2026-04-20",
        "extra": {"original_category": "Cardiac Arrest"},
    }

    with open(structured_dir / "AT_CPG_A0201-1.json", "w") as f:
        json.dump(guideline, f)

    # Run version tracking
    summary = update_version_tracking(
        structured_dir=str(structured_dir),
        tracker_path=str(tracker_path),
    )

    # Verify tracker contains metadata
    with open(tracker_path, "r") as f:
        tracker = json.load(f)

    assert tracker["A0201-1"]["title"] == "Cardiac Arrest - Adult"
    assert "hash" in tracker["A0201-1"]
    assert "last_seen" in tracker["A0201-1"]
