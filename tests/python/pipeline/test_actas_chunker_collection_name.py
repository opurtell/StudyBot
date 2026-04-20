"""Test that the ACTAS chunker accepts an optional collection_name."""

import json
import os
import tempfile

import chromadb

from pipeline.actas.chunker import chunk_and_ingest


def _write_sample_cmg(structured_dir: str) -> str:
    """Write a minimal valid CMG JSON file and return its path."""
    data = {
        "id": "test_cmg_1",
        "cmg_number": "1.0",
        "title": "Test CMG",
        "section": "Cardiac",
        "is_icp_only": False,
        "content_markdown": "# Test Section\nAdrenaline dose for cardiac arrest is 1mg.",
        "dose_lookup": {},
        "extraction_metadata": {"timestamp": "2025-01-01"},
        "checksum": "abc123",
    }
    path = os.path.join(structured_dir, "test_cmg_1.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def test_default_collection_name():
    """Without collection_name, chunks go to 'guidelines_actas'."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "chroma")
        structured_dir = os.path.join(tmp, "structured")
        os.makedirs(structured_dir)
        _write_sample_cmg(structured_dir)

        chunk_and_ingest(structured_dir=structured_dir, db_path=db_path)

        client = chromadb.PersistentClient(path=db_path)
        col = client.get_collection("guidelines_actas")
        assert col.count() > 0


def test_custom_collection_name():
    """With collection_name, chunks go to the named collection."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "chroma")
        structured_dir = os.path.join(tmp, "structured")
        os.makedirs(structured_dir)
        _write_sample_cmg(structured_dir)

        chunk_and_ingest(
            structured_dir=structured_dir,
            db_path=db_path,
            collection_name="guidelines_at",
        )

        client = chromadb.PersistentClient(path=db_path)
        col = client.get_collection("guidelines_at")
        assert col.count() > 0

        # Default collection should NOT exist
        names = [c.name for c in client.list_collections()]
        assert "guidelines_actas" not in names
