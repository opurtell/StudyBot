"""Tests for AT pipeline structurer."""

import json
from datetime import date

from src.python.services.schema import GuidelineDocument
from src.python.pipeline.at.structurer import structure_guideline


def test_structure_guideline_produces_valid_document():
    """Test structuring a clinical guideline produces valid GuidelineDocument."""
    raw = {
        "cpg_code": "A0201-1",
        "title": "Medical Cardiac Arrest",
        "category": "Cardiac Arrest",
        "sections": [
            {"heading": "Initial Assessment", "body": "Confirm cardiac arrest.", "qualifications_required": ["Paramedic"]},
            {"heading": "Defibrillation", "body": "Analyse rhythm.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [
            {"medication": "Adrenaline", "indication": "Cardiac Arrest", "dose": "1 mg IV", "route": "IV", "qualifications_required": ["Paramedic"]},
        ],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/cardiac-arrest/medical-cardiac-arrest",
        "source_hash": "abc123",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.service == "at"
    assert doc.guideline_id == "AT_CPG_A0201-1"
    assert doc.title == "Medical Cardiac Arrest"
    assert len(doc.content_sections) == 2
    assert len(doc.medications) == 1
    assert doc.categories == ["Clinical Guidelines"]
    assert doc.qualifications_required == ["Paramedic"]
    assert doc.source_url == raw["source_url"]
    assert doc.source_hash == "abc123"


def test_structure_medicine_monograph_produces_valid_document():
    """Test structuring a medicine monograph produces valid GuidelineDocument."""
    raw = {
        "cpg_code": "D003",
        "title": "Adrenaline",
        "category": "Medicines",
        "sections": [
            {"heading": "Pharmacology", "body": "Alpha and beta receptor agonist.", "qualifications_required": []},
            {"heading": "Dose Recommendations", "body": "Adult bolus: 1 mg IV every 3-5 min.", "qualifications_required": ["Paramedic", "Intensive Care Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/medicines/page/adrenaline",
        "source_hash": "def456",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.guideline_id == "AT_CPG_D003"
    assert doc.categories == ["Medication Guidelines", "Pharmacology"]
    assert doc.qualifications_required == ["Intensive Care Paramedic", "Paramedic"]
    assert len(doc.content_sections) == 2


def test_structure_guideline_with_flowchart():
    """Test structuring a guideline with flowchart includes flowchart data."""
    raw = {
        "cpg_code": "A0201-1",
        "title": "Medical Cardiac Arrest",
        "category": "Cardiac Arrest",
        "sections": [
            {"heading": "Algorithm", "body": "Follow the algorithm.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [
            {
                "cpg_code": "A0201-1",
                "title": "Cardiac Arrest Algorithm",
                "source_format": "data",
                "mermaid": "graph TD\nA[Start] --> B[Assess]",
                "asset_ref": None,
                "review_required": False,
            }
        ],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/cardiac-arrest/medical-cardiac-arrest",
        "source_hash": "ghi789",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert len(doc.flowcharts) == 1
    assert doc.flowcharts[0].title == "Cardiac Arrest Algorithm"
    assert doc.flowcharts[0].mermaid == "graph TD\nA[Start] --> B[Assess]"
    assert doc.flowcharts[0].source_format == "data"


def test_structure_guideline_multiple_medications():
    """Test structuring guideline with multiple medications."""
    raw = {
        "cpg_code": "A0501",
        "title": "Pain Relief",
        "category": "Pain Relief",
        "sections": [
            {"heading": "Assessment", "body": "Assess pain severity.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [
            {"medication": "Morphine", "indication": "Moderate to severe pain", "dose": "2.5-5 mg IV", "route": "IV", "qualifications_required": ["Paramedic"]},
            {"medication": "Fentanyl", "indication": "Severe pain", "dose": "0.5-1 mcg/kg IV", "route": "IV", "qualifications_required": ["Paramedic", "Intensive Care Paramedic"]},
        ],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/pain-relief",
        "source_hash": "jkl012",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert len(doc.medications) == 2
    assert doc.medications[0].medication == "Morphine"
    assert doc.medications[1].medication == "Fentanyl"
    assert doc.qualifications_required == ["Intensive Care Paramedic", "Paramedic"]


def test_structure_guideline_obstetrics():
    """Test structuring obstetrics guideline maps to correct category."""
    raw = {
        "cpg_code": "M001",
        "title": "Antenatal Assessment",
        "category": "Obstetrics",
        "sections": [
            {"heading": "Assessment", "body": "Perform assessment.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/maternity/antenatal-assessment",
        "source_hash": "mno345",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.guideline_id == "AT_CPG_M001"
    assert doc.categories == ["Clinical Guidelines"]


def test_structure_guideline_paediatric():
    """Test structuring paediatric guideline maps to correct category."""
    raw = {
        "cpg_code": "P0201",
        "title": "Paediatric Assessment",
        "category": "Paediatric",
        "sections": [
            {"heading": "Assessment", "body": "Assess child.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/paediatric/paediatric-assessment",
        "source_hash": "pqr678",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.guideline_id == "AT_CPG_P0201"
    assert doc.categories == ["Clinical Guidelines"]


def test_structure_guideline_equipment_reference():
    """Test structuring equipment/reference guideline maps to operational category."""
    raw = {
        "cpg_code": "E002",
        "title": "Equipment Checklist",
        "category": "Reference Notes",
        "sections": [
            {"heading": "Daily Check", "body": "Check equipment daily.", "qualifications_required": []},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/equipment/equipment-checklist",
        "source_hash": "stu901",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.guideline_id == "AT_CPG_E002"
    assert doc.categories == ["Operational Guidelines"]


def test_structure_guideline_clinical_skills():
    """Test structuring assessment guideline maps to clinical skills."""
    raw = {
        "cpg_code": "A0101",
        "title": "Primary Assessment",
        "category": "Assessment",
        "sections": [
            {"heading": "Overview", "body": "Perform primary assessment.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/assessment/primary-assessment",
        "source_hash": "vwx234",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.guideline_id == "AT_CPG_A0101"
    assert doc.categories == ["Clinical Skills"]


def test_structure_guideline_airway_management():
    """Test structuring airway management guideline maps to clinical skills."""
    raw = {
        "cpg_code": "A0301",
        "title": "Basic Airway Management",
        "category": "Airway Management",
        "sections": [
            {"heading": "Techniques", "body": "Open airway.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/airway-management/basic-airway-management",
        "source_hash": "yza567",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.guideline_id == "AT_CPG_A0301"
    assert doc.categories == ["Clinical Skills"]


def test_structure_guideline_cardiac():
    """Test structuring cardiac guideline maps to clinical guidelines."""
    raw = {
        "cpg_code": "A0401",
        "title": "Acute Myocardial Infarction",
        "category": "Cardiac",
        "sections": [
            {"heading": "Assessment", "body": "Assess chest pain.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/cardiac/acute-myocardial-infarction",
        "source_hash": "bcd890",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.guideline_id == "AT_CPG_A0401"
    assert doc.categories == ["Clinical Guidelines"]


def test_structure_guideline_mental_health():
    """Test structuring mental health guideline maps to clinical guidelines."""
    raw = {
        "cpg_code": "A0106",
        "title": "Behavioural Emergency",
        "category": "Mental Health",
        "sections": [
            {"heading": "Assessment", "body": "Assess behaviour.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/assessment/behavioural-emergency",
        "source_hash": "efg123",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.guideline_id == "AT_CPG_A0106"
    assert doc.categories == ["Clinical Guidelines"]


def test_structure_guideline_empty_sections():
    """Test structuring guideline with no sections produces valid document."""
    raw = {
        "cpg_code": "E009",
        "title": "Reference Note",
        "category": "Reference Notes",
        "sections": [],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/equipment/reference-note",
        "source_hash": "hij456",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert len(doc.content_sections) == 0
    assert len(doc.medications) == 0
    assert len(doc.flowcharts) == 0
    assert doc.qualifications_required == []


def test_structure_guideline_with_last_modified():
    """Test structuring guideline with last_modified date."""
    raw = {
        "cpg_code": "A0201-1",
        "title": "Medical Cardiac Arrest",
        "category": "Cardiac Arrest",
        "sections": [
            {"heading": "Initial Assessment", "body": "Confirm cardiac arrest.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/cardiac-arrest/medical-cardiac-arrest",
        "source_hash": "klm789",
        "last_modified": "2024-03-15",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.last_modified == date(2024, 3, 15)


def test_structure_guideline_with_extra_metadata():
    """Test structuring guideline preserves extra metadata."""
    raw = {
        "cpg_code": "A0201-1",
        "title": "Medical Cardiac Arrest",
        "category": "Cardiac Arrest",
        "sections": [
            {"heading": "Initial Assessment", "body": "Confirm cardiac arrest.", "qualifications_required": ["Paramedic"]},
        ],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/tabs/guidelines/adult-patient-guidelines/cardiac-arrest/medical-cardiac-arrest",
        "source_hash": "nop012",
        "version": "2.1",
        "review_date": "2024-06-30",
    }
    doc_dict = structure_guideline(raw)
    doc = GuidelineDocument(**doc_dict)

    assert doc.extra == {
        "version": "2.1",
        "review_date": "2024-06-30",
    }


def test_structure_all_guidelines(tmp_path):
    """Test structuring multiple guidelines from directory."""
    import os
    from src.python.pipeline.at.structurer import structure_all_guidelines

    # Create test input files
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    output_dir = tmp_path / "structured"
    output_dir.mkdir()

    # Write two test guidelines
    guideline1 = {
        "cpg_code": "A0201-1",
        "title": "Medical Cardiac Arrest",
        "category": "Cardiac Arrest",
        "sections": [{"heading": "Overview", "body": "Content", "qualifications_required": ["Paramedic"]}],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/test1",
        "source_hash": "hash1",
    }
    guideline2 = {
        "cpg_code": "D003",
        "title": "Adrenaline",
        "category": "Medicines",
        "sections": [{"heading": "Pharmacology", "body": "Content", "qualifications_required": []}],
        "medicines": [],
        "flowcharts": [],
        "source_url": "https://cpg.ambulance.tas.gov.au/test2",
        "source_hash": "hash2",
    }

    with open(raw_dir / "A0201-1.json", "w") as f:
        json.dump(guideline1, f)
    with open(raw_dir / "D003.json", "w") as f:
        json.dump(guideline2, f)

    # Process all guidelines
    count = structure_all_guidelines(str(raw_dir), str(output_dir))

    assert count == 2

    # Verify output files
    assert (output_dir / "AT_CPG_A0201-1.json").exists()
    assert (output_dir / "AT_CPG_D003.json").exists()

    # Verify content
    with open(output_dir / "AT_CPG_A0201-1.json") as f:
        doc1 = json.load(f)
    assert doc1["guideline_id"] == "AT_CPG_A0201-1"
    assert doc1["title"] == "Medical Cardiac Arrest"

    with open(output_dir / "AT_CPG_D003.json") as f:
        doc2 = json.load(f)
    assert doc2["guideline_id"] == "AT_CPG_D003"
    assert doc2["categories"] == ["Medication Guidelines", "Pharmacology"]
