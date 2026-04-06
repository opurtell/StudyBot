"""End-to-end integration test: extract → (simulate clean) → ingest."""

import yaml
import chromadb
from pathlib import Path

from pipeline.extractor import extract_all
from pipeline.structurer import validate_and_normalise
from pipeline.chunker import chunk_and_ingest


def _simulate_cleaning(raw_dir: Path, cleaned_dir: Path):
    """Simulate Claude Code cleaning by copying raw files with updated front matter."""
    for raw_file in raw_dir.rglob("*.md"):
        content = raw_file.read_text()
        parts = content.split("---\n", 2)
        meta = yaml.safe_load(parts[1])

        # Simulate: promote default_category to categories list, add review_flags
        cleaned_meta = {
            "title": meta["title"],
            "subject": meta["subject"],
            "categories": [meta.get("default_category", "General Paramedicine")],
            "source_file": meta["source_file"],
            "last_modified": meta["last_modified"],
            "review_flags": [],
        }

        rel_path = raw_file.relative_to(raw_dir)
        out_path = cleaned_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fm_str = yaml.dump(cleaned_meta, default_flow_style=False, allow_unicode=True)
        out_path.write_text(f"---\n{fm_str}---\n{parts[2]}")


def test_full_pipeline(build_note, tmp_output):
    """Extract → simulate clean → validate → ingest → query ChromaDB."""
    # Create test notes
    build_note(
        title="Adrenaline",
        subject="CSA236 Pharmacology",
        pages={"1": "Adrenaline 1mg IV for cardiac arrest", "2": "Repeat every 3-5 minutes"},
    )
    build_note(
        title="Triage",
        subject="General Paramedicine",
        pages={"1": "Triage categories: immediate, urgent, delayed, dead"},
    )

    # Extract
    source_dir = tmp_output["base"]
    raw_dir = tmp_output["raw"]
    results = extract_all(source_dir, raw_dir)
    assert sum(1 for r in results if r["success"]) == 2

    # Simulate cleaning
    cleaned_dir = tmp_output["cleaned"]
    _simulate_cleaning(raw_dir, cleaned_dir)

    # Validate and ingest
    db_path = tmp_output["base"] / "chroma"
    for md_path in cleaned_dir.rglob("*.md"):
        val = validate_and_normalise(md_path)
        assert val["valid"], f"Validation failed: {val.get('error')}"
        result = chunk_and_ingest(md_path, db_path)
        assert result["success"]

    # Query ChromaDB
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection("paramedic_notes")
    assert collection.count() >= 2

    # Search for adrenaline content
    results = collection.query(query_texts=["adrenaline cardiac arrest"], n_results=1)
    assert len(results["documents"][0]) == 1
    assert "Adrenaline" in results["documents"][0][0] or "adrenaline" in results["documents"][0][0].lower()
