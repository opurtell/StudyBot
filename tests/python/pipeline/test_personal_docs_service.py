"""
Tests for service-aware collection routing in the personal_docs chunker.

Covers:
  1. Service routing: chunks with service=actas land in personal_actas
  2. Different service routing: chunks with service=at land in personal_at
  3. Fallback: chunks with no service field land in paramedic_notes (legacy)
  4. Explicit override: collection_name kwarg takes precedence over front-matter
  5. Metadata carries correct service and scope values
"""

from pathlib import Path

import chromadb
import pytest
import yaml

from pipeline.personal_docs.chunker import (
    DEFAULT_COLLECTION_NAME,
    chunk_and_ingest,
    chunk_and_ingest_directory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_structured_md(
    output_dir: Path,
    subdir: str,
    filename: str,
    front_matter: dict,
    body: str,
) -> Path:
    """Write a structured markdown file with YAML front matter."""
    dir_path = output_dir / subdir
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    yaml_block = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)
    file_path.write_text(f"---\n{yaml_block}---\n{body}", encoding="utf-8")
    return file_path


def _base_front_matter(**overrides) -> dict:
    """Return a minimal valid front-matter dict, with optional overrides."""
    defaults = {
        "title": "Test Document",
        "source_type": "ref_doc",
        "source_file": "REFdocs/test-doc.md",
        "categories": ["Clinical Guidelines"],
        "last_modified": "2026-01-01T00:00:00+00:00",
    }
    defaults.update(overrides)
    return defaults


def _get_collection_names(db_path: Path) -> set[str]:
    """List all collection names in a persistent ChromaDB."""
    client = chromadb.PersistentClient(path=str(db_path))
    return {c.name for c in client.list_collections()}


def _get_chunks_with_metadata(db_path: Path, collection_name: str) -> list[dict]:
    """Get all chunks from a collection, returning their metadatas."""
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_or_create_collection(name=collection_name)
    results = collection.get(include=["metadatas", "documents"])
    return list(zip(results["ids"], results["metadatas"], results["documents"]))


# ---------------------------------------------------------------------------
# 1. Service routing: service=actas -> personal_actas
# ---------------------------------------------------------------------------
class TestServiceRouting:
    def test_actas_service_creates_personal_actas_collection(self, tmp_path: Path):
        structured_dir = tmp_path / "structured"
        db_path = tmp_path / "chroma_db"
        db_path.mkdir()

        md_path = _write_structured_md(
            structured_dir,
            "REFdocs",
            "test-actas.md",
            _base_front_matter(service="actas", scope="service-specific"),
            "# ACTAS Guideline\n\nAdrenaline IM 0.5mg for anaphylaxis.\n",
        )

        result = chunk_and_ingest(md_path, db_path)

        assert result["success"] is True
        assert result["chunk_count"] > 0
        names = _get_collection_names(db_path)
        assert "personal_actas" in names

    def test_actas_chunks_have_correct_metadata(self, tmp_path: Path):
        structured_dir = tmp_path / "structured"
        db_path = tmp_path / "chroma_db"
        db_path.mkdir()

        md_path = _write_structured_md(
            structured_dir,
            "REFdocs",
            "test-actas.md",
            _base_front_matter(service="actas", scope="service-specific"),
            "# ACTAS Guideline\n\nAdrenaline IM 0.5mg for anaphylaxis.\n",
        )

        chunk_and_ingest(md_path, db_path)
        chunks = _get_chunks_with_metadata(db_path, "personal_actas")

        assert len(chunks) > 0
        for _chunk_id, meta, _doc in chunks:
            assert meta["service"] == "actas"
            assert meta["scope"] == "service-specific"


# ---------------------------------------------------------------------------
# 2. Different service routing: service=at -> personal_at
# ---------------------------------------------------------------------------
class TestDifferentServiceRouting:
    def test_at_service_creates_personal_at_collection(self, tmp_path: Path):
        structured_dir = tmp_path / "structured"
        db_path = tmp_path / "chroma_db"
        db_path.mkdir()

        md_path = _write_structured_md(
            structured_dir,
            "REFdocs",
            "test-at.md",
            _base_front_matter(
                service="at",
                scope="service-specific",
                source_file="REFdocs/test-at.md",
            ),
            "# AT Guideline\n\nStandard operating procedure for patient transport.\n",
        )

        result = chunk_and_ingest(md_path, db_path)

        assert result["success"] is True
        assert result["chunk_count"] > 0
        names = _get_collection_names(db_path)
        assert "personal_at" in names

    def test_at_chunks_have_correct_metadata(self, tmp_path: Path):
        structured_dir = tmp_path / "structured"
        db_path = tmp_path / "chroma_db"
        db_path.mkdir()

        md_path = _write_structured_md(
            structured_dir,
            "REFdocs",
            "test-at.md",
            _base_front_matter(
                service="at",
                scope="service-specific",
                source_file="REFdocs/test-at.md",
            ),
            "# AT Guideline\n\nStandard operating procedure for patient transport.\n",
        )

        chunk_and_ingest(md_path, db_path)
        chunks = _get_chunks_with_metadata(db_path, "personal_at")

        assert len(chunks) > 0
        for _chunk_id, meta, _doc in chunks:
            assert meta["service"] == "at"
            assert meta["scope"] == "service-specific"


# ---------------------------------------------------------------------------
# 3. Fallback: no service field -> paramedic_notes (legacy)
# ---------------------------------------------------------------------------
class TestFallback:
    def test_no_service_uses_paramedic_notes(self, tmp_path: Path):
        structured_dir = tmp_path / "structured"
        db_path = tmp_path / "chroma_db"
        db_path.mkdir()

        md_path = _write_structured_md(
            structured_dir,
            "REFdocs",
            "test-legacy.md",
            _base_front_matter(),
            "# Legacy Doc\n\nSome clinical content without a service tag.\n",
        )

        result = chunk_and_ingest(md_path, db_path)

        assert result["success"] is True
        assert result["chunk_count"] > 0
        names = _get_collection_names(db_path)
        assert "paramedic_notes" in names
        # No service-scoped collection should have been created
        assert "personal_actas" not in names
        assert "personal_at" not in names

    def test_no_service_metadata_is_empty_string(self, tmp_path: Path):
        structured_dir = tmp_path / "structured"
        db_path = tmp_path / "chroma_db"
        db_path.mkdir()

        md_path = _write_structured_md(
            structured_dir,
            "REFdocs",
            "test-legacy.md",
            _base_front_matter(),
            "# Legacy Doc\n\nSome clinical content without a service tag.\n",
        )

        chunk_and_ingest(md_path, db_path)
        chunks = _get_chunks_with_metadata(db_path, DEFAULT_COLLECTION_NAME)

        assert len(chunks) > 0
        for _chunk_id, meta, _doc in chunks:
            assert meta["service"] == ""
            assert meta["scope"] == ""


# ---------------------------------------------------------------------------
# 4. Explicit collection_name override takes precedence
# ---------------------------------------------------------------------------
class TestExplicitOverride:
    def test_explicit_collection_name_overrides_service(self, tmp_path: Path):
        structured_dir = tmp_path / "structured"
        db_path = tmp_path / "chroma_db"
        db_path.mkdir()

        md_path = _write_structured_md(
            structured_dir,
            "REFdocs",
            "test-override.md",
            _base_front_matter(service="actas", scope="service-specific"),
            "# Override Test\n\nContent that should go to custom collection.\n",
        )

        result = chunk_and_ingest(md_path, db_path, collection_name="custom_collection")

        assert result["success"] is True
        assert result["chunk_count"] > 0
        names = _get_collection_names(db_path)
        assert "custom_collection" in names
        # personal_actas should NOT exist because the explicit override was used
        assert "personal_actas" not in names


# ---------------------------------------------------------------------------
# 5. Directory ingestion routes per-file based on front-matter
# ---------------------------------------------------------------------------
class TestDirectoryIngestion:
    def test_mixed_services_route_to_separate_collections(self, tmp_path: Path):
        structured_dir = tmp_path / "structured"
        db_path = tmp_path / "chroma_db"
        db_path.mkdir()

        # File 1: service=actas
        _write_structured_md(
            structured_dir,
            "REFdocs",
            "doc-actas.md",
            _base_front_matter(
                service="actas",
                scope="service-specific",
                source_file="REFdocs/doc-actas.md",
            ),
            "# ACTAS Doc\n\nAdrenaline protocol content.\n",
        )

        # File 2: no service (legacy)
        _write_structured_md(
            structured_dir,
            "REFdocs",
            "doc-legacy.md",
            _base_front_matter(source_file="REFdocs/doc-legacy.md"),
            "# Legacy Doc\n\nGeneral clinical content.\n",
        )

        result = chunk_and_ingest_directory(structured_dir, db_path)

        assert result["processed"] == 2
        assert result["errors"] == 0
        assert result["total_chunks"] > 0

        names = _get_collection_names(db_path)
        assert "personal_actas" in names
        assert "paramedic_notes" in names

    def test_different_services_in_different_subdirs(self, tmp_path: Path):
        structured_dir = tmp_path / "structured"
        db_path = tmp_path / "chroma_db"
        db_path.mkdir()

        # REFdocs file with service=actas
        _write_structured_md(
            structured_dir,
            "REFdocs",
            "ref-actas.md",
            _base_front_matter(
                service="actas",
                scope="service-specific",
                source_file="REFdocs/ref-actas.md",
                source_type="ref_doc",
            ),
            "# ACTAS Reference\n\nReference clinical content.\n",
        )

        # CPDdocs file with service=at
        _write_structured_md(
            structured_dir,
            "CPDdocs",
            "cpd-at.md",
            _base_front_matter(
                service="at",
                scope="service-specific",
                source_file="CPDdocs/cpd-at.md",
                source_type="cpd_doc",
            ),
            "# AT CPD\n\nContinuing professional development content.\n",
        )

        result = chunk_and_ingest_directory(structured_dir, db_path)

        assert result["processed"] == 2
        assert result["errors"] == 0

        names = _get_collection_names(db_path)
        assert "personal_actas" in names
        assert "personal_at" in names

        # Verify metadata on each collection
        actas_chunks = _get_chunks_with_metadata(db_path, "personal_actas")
        for _cid, meta, _doc in actas_chunks:
            assert meta["service"] == "actas"
            assert meta["source_type"] == "ref_doc"

        at_chunks = _get_chunks_with_metadata(db_path, "personal_at")
        for _cid, meta, _doc in at_chunks:
            assert meta["service"] == "at"
            assert meta["source_type"] == "cpd_doc"
