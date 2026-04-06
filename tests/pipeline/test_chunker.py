import yaml
from pathlib import Path

import chromadb

from pipeline.chunker import chunk_and_ingest, sanitise_id


def _write_cleaned_md(path: Path, front_matter: dict, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)
    path.write_text(f"---\n{fm}---\n{body}\n")
    return path


def _make_fm(source_file="Test/Note.note", categories=None):
    return {
        "title": "Note",
        "subject": "Test",
        "categories": categories or ["General Paramedicine"],
        "source_file": source_file,
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": [],
    }


def test_sanitise_id():
    assert sanitise_id("CSA236 Pharmacology/Week 2.note") == "CSA236_Pharmacology__Week_2.note"


def test_chunk_and_ingest_basic(tmp_path):
    """A short note produces at least one chunk in ChromaDB."""
    md_path = _write_cleaned_md(
        tmp_path / "test.md",
        _make_fm(),
        "This is a short piece of text for testing the chunker.",
    )
    db_path = tmp_path / "chroma"
    result = chunk_and_ingest(md_path, db_path)

    assert result["success"] is True
    assert result["chunk_count"] >= 1

    # Verify in ChromaDB
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection("paramedic_notes")
    assert collection.count() >= 1


def test_chunk_metadata_correct(tmp_path):
    """Chunk metadata includes all required fields."""
    md_path = _write_cleaned_md(
        tmp_path / "test.md",
        _make_fm(
            source_file="CSA236 Pharmacology/Week 2.note",
            categories=["Pharmacology", "Clinical Skills"],
        ),
        "Some clinical content about pharmacology and skills.",
    )
    db_path = tmp_path / "chroma"
    chunk_and_ingest(md_path, db_path)

    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection("paramedic_notes")
    result = collection.get(include=["metadatas"])
    meta = result["metadatas"][0]

    assert meta["source_type"] == "notability_note"
    assert meta["source_file"] == "CSA236 Pharmacology/Week 2.note"
    assert meta["categories"] == "Pharmacology,Clinical Skills"
    assert meta["chunk_index"] == 0
    assert meta["has_review_flag"] is False


def test_reingest_is_idempotent(tmp_path):
    """Ingesting the same file twice does not duplicate chunks."""
    md_path = _write_cleaned_md(
        tmp_path / "test.md",
        _make_fm(),
        "Text for idempotency test.",
    )
    db_path = tmp_path / "chroma"
    chunk_and_ingest(md_path, db_path)
    count1 = chromadb.PersistentClient(path=str(db_path)).get_collection("paramedic_notes").count()

    chunk_and_ingest(md_path, db_path)
    count2 = chromadb.PersistentClient(path=str(db_path)).get_collection("paramedic_notes").count()

    assert count1 == count2


def test_long_text_produces_multiple_chunks(tmp_path):
    """Text longer than 800 chars is split into multiple chunks."""
    long_text = "This is a paragraph about clinical practice. " * 50  # ~2300 chars
    md_path = _write_cleaned_md(tmp_path / "test.md", _make_fm(), long_text)
    db_path = tmp_path / "chroma"
    result = chunk_and_ingest(md_path, db_path)
    assert result["chunk_count"] > 1


def test_review_flag_metadata(tmp_path):
    """has_review_flag is True when review_flags are present."""
    fm = _make_fm()
    fm["review_flags"] = ["mldazolam → midazolam"]
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, "Some text.")
    db_path = tmp_path / "chroma"
    chunk_and_ingest(md_path, db_path)

    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection("paramedic_notes")
    meta = collection.get(include=["metadatas"])["metadatas"][0]
    assert meta["has_review_flag"] is True
