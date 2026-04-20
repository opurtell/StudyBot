from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import chromadb


def test_seed_cmg_index_skips_when_collection_has_data(tmp_path, monkeypatch):
    from seed import _collection_has_data

    in_memory = chromadb.Client()
    collection = in_memory.get_or_create_collection("guidelines_actas")
    collection.add(ids=["existing"], documents=["test"], metadatas=[{"source_type": "cmg"}])

    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "chroma_db")

    with patch("seed.chromadb.PersistentClient", return_value=in_memory):
        assert _collection_has_data(tmp_path / "chroma_db", "guidelines_actas") is True


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
    # ACTAS chunker writes to cmg_guidelines (will be updated in Task 16)
    collection = in_memory.get_or_create_collection("cmg_guidelines")

    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "chroma_db")
    monkeypatch.setattr("seed.resolve_service_structured_dir", lambda svc_id: structured_dir)

    with patch("seed.chromadb.PersistentClient", return_value=in_memory):
        _seed_cmg_index()

    assert collection.count() > 0
    docs = collection.get()["documents"]
    assert any("cardiac" in d.lower() for d in docs)


def test_seed_personal_copies_from_bundled_when_available(tmp_path, monkeypatch):
    """When personal collection is missing from user DB but present in bundled DB, copy it."""
    import seed as seed_mod

    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "chroma_db")
    monkeypatch.setattr("seed.BUNDLED_CHROMA_DB_DIR", tmp_path / "bundled" / "chroma_db")
    monkeypatch.setattr("seed._service_id_from_registry", lambda: ("actas",))

    # Mock collection-has-data to return False (user DB is empty)
    monkeypatch.setattr("seed._collection_has_data", lambda *a, **kw: False)

    # Mock _copy_bundled_collection to succeed
    monkeypatch.setattr("seed._copy_bundled_collection", lambda *a, **kw: True)

    called = []
    monkeypatch.setattr("seed._run_notability_notes_ingest", lambda svc_id: called.append("notability"))
    monkeypatch.setattr("seed._run_personal_docs_ingest", lambda svc_id: called.append("personal_docs"))

    seed_mod._seed_personal_data()

    # Should NOT have fallen through to pipeline ingestion
    assert called == []


def test_seed_personal_falls_through_when_no_bundled(tmp_path, monkeypatch):
    """When no bundled DB exists, fall through to pipeline ingestion."""
    import seed as seed_mod

    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "chroma_db")
    monkeypatch.setattr("seed.BUNDLED_CHROMA_DB_DIR", tmp_path / "nonexistent" / "chroma_db")
    monkeypatch.setattr("seed._service_id_from_registry", lambda: ("actas",))

    # Mock collection-has-data to return False (user DB is empty)
    monkeypatch.setattr("seed._collection_has_data", lambda *a, **kw: False)

    # Mock _copy_bundled_collection to fail (no bundled data)
    monkeypatch.setattr("seed._copy_bundled_collection", lambda *a, **kw: False)

    called = []
    monkeypatch.setattr("seed._run_notability_notes_ingest", lambda svc_id: called.append("notability"))
    monkeypatch.setattr("seed._run_personal_docs_ingest", lambda svc_id: called.append("personal_docs"))

    seed_mod._seed_personal_data()

    assert "notability" in called
    assert "personal_docs" in called


def test_seed_personal_skips_when_collection_has_data(tmp_path, monkeypatch):
    """Auto-seed should skip if personal_actas already has data."""
    import seed as seed_mod

    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "chroma_db")
    monkeypatch.setattr("seed._service_id_from_registry", lambda: ("actas",))

    # Mock collection-has-data to return True
    monkeypatch.setattr("seed._collection_has_data", lambda *a, **kw: True)

    called = []
    monkeypatch.setattr("seed._run_notability_notes_ingest", lambda svc_id: called.append("notability"))

    seed_mod._seed_personal_data()

    assert called == []


def test_copy_bundled_collection_copies_data_between_persistent_dbs(tmp_path, monkeypatch):
    """_copy_bundled_collection should copy chunks from bundled to user ChromaDB."""
    from seed import _copy_bundled_collection

    # Create real PersistentClient databases in tmp directories
    bundled_dir = tmp_path / "bundled" / "data" / "chroma_db"
    user_dir = tmp_path / "user" / "data" / "chroma_db"
    bundled_dir.mkdir(parents=True)
    user_dir.mkdir(parents=True)

    # Populate bundled DB with test data
    bundled_client = chromadb.PersistentClient(path=str(bundled_dir))
    src_col = bundled_client.get_or_create_collection("test_collection")
    src_col.add(
        ids=["c1", "c2"],
        documents=["doc one", "doc two"],
        metadatas=[{"source": "a"}, {"source": "b"}],
    )

    monkeypatch.setattr("seed.BUNDLED_CHROMA_DB_DIR", bundled_dir)
    monkeypatch.setattr("seed.CHROMA_DB_DIR", user_dir)

    result = _copy_bundled_collection("test_collection")

    assert result is True
    # Verify data was copied to user DB
    user_client = chromadb.PersistentClient(path=str(user_dir))
    dst_col = user_client.get_or_create_collection("test_collection")
    assert dst_col.count() == 2
    docs = dst_col.get()["documents"]
    assert "doc one" in docs
    assert "doc two" in docs


def test_copy_bundled_collection_returns_false_when_empty(tmp_path, monkeypatch):
    """_copy_bundled_collection should return False when bundled collection is empty."""
    from seed import _copy_bundled_collection

    bundled_dir = tmp_path / "bundled" / "data" / "chroma_db"
    user_dir = tmp_path / "user" / "data" / "chroma_db"
    bundled_dir.mkdir(parents=True)
    user_dir.mkdir(parents=True)

    # Create empty collection in bundled DB
    bundled_client = chromadb.PersistentClient(path=str(bundled_dir))
    bundled_client.get_or_create_collection("empty_col")

    monkeypatch.setattr("seed.BUNDLED_CHROMA_DB_DIR", bundled_dir)
    monkeypatch.setattr("seed.CHROMA_DB_DIR", user_dir)

    result = _copy_bundled_collection("empty_col")
    assert result is False


def test_copy_bundled_collection_returns_false_when_no_bundled_dir(tmp_path, monkeypatch):
    """_copy_bundled_collection should return False when bundled dir doesn't exist."""
    from seed import _copy_bundled_collection

    monkeypatch.setattr("seed.BUNDLED_CHROMA_DB_DIR", tmp_path / "nonexistent")
    monkeypatch.setattr("seed.CHROMA_DB_DIR", tmp_path / "user" / "chroma_db")

    result = _copy_bundled_collection("any_collection")
    assert result is False
