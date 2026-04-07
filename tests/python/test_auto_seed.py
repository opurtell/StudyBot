from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import chromadb


def test_seed_cmg_index_skips_when_collection_has_data(tmp_path, monkeypatch):
    from seed import _seed_cmg_index

    in_memory = chromadb.Client()
    collection = in_memory.get_or_create_collection("cmg_guidelines")
    collection.add(ids=["existing"], documents=["test"], metadatas=[{"source_type": "cmg"}])

    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "chroma_db")
    monkeypatch.setattr("seed.CMG_STRUCTURED_DIR", tmp_path / "structured")
    monkeypatch.setattr("seed.resolve_cmg_structured_dir", lambda: tmp_path / "structured")

    with patch("seed.chromadb.PersistentClient", return_value=in_memory):
        _seed_cmg_index()

    assert collection.count() == 1


def test_seed_cmg_index_ingests_from_bundled_dir(tmp_path, monkeypatch):
    from seed import _seed_cmg_index

    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    sample = {
        "id": "test_cmg",
        "cmg_number": "CMG 1",
        "title": "Test",
        "section": "Cardiac",
        "content_markdown": "# Test CMG\n\nSome content about cardiac care.",
        "is_icp_only": False,
        "checksum": "abc123",
        "extraction_metadata": {"timestamp": "2026-01-01T00:00:00+00:00", "source_type": "cmg"},
    }
    with open(structured_dir / "test_cmg.json", "w") as f:
        json.dump(sample, f)

    in_memory = chromadb.Client()
    collection = in_memory.get_or_create_collection("cmg_guidelines")

    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "chroma_db")
    monkeypatch.setattr("seed.resolve_cmg_structured_dir", lambda: structured_dir)

    with patch("seed.chromadb.PersistentClient", return_value=in_memory):
        _seed_cmg_index()

    assert collection.count() > 0
    docs = collection.get()["documents"]
    assert any("cardiac" in d.lower() for d in docs)
