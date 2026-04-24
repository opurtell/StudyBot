import pytest
import os
import json
from pipeline.actas.models import CMGGuideline
from pipeline.actas.flowcharts import convert_to_mermaid
from pipeline.actas.chunker import determine_chunk_type


def test_pydantic_schema_validation():
    mock_cmg = {
        "id": "CMG_12_Asthma",
        "cmg_number": "12",
        "title": "Asthma",
        "section": "Respiratory",
        "content_markdown": "# Asthma\nTreatment for asthma.",
        "checksum": "abc123hash",
        "extraction_metadata": {
            "timestamp": "2026-04-01T00:00:00Z",
            "source_type": "cmg",
            "agent_version": "1.0",
        },
    }

    # Should not raise exception
    cmg = CMGGuideline(**mock_cmg)
    assert cmg.cmg_number == "12"
    assert cmg.section == "Respiratory"


def test_structure_flags_short_content(tmp_path):
    from pipeline.actas.structurer import structure_guidelines

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    guidelines = [
        {
            "cmg_number": "99",
            "title": "Test Short CMG",
            "section": "Other",
            "spotlightId": "test123",
            "tags": [],
            "atp": [],
            "content_html": "",
            "content_markdown": "",
        },
        {
            "cmg_number": "100",
            "title": "Test Good CMG",
            "section": "Medical",
            "spotlightId": "test456",
            "tags": [],
            "atp": [],
            "content_html": "",
            "content_markdown": "## Indications\n- Chest pain with haemodynamic instability\n- Suspected aortic dissection",
        },
    ]

    with open(raw_dir / "guidelines.json", "w") as f:
        json.dump(guidelines, f)

    output_dir = tmp_path / "structured"
    structure_guidelines(
        guidelines_path=str(raw_dir / "guidelines.json"),
        output_dir=str(output_dir),
    )

    with open(output_dir / "CMG_99_Test_Short_CMG.json") as f:
        short_cmg = json.load(f)
    assert short_cmg.get("extraction_metadata", {}).get("content_flag") == "short"

    with open(output_dir / "CMG_100_Test_Good_CMG.json") as f:
        good_cmg = json.load(f)
    assert good_cmg.get("extraction_metadata", {}).get("content_flag") is None


def test_mermaid_conversion():
    svg_mock = "<svg><text y='10'>Start</text></svg>"
    mmd = convert_to_mermaid(svg_mock)
    assert "graph TD" in mmd
    assert "Condition critical" in mmd


def test_chunk_type_determination():
    dose_text = "The recommended dose of adrenaline for 25kg is 0.25mg"
    assert determine_chunk_type(dose_text) == "dosage"

    safety_text = "Contraindications include severe hypersensitivity."
    assert determine_chunk_type(safety_text) == "safety"

    gen_text = "The patient arrived on scene."
    assert determine_chunk_type(gen_text) == "general"


def test_dose_lookup_matches_by_content(tmp_path):
    from pipeline.actas.structurer import structure_guidelines

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    guidelines = [
        {
            "cmg_number": "4",
            "title": "Cardiac Arrest: Adult",
            "section": "Cardiac",
            "spotlightId": "testCardiac",
            "tags": [],
            "atp": [],
            "content_html": "",
            "content_markdown": "# Cardiac Arrest: Adult\n\nAdrenaline 1mg IV every 3-5 minutes.\nAmiodarone 300mg IV bolus.",
        }
    ]
    dose_data = {
        "total_dose_groups": 1,
        "unique_medicines": ["Adrenaline", "Amiodarone"],
        "medicine_count": 2,
        "source_files": [],
        "medicine_index": {
            "Adrenaline": [
                {
                    "text": "Adrenaline 1mg IV",
                    "dose_values": [{"amount": "1", "unit": "mg"}],
                }
            ],
            "Amiodarone": [
                {
                    "text": "Amiodarone 300mg IV",
                    "dose_values": [{"amount": "300", "unit": "mg"}],
                }
            ],
        },
    }

    with open(raw_dir / "guidelines.json", "w") as f:
        json.dump(guidelines, f)
    with open(raw_dir / "dose_tables.json", "w") as f:
        json.dump(dose_data, f)

    output_dir = tmp_path / "structured"
    structure_guidelines(
        guidelines_path=str(raw_dir / "guidelines.json"),
        dose_tables_path=str(raw_dir / "dose_tables.json"),
        output_dir=str(output_dir),
    )

    with open(output_dir / "CMG_4_Cardiac_Arrest__Adult.json") as f:
        cmg = json.load(f)
    assert cmg["dose_lookup"] is not None
    assert "Adrenaline" in cmg["dose_lookup"]


def test_structure_handles_med_entries(tmp_path):
    from pipeline.actas.structurer import structure_guidelines

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    guidelines = [
        {
            "cmg_number": "01",
            "title": "Adrenaline",
            "section": "Medicine",
            "spotlightId": "med01test",
            "tags": [],
            "atp": [],
            "content_html": "",
            "content_markdown": "# Adrenaline\n\nPrimary treatment for anaphylaxis.",
            "entry_type": "med",
        },
    ]

    with open(raw_dir / "guidelines.json", "w") as f:
        json.dump(guidelines, f)

    output_dir = tmp_path / "structured"
    structure_guidelines(
        guidelines_path=str(raw_dir / "guidelines.json"),
        output_dir=str(output_dir),
    )

    med_dir = output_dir / "med"
    assert med_dir.exists()
    files = list(med_dir.glob("*.json"))
    assert len(files) == 1
    with open(files[0]) as f:
        data = json.load(f)
    assert data["extraction_metadata"]["source_type"] == "med"

    with open(output_dir / "guidelines-index.json") as f:
        guideline_index = json.load(f)
    with open(output_dir / "medications-index.json") as f:
        medication_index = json.load(f)

    assert guideline_index["items"][0]["source_type"] == "med"
    assert medication_index["items"][0]["name"] == "Adrenaline"


def test_structure_flags_known_icp_only_entries(tmp_path):
    from pipeline.actas.structurer import structure_guidelines

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    guidelines = [
        {
            "cmg_number": "02",
            "title": "Adenosine",
            "section": "Medicine",
            "content_markdown": "#### Doses\n- 6mg IV",
            "entry_type": "med",
        },
        {
            "cmg_number": "3B",
            "title": "Intubation Algorithm",
            "section": "Airway Management",
            "content_markdown": "# Intubation Algorithm\n\nPrepare RSI drugs as required.",
            "entry_type": "cmg",
        },
        {
            "cmg_number": "CSM.C05",
            "title": "External Cardiac Pacing (Zoll X Series)",
            "section": "Clinical Skill",
            "content_markdown": "#### Indications\n- Bradycardia with poor perfusion.",
            "entry_type": "csm",
        },
        {
            "cmg_number": "22",
            "title": "Midazolam",
            "section": "Medicine",
            "content_markdown": "#### Doses\n- 0.2mg/kg IM\n- **ICP:** 0.2mg/kg IV/IO",
            "entry_type": "med",
        },
    ]

    with open(raw_dir / "guidelines.json", "w") as f:
        json.dump(guidelines, f)

    output_dir = tmp_path / "structured"
    structure_guidelines(
        guidelines_path=str(raw_dir / "guidelines.json"),
        output_dir=str(output_dir),
    )

    with open(output_dir / "med" / "MED_02_Adenosine.json") as f:
        adenosine = json.load(f)
    assert adenosine["is_icp_only"] is True

    with open(output_dir / "CMG_3B_Intubation_Algorithm.json") as f:
        algorithm = json.load(f)
    assert algorithm["is_icp_only"] is True

    with open(output_dir / "csm" / "CMG_CSM.C05_External_Cardiac_Pacing__Zoll_X_Series_.json") as f:
        pacing = json.load(f)
    assert pacing["is_icp_only"] is True

    with open(output_dir / "med" / "MED_22_Midazolam.json") as f:
        midazolam = json.load(f)
    assert midazolam["is_icp_only"] is False
