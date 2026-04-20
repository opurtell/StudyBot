"""
Tests for AT medication denormalised index builder.
"""

import json

import pytest

from src.python.pipeline.at.medications_index import build_medications_index


def test_build_index_produces_per_medicine_files(tmp_path):
    """Test that build_medications_index creates per-medicine JSON files."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Write two guideline JSONs that reference Adrenaline
    # One with medications list (medicine monograph), one from a clinical guideline
    guideline1 = {
        "service": "at",
        "guideline_id": "AT_CPG_D003",
        "title": "Adrenaline",
        "categories": ["Medication Guidelines"],
        "medications": [
            {
                "medication": "Adrenaline",
                "indication": "Anaphylaxis",
                "dose": "0.3-0.5 mg IM",
                "route": "IM",
                "qualifications_required": ["Paramedic"],
            },
            {
                "medication": "Adrenaline",
                "indication": "Cardiac Arrest",
                "dose": "1 mg IV/IO",
                "route": "IV",
                "qualifications_required": ["Intensive Care Paramedic"],
            },
        ],
    }

    guideline2 = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "medications": [
            {
                "medication": "Adrenaline",
                "indication": "Cardiac Arrest",
                "dose": "1 mg IV/IO every 3-5 minutes",
                "route": "IV",
                "qualifications_required": ["Paramedic"],
            }
        ],
    }

    (structured_dir / "AT_CPG_D003.json").write_text(json.dumps(guideline1))
    (structured_dir / "AT_CPG_A0201-1.json").write_text(json.dumps(guideline2))

    output_dir = tmp_path / "medications"
    count = build_medications_index(str(structured_dir), str(output_dir))

    assert count >= 1
    assert (output_dir / "adrenaline.json").exists()


def test_build_index_aggregates_all_doses_for_medicine(tmp_path):
    """Test that all doses for a medicine are aggregated from multiple guidelines."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    guideline1 = {
        "service": "at",
        "guideline_id": "AT_CPG_D003",
        "title": "Adrenaline",
        "categories": ["Medication Guidelines"],
        "medications": [
            {
                "medication": "Adrenaline",
                "indication": "Anaphylaxis",
                "dose": "0.3-0.5 mg IM",
                "route": "IM",
                "qualifications_required": ["Paramedic"],
            }
        ],
    }

    guideline2 = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "medications": [
            {
                "medication": "Adrenaline",
                "indication": "Cardiac Arrest",
                "dose": "1 mg IV/IO",
                "route": "IV",
                "qualifications_required": ["Paramedic"],
            }
        ],
    }

    (structured_dir / "AT_CPG_D003.json").write_text(json.dumps(guideline1))
    (structured_dir / "AT_CPG_A0201-1.json").write_text(json.dumps(guideline2))

    output_dir = tmp_path / "medications"
    count = build_medications_index(str(structured_dir), str(output_dir))

    assert count == 1

    # Verify the aggregated file contains all entries
    adrenaline_file = output_dir / "adrenaline.json"
    assert adrenaline_file.exists()

    data = json.loads(adrenaline_file.read_text())
    assert data["medication"] == "Adrenaline"
    assert data["service"] == "at"
    assert len(data["entries"]) == 2

    # Verify each entry has required fields
    for entry in data["entries"]:
        assert "medication" in entry
        assert "indication" in entry
        assert "dose" in entry
        assert "route" in entry
        assert "qualifications_required" in entry
        assert "service" in entry
        assert "guideline_id" in entry
        assert "source_file" in entry


def test_build_index_handles_medicines_with_spaces(tmp_path):
    """Test that medicine names with spaces are converted to slugs correctly."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    guideline = {
        "service": "at",
        "guideline_id": "AT_CPG_D001",
        "title": "Ipratropium Bromide",
        "categories": ["Medication Guidelines"],
        "medications": [
            {
                "medication": "Ipratropium Bromide",
                "indication": "Asthma",
                "dose": "0.5 mg nebulised",
                "route": "inhaled",
                "qualifications_required": ["Paramedic"],
            }
        ],
    }

    (structured_dir / "AT_CPG_D001.json").write_text(json.dumps(guideline))

    output_dir = tmp_path / "medications"
    count = build_medications_index(str(structured_dir), str(output_dir))

    assert count == 1
    assert (output_dir / "ipratropium-bromide.json").exists()


def test_build_index_skips_guidelines_without_medications(tmp_path):
    """Test that guidelines without medications are skipped."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Guideline with no medications
    guideline1 = {
        "service": "at",
        "guideline_id": "AT_CPG_A0101",
        "title": "Assessment",
        "categories": ["Clinical Skills"],
        "medications": [],
    }

    (structured_dir / "AT_CPG_A0101.json").write_text(json.dumps(guideline1))

    output_dir = tmp_path / "medications"
    count = build_medications_index(str(structured_dir), str(output_dir))

    assert count == 0
    assert not any(output_dir.iterdir())  # Output directory should be empty


def test_build_index_malenames_to_slugs(tmp_path):
    """Test that medicine names are converted to slugs correctly."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    guideline = {
        "service": "at",
        "guideline_id": "AT_CPG_D005",
        "title": "Salbutamol",
        "categories": ["Medication Guidelines"],
        "medications": [
            {
                "medication": "Salbutamol (Sulfate)",
                "indication": "Asthma",
                "dose": "2.5-5 mg nebulised",
                "route": "inhaled",
                "qualifications_required": ["Paramedic"],
            }
        ],
    }

    (structured_dir / "AT_CPG_D005.json").write_text(json.dumps(guideline))

    output_dir = tmp_path / "medications"
    build_medications_index(str(structured_dir), str(output_dir))

    # Parentheses should be stripped, spaces converted to hyphens
    assert (output_dir / "salbutamol-sulfate.json").exists()


def test_build_index_preserves_all_medication_fields(tmp_path):
    """Test that all MedicationDose fields are preserved in the index."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    guideline = {
        "service": "at",
        "guideline_id": "AT_CPG_D010",
        "title": "Fentanyl",
        "categories": ["Medication Guidelines"],
        "medications": [
            {
                "medication": "Fentanyl",
                "indication": "Pain Relief",
                "dose": "1-2 mcg/kg IV",
                "route": "IV",
                "qualifications_required": ["Intensive Care Paramedic", "Paramedic"],
            }
        ],
    }

    (structured_dir / "AT_CPG_D010.json").write_text(json.dumps(guideline))

    output_dir = tmp_path / "medications"
    build_medications_index(str(structured_dir), str(output_dir))

    fentanyl_file = output_dir / "fentanyl.json"
    data = json.loads(fentanyl_file.read_text())

    entry = data["entries"][0]
    assert entry["medication"] == "Fentanyl"
    assert entry["indication"] == "Pain Relief"
    assert entry["dose"] == "1-2 mcg/kg IV"
    assert entry["route"] == "IV"
    assert entry["qualifications_required"] == ["Intensive Care Paramedic", "Paramedic"]
    assert entry["service"] == "at"
    assert entry["guideline_id"] == "AT_CPG_D010"
    assert entry["source_file"] == "AT_CPG_D010.json"


def test_build_index_handles_multiple_medicines(tmp_path):
    """Test that multiple medicines are processed correctly."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    guideline = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "medications": [
            {
                "medication": "Adrenaline",
                "indication": "Cardiac Arrest",
                "dose": "1 mg IV/IO",
                "route": "IV",
                "qualifications_required": ["Paramedic"],
            },
            {
                "medication": "Amiodarone",
                "indication": "Cardiac Arrest",
                "dose": "300 mg IV/IO",
                "route": "IV",
                "qualifications_required": ["Intensive Care Paramedic"],
            },
        ],
    }

    (structured_dir / "AT_CPG_A0201-1.json").write_text(json.dumps(guideline))

    output_dir = tmp_path / "medications"
    count = build_medications_index(str(structured_dir), str(output_dir))

    assert count == 2
    assert (output_dir / "adrenaline.json").exists()
    assert (output_dir / "amiodarone.json").exists()


def test_build_index_returns_file_count(tmp_path):
    """Test that build_medications_index returns correct count."""
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()

    # Create 3 medicines across 2 guidelines
    guideline1 = {
        "service": "at",
        "guideline_id": "AT_CPG_D003",
        "title": "Adrenaline",
        "categories": ["Medication Guidelines"],
        "medications": [
            {
                "medication": "Adrenaline",
                "indication": "Anaphylaxis",
                "dose": "0.3-0.5 mg IM",
                "route": "IM",
                "qualifications_required": ["Paramedic"],
            }
        ],
    }

    guideline2 = {
        "service": "at",
        "guideline_id": "AT_CPG_A0201-1",
        "title": "Cardiac Arrest",
        "categories": ["Clinical Guidelines"],
        "medications": [
            {
                "medication": "Adrenaline",
                "indication": "Cardiac Arrest",
                "dose": "1 mg IV/IO",
                "route": "IV",
                "qualifications_required": ["Paramedic"],
            },
            {
                "medication": "Amiodarone",
                "indication": "Cardiac Arrest",
                "dose": "300 mg IV/IO",
                "route": "IV",
                "qualifications_required": ["Intensive Care Paramedic"],
            },
            {
                "medication": "Magnesium Sulfate",
                "indication": "Cardiac Arrest",
                "dose": "2 g IV/IO",
                "route": "IV",
                "qualifications_required": ["Intensive Care Paramedic"],
            },
        ],
    }

    (structured_dir / "AT_CPG_D003.json").write_text(json.dumps(guideline1))
    (structured_dir / "AT_CPG_A0201-1.json").write_text(json.dumps(guideline2))

    output_dir = tmp_path / "medications"
    count = build_medications_index(str(structured_dir), str(output_dir))

    # Should count unique medicines: Adrenaline, Amiodarone, Magnesium Sulfate
    assert count == 3
