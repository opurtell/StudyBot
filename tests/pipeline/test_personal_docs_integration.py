"""Integration test: full personal docs pipeline from source to ChromaDB query."""

import chromadb
import yaml
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline.personal_docs.chunker import chunk_and_ingest, chunk_and_ingest_directory
from pipeline.personal_docs.structurer import structure_directory, structure_file


class TestPersonalDocsIntegration:
    def test_full_pipeline_structure_then_ingest(self, tmp_path):
        source = tmp_path / "docs"
        (source / "REFdocs").mkdir(parents=True)
        (source / "CPDdocs").mkdir(parents=True)

        (source / "REFdocs" / "Reference Info ACTAS CMGs.md").write_text(
            "# Reference Tables\n\n"
            "## Paediatric Doses\n\n"
            "Adrenaline cardiac arrest dose for children is 0.01 mg/kg.\n\n"
            "Defibrillation energy for children is 4 J/kg.\n\n"
            "## Adult Doses\n\n"
            "Adrenaline cardiac arrest dose for adults is 1 mg.\n\n"
            "Defibrillation energy for adults is 200 J.\n"
        )

        (source / "CPDdocs" / "ECGs.md").write_text(
            "# Cardiac Rhythms\n\n"
            "## Sinus Rhythm\n\n"
            "Normal sinus rhythm has a rate of 60-100 bpm with consistent P waves.\n\n"
            "## Atrial Fibrillation\n\n"
            "AF is characterised by irregular R-R intervals and absence of distinct P waves.\n"
            "Treatment depends on haemodynamic stability and duration.\n\n"
            "### Rate Control\n\n"
            "Rate control with beta blockers or calcium channel blockers.\n\n"
            "### Rhythm Control\n\n"
            "Rhythm control with cardioversion or antiarrhythmics.\n"
        )

        structured_dir = tmp_path / "structured"
        structured_dir.mkdir()
        db_path = tmp_path / "chroma_db"

        struct_result = structure_directory(source, structured_dir)
        assert struct_result["processed"] == 2

        assert (structured_dir / "REFdocs" / "Reference Info ACTAS CMGs.md").exists()
        assert (structured_dir / "CPDdocs" / "ECGs.md").exists()

        ref_content = (
            structured_dir / "REFdocs" / "Reference Info ACTAS CMGs.md"
        ).read_text()
        assert "source_type: ref_doc" in ref_content
        assert "Medication Guidelines" in ref_content

        cpd_content = (structured_dir / "CPDdocs" / "ECGs.md").read_text()
        assert "source_type: cpd_doc" in cpd_content
        assert "ECGs" in cpd_content

        ingest_result = chunk_and_ingest_directory(structured_dir, db_path)
        assert ingest_result["processed"] == 2
        assert ingest_result["total_chunks"] > 0

        client = chromadb.PersistentClient(path=str(db_path))
        collection = client.get_collection("paramedic_notes")

        ref_results = collection.get(where={"source_type": "ref_doc"})
        assert len(ref_results["ids"]) > 0

        cpd_results = collection.get(where={"source_type": "cpd_doc"})
        assert len(cpd_results["ids"]) > 0

        all_ref_text = " ".join(ref_results["documents"])
        assert "Adrenaline" in all_ref_text

        all_cpd_text = " ".join(cpd_results["documents"])
        assert "Sinus Rhythm" in all_cpd_text or "AF" in all_cpd_text

        query_results = collection.query(
            query_texts=["paediatric adrenaline dose"],
            n_results=3,
            where={"source_type": "ref_doc"},
        )
        assert len(query_results["documents"][0]) > 0
        assert any("Adrenaline" in doc for doc in query_results["documents"][0])

    def test_header_context_preserved_in_chunks(self, tmp_path):
        src = tmp_path / "source" / "CPDdocs"
        src.mkdir(parents=True)
        out = tmp_path / "structured"
        out.mkdir()
        db = tmp_path / "db"

        md_file = src / "Test.md"
        md_file.write_text(
            "# Cardiac Conditions\n\n## AF Management\n\nRate control and rhythm control strategies.\n\n## VT Management\n\nSynchronised cardioversion for unstable VT.\n"
        )

        structure_file(md_file, out, "CPDdocs")
        output_file = out / "CPDdocs" / "Test.md"

        chunk_and_ingest(output_file, db)

        client = chromadb.PersistentClient(path=str(db))
        collection = client.get_collection("paramedic_notes")
        results = collection.get(where={"source_file": "CPDdocs/Test.md"})

        header_contexts = [m["header_context"] for m in results["metadatas"]]
        assert any("AF" in ctx for ctx in header_contexts)
        assert any("VT" in ctx for ctx in header_contexts)
