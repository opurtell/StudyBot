"""Tests for AT pipeline chunker — service-scoped ChromaDB ingestion."""

import json

import chromadb
import pytest
from datetime import date

from src.python.pipeline.at.chunker import chunk_and_ingest


def test_chunk_and_ingest_writes_to_guidelines_at(tmp_path):
    """Test that chunk_and_ingest writes to the guidelines_at collection."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    fixture = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Medical Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "qualifications_required": [],
        "content_sections": [
            {
                "heading": "Initial Assessment",
                "body": "Confirm cardiac arrest. Begin CPR.",
                "qualifications_required": [],
            },
        ],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_hash": "abc",
        "last_modified": "2026-04-20",
        "extra": {},
    }
    (structured_dir / "AT_CPG_A0201-1.json").write_text(json.dumps(fixture))

    db_path = str(tmp_path / "chroma")
    result = chunk_and_ingest(structured_dir=str(structured_dir), db_path=db_path)

    # Verify chunks were written
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection("guidelines_at")
    assert collection.count() > 0
    assert result["total_chunks"] > 0


def test_chunks_carry_at_metadata(tmp_path):
    """Test that chunks carry the required AT metadata fields."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    fixture = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Medical Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "qualifications_required": [],
        "content_sections": [
            {
                "heading": "Initial Assessment",
                "body": "Confirm cardiac arrest. Begin CPR.",
                "qualifications_required": [],
            },
        ],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_hash": "abc",
        "last_modified": "2026-04-20",
        "extra": {},
    }
    (structured_dir / "AT_CPG_A0201-1.json").write_text(json.dumps(fixture))

    db_path = str(tmp_path / "chroma")
    chunk_and_ingest(structured_dir=str(structured_dir), db_path=db_path)

    # Verify metadata
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection("guidelines_at")
    results = collection.get()

    assert len(results["ids"]) > 0
    assert results["metadatas"][0]["source_type"] == "cmg"
    assert results["metadatas"][0]["source_file"] == "AT_CPG_A0201-1.json"
    assert results["metadatas"][0]["guideline_id"] == "AT_CPG_A0201-1"
    assert "section" in results["metadatas"][0]
    assert "chunk_type" in results["metadatas"][0]
    assert "last_modified" in results["metadatas"][0]


def test_qualifications_required_in_chunk_metadata(tmp_path):
    """Test that qualifications_required is properly stored in chunk metadata."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    fixture = {
        "service": "at",
        "guideline_id": "AT_CPG_D003",
        "title": "Adrenaline",
        "categories": ["Medication Guidelines"],
        "qualifications_required": [],
        "content_sections": [
            {
                "heading": "Administration",
                "body": "Adrenaline 1:1000 (1 mg/mL) for anaphylaxis.",
                "qualifications_required": ["ICP", "Paramedic"],
            },
        ],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_hash": "def",
        "last_modified": "2026-04-20",
        "extra": {},
    }
    (structured_dir / "AT_CPG_D003.json").write_text(json.dumps(fixture))

    db_path = str(tmp_path / "chroma")
    chunk_and_ingest(structured_dir=str(structured_dir), db_path=db_path)

    # Verify qualifications_required in metadata
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection("guidelines_at")
    results = collection.get()

    assert len(results["ids"]) > 0
    # qualifications_required should be JSON-encoded string
    qualifications_json = results["metadatas"][0]["qualifications_required"]
    qualifications = json.loads(qualifications_json)
    assert "ICP" in qualifications
    assert "Paramedic" in qualifications


def test_medications_chunked_as_dosage_type(tmp_path):
    """Test that medication sections are chunked with type 'dosage'."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    fixture = {
        "service": "at",
        "guideline_id": "AT_CPG_D003",
        "title": "Adrenaline",
        "categories": ["Medication Guidelines"],
        "qualifications_required": [],
        "content_sections": [
            {
                "heading": "Dose and Administration",
                "body": "Adrenaline 1:1000 (1 mg/mL) IM dose for anaphylaxis.",
                "qualifications_required": [],
            },
        ],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_hash": "ghi",
        "last_modified": "2026-04-20",
        "extra": {},
    }
    (structured_dir / "AT_CPG_D003.json").write_text(json.dumps(fixture))

    db_path = str(tmp_path / "chroma")
    chunk_and_ingest(structured_dir=str(structured_dir), db_path=db_path)

    # Verify at least one chunk has chunk_type 'dosage'
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection("guidelines_at")
    results = collection.get()

    assert len(results["ids"]) > 0
    chunk_types = [meta["chunk_type"] for meta in results["metadatas"]]
    assert "dosage" in chunk_types


def test_returns_stats_dict(tmp_path):
    """Test that chunk_and_ingest returns a stats dictionary."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    fixture = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Medical Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "qualifications_required": [],
        "content_sections": [
            {
                "heading": "Initial Assessment",
                "body": "Confirm cardiac arrest. Begin CPR.",
                "qualifications_required": [],
            },
        ],
        "medications": [],
        "flowcharts": [],
        "references": [],
        "source_hash": "abc",
        "last_modified": "2026-04-20",
        "extra": {},
    }
    (structured_dir / "AT_CPG_A0201-1.json").write_text(json.dumps(fixture))

    db_path = str(tmp_path / "chroma")
    result = chunk_and_ingest(structured_dir=str(structured_dir), db_path=db_path)

    assert isinstance(result, dict)
    assert "total_chunks" in result
    assert "files_processed" in result


def test_handles_empty_structured_dir(tmp_path):
    """Test that chunk_and_ingest handles empty structured directory gracefully."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    db_path = str(tmp_path / "chroma")
    result = chunk_and_ingest(structured_dir=str(structured_dir), db_path=db_path)

    assert result["total_chunks"] == 0
    assert result["files_processed"] == 0
