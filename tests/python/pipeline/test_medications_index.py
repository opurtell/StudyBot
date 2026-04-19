"""
Tests for the medication denormalisation index builder.

Covers:
  - Building index from fixture dir produces expected medication files
  - Each entry has service, guideline_id, qualifications_required
  - A medication appearing in multiple guidelines has all entries aggregated
  - Output dir is created if missing
  - Empty dose_lookup produces no medication file
"""

import json
from pathlib import Path

import pytest

from src.python.pipeline.actas.medications_index import build_medication_index

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "services" / "actas"


@pytest.fixture()
def fixture_structured_dir() -> Path:
    """Points at the shared ACTAS fixture directory."""
    return FIXTURES_DIR


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    """Temporary output directory for medication index files."""
    return tmp_path / "medications"


# ---------------------------------------------------------------------------
# 1. Building index from fixture dir produces expected medication files
# ---------------------------------------------------------------------------
class TestBuildIndexFromFixtures:
    def test_returns_medication_counts(self, fixture_structured_dir: Path, output_dir: Path):
        result = build_medication_index(fixture_structured_dir, output_dir)
        assert isinstance(result, dict)
        assert all(isinstance(v, int) and v > 0 for v in result.values())

    def test_expected_medications_created(self, fixture_structured_dir: Path, output_dir: Path):
        build_medication_index(fixture_structured_dir, output_dir)
        # Fixture AP doc has Adrenaline + Amiodarone; ICP doc has Suxamethonium + Morphine
        expected_files = {
            "adrenaline.json",
            "amiodarone.json",
            "suxamethonium.json",
            "morphine.json",
        }
        actual_files = {f.name for f in output_dir.iterdir() if f.suffix == ".json"}
        assert actual_files == expected_files

    def test_file_naming_sanitised(self, fixture_structured_dir: Path, output_dir: Path):
        build_medication_index(fixture_structured_dir, output_dir)
        # All filenames should be lowercase with hyphens, no spaces or special chars
        for f in output_dir.iterdir():
            assert f.name == f.name.lower()
            assert " " not in f.name

    def test_result_counts_match_entries(self, fixture_structured_dir: Path, output_dir: Path):
        result = build_medication_index(fixture_structured_dir, output_dir)
        for med_name, count in result.items():
            safe_name = med_name.lower().replace(" ", "-")
            # strip any non-alphanumeric/hyphen chars
            safe_name = "".join(c for c in safe_name if c.isalnum() or c == "-")
            med_file = output_dir / f"{safe_name}.json"
            data = json.loads(med_file.read_text())
            assert data["total_entries"] == count
            assert len(data["dose_entries"]) == count


# ---------------------------------------------------------------------------
# 2. Each entry has required fields
# ---------------------------------------------------------------------------
class TestEntryFields:
    def test_each_entry_has_service(self, fixture_structured_dir: Path, output_dir: Path):
        build_medication_index(fixture_structured_dir, output_dir)
        for f in output_dir.iterdir():
            data = json.loads(f.read_text())
            for entry in data["dose_entries"]:
                assert "service" in entry
                assert entry["service"] == "actas"

    def test_each_entry_has_guideline_id(self, fixture_structured_dir: Path, output_dir: Path):
        build_medication_index(fixture_structured_dir, output_dir)
        for f in output_dir.iterdir():
            data = json.loads(f.read_text())
            for entry in data["dose_entries"]:
                assert "guideline_id" in entry
                assert isinstance(entry["guideline_id"], str)
                assert len(entry["guideline_id"]) > 0

    def test_each_entry_has_qualifications_required(self, fixture_structured_dir: Path, output_dir: Path):
        build_medication_index(fixture_structured_dir, output_dir)
        for f in output_dir.iterdir():
            data = json.loads(f.read_text())
            for entry in data["dose_entries"]:
                assert "qualifications_required" in entry
                assert isinstance(entry["qualifications_required"], list)

    def test_each_entry_has_source_file(self, fixture_structured_dir: Path, output_dir: Path):
        build_medication_index(fixture_structured_dir, output_dir)
        for f in output_dir.iterdir():
            data = json.loads(f.read_text())
            for entry in data["dose_entries"]:
                assert "source_file" in entry
                assert entry["source_file"].endswith(".json")

    def test_top_level_fields(self, fixture_structured_dir: Path, output_dir: Path):
        build_medication_index(fixture_structured_dir, output_dir)
        for f in output_dir.iterdir():
            data = json.loads(f.read_text())
            assert "medication" in data
            assert "service" in data
            assert data["service"] == "actas"
            assert "dose_entries" in data
            assert "total_entries" in data
            assert "sources" in data


# ---------------------------------------------------------------------------
# 3. Cross-guideline aggregation (needs synthetic multi-guideline fixture)
# ---------------------------------------------------------------------------
class TestCrossGuidelineAggregation:
    def _make_dir_with_shared_medication(self, tmp_path: Path) -> Path:
        """Create a structured dir with two docs that both reference Adrenaline."""
        structured = tmp_path / "structured"
        structured.mkdir()
        # Doc 1
        doc1 = {
            "id": "test-cmg-1",
            "cmg_number": "1",
            "title": "General Care",
            "is_icp_only": False,
            "dose_lookup": {
                "Adrenaline": [
                    {
                        "text": "Adrenaline IM 0.5mg",
                        "dose_values": [{"amount": "0.5", "unit": "mg"}],
                        "qualifications_required": ["AP"],
                    }
                ]
            },
            "service": "actas",
            "guideline_id": "CMG_1",
            "qualifications_required": ["AP"],
        }
        # Doc 2
        doc2 = {
            "id": "test-cmg-4",
            "cmg_number": "4",
            "title": "Anaphylaxis",
            "is_icp_only": False,
            "dose_lookup": {
                "Adrenaline": [
                    {
                        "text": "Adrenaline IM 0.3mg for anaphylaxis",
                        "dose_values": [{"amount": "0.3", "unit": "mg"}],
                        "qualifications_required": ["AP"],
                    }
                ],
                "Glucagon": [
                    {
                        "text": "Glucagon IM 1mg",
                        "dose_values": [{"amount": "1", "unit": "mg"}],
                        "qualifications_required": ["AP"],
                    }
                ],
            },
            "service": "actas",
            "guideline_id": "CMG_4",
            "qualifications_required": ["AP"],
        }
        (structured / "doc1.json").write_text(json.dumps(doc1))
        (structured / "doc2.json").write_text(json.dumps(doc2))
        return structured

    def test_adrenaline_aggregated_from_two_guidelines(self, tmp_path: Path):
        structured = self._make_dir_with_shared_medication(tmp_path)
        output = tmp_path / "medications"
        result = build_medication_index(structured, output)

        assert result["Adrenaline"] == 2
        adrenaline_file = output / "adrenaline.json"
        data = json.loads(adrenaline_file.read_text())
        assert data["total_entries"] == 2
        assert len(data["dose_entries"]) == 2

    def test_sources_list_includes_all_guidelines(self, tmp_path: Path):
        structured = self._make_dir_with_shared_medication(tmp_path)
        output = tmp_path / "medications"
        build_medication_index(structured, output)

        adrenaline_file = output / "adrenaline.json"
        data = json.loads(adrenaline_file.read_text())
        assert set(data["sources"]) == {"CMG_1", "CMG_4"}

    def test_glucagon_only_from_one_guideline(self, tmp_path: Path):
        structured = self._make_dir_with_shared_medication(tmp_path)
        output = tmp_path / "medications"
        result = build_medication_index(structured, output)

        assert result["Glucagon"] == 1
        glucagon_file = output / "glucagon.json"
        data = json.loads(glucagon_file.read_text())
        assert data["sources"] == ["CMG_4"]

    def test_entries_carry_correct_source_title(self, tmp_path: Path):
        structured = self._make_dir_with_shared_medication(tmp_path)
        output = tmp_path / "medications"
        build_medication_index(structured, output)

        adrenaline_file = output / "adrenaline.json"
        data = json.loads(adrenaline_file.read_text())
        titles = {e["source_title"] for e in data["dose_entries"]}
        assert titles == {"General Care", "Anaphylaxis"}


# ---------------------------------------------------------------------------
# 4. Output dir is created if missing
# ---------------------------------------------------------------------------
class TestOutputDirCreation:
    def test_creates_missing_output_dir(self, fixture_structured_dir: Path, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "medications"
        assert not nested.exists()
        build_medication_index(fixture_structured_dir, nested)
        assert nested.exists()
        assert nested.is_dir()

    def test_works_with_existing_output_dir(self, fixture_structured_dir: Path, tmp_path: Path):
        output = tmp_path / "medications"
        output.mkdir()
        build_medication_index(fixture_structured_dir, output)
        assert any(output.iterdir())


# ---------------------------------------------------------------------------
# 5. Empty dose_lookup produces no medication file
# ---------------------------------------------------------------------------
class TestEmptyDoseLookup:
    def test_empty_dose_lookup_produces_no_file(self, tmp_path: Path):
        structured = tmp_path / "structured"
        structured.mkdir()
        doc = {
            "id": "test-cmg-empty",
            "cmg_number": "99",
            "title": "No Meds Guideline",
            "is_icp_only": False,
            "dose_lookup": {},
            "service": "actas",
            "guideline_id": "CMG_99",
        }
        (structured / "empty_doc.json").write_text(json.dumps(doc))
        output = tmp_path / "medications"
        result = build_medication_index(structured, output)
        assert result == {}
        assert not any(output.iterdir())

    def test_idempotent_overwrites(self, fixture_structured_dir: Path, tmp_path: Path):
        output = tmp_path / "medications"
        result1 = build_medication_index(fixture_structured_dir, output)
        files_after_first = sorted(f.name for f in output.iterdir())
        result2 = build_medication_index(fixture_structured_dir, output)
        files_after_second = sorted(f.name for f in output.iterdir())
        assert result1 == result2
        assert files_after_first == files_after_second
