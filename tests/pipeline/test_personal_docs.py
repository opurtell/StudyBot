"""Tests for Phase 3: Personal docs pipeline."""

from datetime import datetime, timezone
from pathlib import Path

import chromadb
import pytest
import yaml
from click.testing import CliRunner

from pipeline.clinical_dictionary import (
    get_categories_for_file,
    get_source_type_for_dir,
)
from pipeline.personal_docs.chunker import chunk_and_ingest, chunk_and_ingest_directory
from pipeline.personal_docs.run import cli
from pipeline.personal_docs.structurer import structure_directory, structure_file


class TestPersonalDocCategoryMapping:
    def test_ref_doc_cmg_reference_maps_to_categories(self):
        result = get_categories_for_file("REFdocs/Reference Info ACTAS CMGs.md")
        assert "Medication Guidelines" in result
        assert "Clinical Guidelines" in result

    def test_ref_doc_policies_maps_to_operational(self):
        result = get_categories_for_file("REFdocs/ACTAS Policies and procedures.md")
        assert result == ["Operational Guidelines"]

    def test_cpdoc_ecgs_maps_to_ecg_category(self):
        result = get_categories_for_file("CPDdocs/ECGs.md")
        assert "ECGs" in result

    def test_unknown_file_returns_default(self):
        result = get_categories_for_file("CPDdocs/unknown_file.md")
        assert result == ["General Paramedicine"]


class TestDirectorySourceType:
    def test_refdocs_dir_maps_to_ref_doc(self):
        assert get_source_type_for_dir("REFdocs") == "ref_doc"

    def test_cpddocs_dir_maps_to_cpd_doc(self):
        assert get_source_type_for_dir("CPDdocs") == "cpd_doc"

    def test_unknown_dir_raises(self):
        with pytest.raises(ValueError, match="Unknown source directory"):
            get_source_type_for_dir("unknown")


class TestPersonalDocsStructurer:
    def test_structure_file_adds_yaml_front_matter(self, tmp_path):
        src = tmp_path / "source" / "CPDdocs"
        src.mkdir(parents=True)
        out = tmp_path / "structured"
        out.mkdir()

        md_file = src / "Test File.md"
        md_file.write_text("# Test Title\n\nSome body text.\n")

        result = structure_file(md_file, out, "CPDdocs")

        output_file = out / "CPDdocs" / "Test File.md"
        assert output_file.exists()

        content = output_file.read_text()
        assert content.startswith("---\n")
        assert "title: Test Title" in content
        assert "source_type: cpd_doc" in content
        assert "Some body text." in content

    def test_structure_file_uses_filename_when_no_header(self, tmp_path):
        src = tmp_path / "source" / "REFdocs"
        src.mkdir(parents=True)
        out = tmp_path / "structured"
        out.mkdir()

        md_file = src / "Policies.md"
        md_file.write_text("Just some text without a header.\n")

        result = structure_file(md_file, out, "REFdocs")

        assert result["title"] == "Policies"

    def test_structure_file_assigns_categories(self, tmp_path):
        src = tmp_path / "source" / "CPDdocs"
        src.mkdir(parents=True)
        out = tmp_path / "structured"
        out.mkdir()

        md_file = src / "ECGs.md"
        md_file.write_text("# ECGs\n\nSome content.\n")

        result = structure_file(md_file, out, "CPDdocs")

        assert "ECGs" in result["categories"]

    def test_structure_file_sets_last_modified(self, tmp_path):
        src = tmp_path / "source" / "CPDdocs"
        src.mkdir(parents=True)
        out = tmp_path / "structured"
        out.mkdir()

        md_file = src / "Test.md"
        md_file.write_text("# Test\nBody\n")

        result = structure_file(md_file, out, "CPDdocs")

        assert "last_modified" in result
        datetime.fromisoformat(result["last_modified"])

    def test_structure_directory_processes_all_files(self, tmp_path):
        src = tmp_path / "source"
        (src / "REFdocs").mkdir(parents=True)
        (src / "CPDdocs").mkdir(parents=True)
        out = tmp_path / "structured"
        out.mkdir()

        (src / "REFdocs" / "Ref.md").write_text("# Ref\nBody\n")
        (src / "CPDdocs" / "Cpd.md").write_text("# Cpd\nBody\n")

        result = structure_directory(src, out)

        assert result["processed"] == 2
        assert (out / "REFdocs" / "Ref.md").exists()
        assert (out / "CPDdocs" / "Cpd.md").exists()


class TestPersonalDocsChunker:
    def _make_structured_md(self, tmp_path, source_type="cpd_doc", categories=None):
        out = tmp_path / "structured" / "CPDdocs"
        out.mkdir(parents=True)
        db = tmp_path / "chroma_db"

        front = {
            "title": "Test Document",
            "source_type": source_type,
            "source_file": "CPDdocs/Test Document.md",
            "categories": categories or ["Clinical Guidelines"],
            "last_modified": datetime.now(timezone.utc).isoformat(),
        }

        yaml_block = yaml.dump(front, default_flow_style=False)
        body = "# Section A\n\nParagraph one about clinical guidelines.\n\n## Subsection\n\nParagraph two with more detail about procedures.\n\n# Section B\n\nParagraph three about medications."
        content = f"---\n{yaml_block}---\n{body}"

        md_file = out / "Test Document.md"
        md_file.write_text(content)
        return md_file, db

    def test_chunk_and_ingest_creates_chunks(self, tmp_path):
        md_file, db = self._make_structured_md(tmp_path)

        result = chunk_and_ingest(md_file, db)

        assert result["success"] is True
        assert result["chunk_count"] > 0
        assert result["source_file"] == "CPDdocs/Test Document.md"

    def test_chunks_have_correct_metadata(self, tmp_path):
        md_file, db = self._make_structured_md(tmp_path)

        chunk_and_ingest(md_file, db)

        client = chromadb.PersistentClient(path=str(db))
        collection = client.get_collection("paramedic_notes")
        results = collection.get(where={"source_file": "CPDdocs/Test Document.md"})

        assert len(results["ids"]) > 0
        for meta in results["metadatas"]:
            assert meta["source_type"] == "cpd_doc"
            assert "Clinical Guidelines" in meta["categories"]
            assert "chunk_index" in meta

    def test_chunks_preserve_header_context(self, tmp_path):
        md_file, db = self._make_structured_md(tmp_path)

        chunk_and_ingest(md_file, db)

        client = chromadb.PersistentClient(path=str(db))
        collection = client.get_collection("paramedic_notes")
        results = collection.get(where={"source_file": "CPDdocs/Test Document.md"})

        docs = results["documents"]
        all_text = " ".join(docs)
        assert "Section A" in all_text
        assert "Section B" in all_text

    def test_ingest_is_idempotent(self, tmp_path):
        md_file, db = self._make_structured_md(tmp_path)

        r1 = chunk_and_ingest(md_file, db)
        r2 = chunk_and_ingest(md_file, db)

        assert r1["chunk_count"] == r2["chunk_count"]

        client = chromadb.PersistentClient(path=str(db))
        collection = client.get_collection("paramedic_notes")
        results = collection.get(where={"source_file": "CPDdocs/Test Document.md"})
        assert len(results["ids"]) == r1["chunk_count"]

    def test_ref_doc_source_type_preserved(self, tmp_path):
        out = tmp_path / "structured" / "REFdocs"
        out.mkdir(parents=True)
        db = tmp_path / "chroma_db"

        front = {
            "title": "Policies",
            "source_type": "ref_doc",
            "source_file": "REFdocs/Policies.md",
            "categories": ["Operational Guidelines"],
            "last_modified": "2026-01-01T00:00:00+00:00",
        }

        yaml_block = yaml.dump(front, default_flow_style=False)
        content = f"---\n{yaml_block}---\n# Policies\n\nContent about policies."
        md_file = out / "Policies.md"
        md_file.write_text(content)

        chunk_and_ingest(md_file, db)

        client = chromadb.PersistentClient(path=str(db))
        collection = client.get_collection("paramedic_notes")
        results = collection.get(where={"source_file": "REFdocs/Policies.md"})

        for meta in results["metadatas"]:
            assert meta["source_type"] == "ref_doc"

    def test_ingest_directory(self, tmp_path):
        out = tmp_path / "structured"
        (out / "REFdocs").mkdir(parents=True)
        (out / "CPDdocs").mkdir(parents=True)
        db = tmp_path / "chroma_db"

        for dir_name, st in [("REFdocs", "ref_doc"), ("CPDdocs", "cpd_doc")]:
            front = {
                "title": f"Doc in {dir_name}",
                "source_type": st,
                "source_file": f"{dir_name}/Doc.md",
                "categories": ["Clinical Guidelines"],
                "last_modified": datetime.now(timezone.utc).isoformat(),
            }
            yaml_block = yaml.dump(front, default_flow_style=False)
            content = f"---\n{yaml_block}---\n# Title\n\nBody text here."
            (out / dir_name / "Doc.md").write_text(content)

        result = chunk_and_ingest_directory(out, db)

        assert result["processed"] == 2
        assert result["total_chunks"] > 0


class TestPersonalDocsCLI:
    def test_status_reports_empty(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--db-path", str(tmp_path / "db")])

        assert result.exit_code == 0
        assert "Personal Docs Pipeline" in result.output

    def test_structure_command(self, tmp_path):
        src = tmp_path / "source"
        (src / "CPDdocs").mkdir(parents=True)
        (src / "CPDdocs" / "Test.md").write_text("# Test\nBody\n")
        out = tmp_path / "structured"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "structure",
                "--source-root",
                str(src),
                "--output-dir",
                str(out),
            ],
        )

        assert result.exit_code == 0
        assert (out / "CPDdocs" / "Test.md").exists()

    def test_ingest_command(self, tmp_path):
        out = tmp_path / "structured"
        (out / "CPDdocs").mkdir(parents=True)
        db = tmp_path / "db"

        front = {
            "title": "CLI Test",
            "source_type": "cpd_doc",
            "source_file": "CPDdocs/CLI Test.md",
            "categories": ["Clinical Guidelines"],
            "last_modified": datetime.now(timezone.utc).isoformat(),
        }
        yaml_block = yaml.dump(front, default_flow_style=False)
        content = f"---\n{yaml_block}---\n# CLI Test\n\nSome content for CLI test."
        (out / "CPDdocs" / "CLI Test.md").write_text(content)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "ingest",
                "--structured-dir",
                str(out),
                "--db-path",
                str(db),
            ],
        )

        assert result.exit_code == 0

    def test_dry_run_does_not_write(self, tmp_path):
        src = tmp_path / "source"
        (src / "CPDdocs").mkdir(parents=True)
        (src / "CPDdocs" / "Test.md").write_text("# Test\nBody\n")
        out = tmp_path / "structured"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "structure",
                "--source-root",
                str(src),
                "--output-dir",
                str(out),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert not (out / "CPDdocs" / "Test.md").exists()
