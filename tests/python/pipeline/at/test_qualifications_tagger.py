"""
Tests for AT qualification level tagging for guideline sections.

These tests verify that the qualifications tagger can:
1. Tag sections with appropriate qualification requirements
2. Handle universal content (no restrictions)
3. Detect ICP-specific content
4. Detect PACER-specific content
5. Detect CP/ECP-specific content
6. Handle VAO baseline content
7. Tag entire guidelines with section-level granularity
"""

import pytest

from src.python.pipeline.at.qualifications_tagger import (
    tag_section_qualifications,
    tag_guideline_qualifications,
    tag_medicine_qualifications,
)


class TestTagSectionQualifications:
    """Test single section qualification tagging."""

    def test_universal_section_gets_empty_required(self):
        """Universal sections should have empty qualifications_required."""
        section = {"heading": "Indications", "body": "Chest pain."}
        result = tag_section_qualifications(section)
        assert result["qualifications_required"] == []

    def test_icp_tagged_section(self):
        """ICP-specific sections should be tagged with ICP."""
        section = {"heading": "ICP Management", "body": "Cold intubation protocol."}
        result = tag_section_qualifications(section)
        assert "ICP" in result["qualifications_required"]

    def test_icp_keywords_in_body(self):
        """ICP keywords in body should trigger ICP tag."""
        section = {
            "heading": "Clinical Management",
            "body": "Paramedics may administer oxygen. ICPs may perform rapid sequence intubation."
        }
        result = tag_section_qualifications(section)
        assert "ICP" in result["qualifications_required"]

    def test_pacer_tagged_section(self):
        """PACER-specific sections should be tagged with PACER."""
        section = {
            "heading": "PACER Protocol",
            "body": "PACER-specific assessment and management."
        }
        result = tag_section_qualifications(section)
        assert "PACER" in result["qualifications_required"]

    def test_cp_ecp_tagged_section(self):
        """CP/ECP-specific sections should be tagged with CP_ECP."""
        section = {
            "heading": "Community Paramedic Interventions",
            "body": "Extended care paramedic assessment."
        }
        result = tag_section_qualifications(section)
        assert "CP_ECP" in result["qualifications_required"]

    def test_vao_scope_section(self):
        """VAO baseline content should be universally available."""
        section = {
            "heading": "Basic Life Support",
            "body": "BPR, AED, OPA. Airway positioning."
        }
        result = tag_section_qualifications(section)
        # VAO content is available to all AT levels
        assert result["qualifications_required"] == []

    def test_conservative_default(self):
        """Uncertain sections should default to empty (universally available)."""
        section = {
            "heading": "General Assessment",
            "body": "Assess patient condition and vital signs."
        }
        result = tag_section_qualifications(section)
        assert result["qualifications_required"] == []

    def test_preserves_heading_and_body(self):
        """Should preserve original heading and body."""
        section = {
            "heading": "Test Heading",
            "body": "Test body content."
        }
        result = tag_section_qualifications(section)
        assert result["heading"] == "Test Heading"
        assert result["body"] == "Test body content."

    def test_multiple_qualifications_in_section(self):
        """Sections with multiple qualification markers should tag all found."""
        section = {
            "heading": "Advanced Protocols",
            "body": "ICP: Cold intubation. PACER: Cardiac pacing. CP/ECP: Extended care."
        }
        result = tag_section_qualifications(section)
        assert "ICP" in result["qualifications_required"]
        assert "PACER" in result["qualifications_required"]
        assert "CP_ECP" in result["qualifications_required"]

    def test_icp_intensive_care_variations(self):
        """Should detect various ICP terminology patterns."""
        variations = [
            {"heading": "Intensive Care", "body": "Advanced protocols."},
            {"heading": "Management", "body": "Intensive Care Paramedic interventions."},
            {"heading": "Procedures", "body": "cold intubation for ICPs."},
        ]

        for section in variations:
            result = tag_section_qualifications(section)
            assert "ICP" in result["qualifications_required"], f"Failed for: {section}"

    def test_case_insensitive_matching(self):
        """Qualification detection should be case-insensitive."""
        section = {
            "heading": "Management",
            "body": "icp, pacer, and cp/ecp protocols."
        }
        result = tag_section_qualifications(section)
        assert "ICP" in result["qualifications_required"]
        assert "PACER" in result["qualifications_required"]
        assert "CP_ECP" in result["qualifications_required"]


class TestTagGuidelineQualifications:
    """Test entire guideline qualification tagging."""

    def test_guideline_with_mixed_sections(self):
        """Guidelines with mixed section types should tag appropriately."""
        guideline = {
            "cpg_code": "A0201-1",
            "title": "Medical Cardiac Arrest",
            "sections": [
                {"heading": "Initial Assessment", "body": "DRABC."},
                {"heading": "ICP Interventions", "body": "Cold intubation, extended meds."},
            ]
        }
        result = tag_guideline_qualifications(guideline)

        # First section should be universal
        assert result["sections"][0]["qualifications_required"] == []

        # Second section should require ICP
        assert "ICP" in result["sections"][1]["qualifications_required"]

    def test_preserves_guideline_metadata(self):
        """Should preserve guideline metadata."""
        guideline = {
            "cpg_code": "A0201-1",
            "title": "Test Guideline",
            "category": "Cardiac",
            "route_slug": "test",
            "sections": [
                {"heading": "Overview", "body": "Test content."}
            ]
        }
        result = tag_guideline_qualifications(guideline)

        assert result["cpg_code"] == "A0201-1"
        assert result["title"] == "Test Guideline"
        assert result["category"] == "Cardiac"
        assert result["route_slug"] == "test"

    def test_empty_sections_list(self):
        """Should handle guidelines with no sections."""
        guideline = {
            "cpg_code": "D003",
            "title": "Adrenaline",
            "sections": []
        }
        result = tag_guideline_qualifications(guideline)

        assert result["sections"] == []
        assert result["cpg_code"] == "D003"

    def test_all_universal_sections(self):
        """Guidelines with all universal content should tag appropriately."""
        guideline = {
            "cpg_code": "A0101-1",
            "title": "Basic Assessment",
            "sections": [
                {"heading": "Primary Survey", "body": "DRABC."},
                {"heading": "Secondary Survey", "body": "Head to toe assessment."},
                {"heading": "Vital Signs", "body": "BP, HR, RR, SpO2, Temp."},
            ]
        }
        result = tag_guideline_qualifications(guideline)

        # All sections should be universal
        for section in result["sections"]:
            assert section["qualifications_required"] == []

    def test_complex_guideline_with_multiple_levels(self):
        """Should handle complex guidelines with multiple qualification levels."""
        guideline = {
            "cpg_code": "A0501-1",
            "title": "Advanced Airway Management",
            "sections": [
                {"heading": "Indications", "body": "Airway compromise."},
                {"heading": "Basic Airway", "body": "OPA, NPA, BVM."},
                {"heading": "ICP Procedures", "body": "RSI, cold intubation."},
                {"heading": "PACER Protocols", "body": "Cardiac pacing indications."},
                {"heading": "Community Care", "body": "CP/ECP extended assessment."},
            ]
        }
        result = tag_guideline_qualifications(guideline)

        assert result["sections"][0]["qualifications_required"] == []
        assert result["sections"][1]["qualifications_required"] == []
        assert "ICP" in result["sections"][2]["qualifications_required"]
        assert "PACER" in result["sections"][3]["qualifications_required"]
        assert "CP_ECP" in result["sections"][4]["qualifications_required"]

    def test_does_not_modify_original_guideline(self):
        """Should not modify the input guideline dict."""
        guideline = {
            "cpg_code": "A0201-1",
            "title": "Test",
            "sections": [
                {"heading": "ICP Management", "body": "Cold intubation."}
            ]
        }

        original_sections = guideline["sections"].copy()
        result = tag_guideline_qualifications(guideline)

        # Original should be unchanged
        assert guideline["sections"] == original_sections

        # Result should have qualifications tagged
        assert "ICP" in result["sections"][0]["qualifications_required"]


class TestQualificationPatterns:
    """Test specific qualification pattern detection."""

    def test_intensive_care_paramedic_phrase(self):
        """Should detect 'Intensive Care Paramedic' phrase."""
        section = {
            "heading": "Qualifications",
            "body": "Intensive Care Paramedic may administer this medication."
        }
        result = tag_section_qualifications(section)
        assert "ICP" in result["qualifications_required"]

    def test_community_paramedic_variations(self):
        """Should detect various CP/ECP terminology patterns."""
        variations = [
            {"heading": "Community Paramedic", "body": "Extended role."},
            {"heading": "Extended Care", "body": "Paramedic extended care protocols."},
            {"heading": "CP/ECP", "body": "Community and extended care."},
        ]

        for section in variations:
            result = tag_section_qualifications(section)
            assert "CP_ECP" in result["qualifications_required"], f"Failed for: {section}"

    def test_pacer_variations(self):
        """Should detect various PACER terminology patterns."""
        variations = [
            {"heading": "PACER Assessment", "body": "PACER-specific protocols."},
            {"heading": "Pacing", "body": "pacer cardiac management."},
        ]

        for section in variations:
            result = tag_section_qualifications(section)
            assert "PACER" in result["qualifications_required"], f"Failed for: {section}"

    def test_no_false_positives_for_paramedic_word(self):
        """The word 'paramedic' alone should not trigger PARAMEDIC qualification."""
        section = {
            "heading": "Assessment",
            "body": "The paramedic should assess the patient using standard protocols."
        }
        result = tag_section_qualifications(section)
        # Should be universal, not PARAMEDIC-restricted
        assert result["qualifications_required"] == []

    def test_medication_restriction_by_qualification(self):
        """Should detect qualification-restricted medications."""
        section = {
            "heading": "Clinical Management",
            "body": "ICP: Amiodarone, RSI drugs. Paramedic: Adrenaline, fentanyl."
        }
        result = tag_section_qualifications(section)
        # ICP should be tagged due to ICP-specific medications
        assert "ICP" in result["qualifications_required"]


class TestTagMedicineQualifications:
    """Test per-medicine qualification tagging."""

    def test_paramedic_medicine_gets_empty_required(self):
        """Medicines available to all PARAMEDIC-level staff."""
        med = {"name": "Adrenaline", "cpg_code": "D003"}
        result = tag_medicine_qualifications(med)
        assert result["qualifications_required"] == []

    def test_icp_medicine_gets_icp_required(self):
        """Medicines restricted to ICP endorsement."""
        med = {"name": "Amiodarone", "cpg_code": "D004"}
        result = tag_medicine_qualifications(med)
        assert "ICP" in result["qualifications_required"]

    def test_preserves_all_original_keys(self):
        """Should preserve all original medicine dict keys."""
        med = {
            "name": "Morphine",
            "cpg_code": "D005",
            "category": "Analgesic",
            "route_slug": "morphine",
        }
        result = tag_medicine_qualifications(med)
        assert result["name"] == "Morphine"
        assert result["cpg_code"] == "D005"
        assert result["category"] == "Analgesic"
        assert result["route_slug"] == "morphine"

    def test_unknown_medicine_defaults_to_universal(self):
        """Unknown medicines should default to empty (universally available)."""
        med = {"name": "Unknown Medicine", "cpg_code": "D999"}
        result = tag_medicine_qualifications(med)
        assert result["qualifications_required"] == []

    def test_case_insensitive_medicine_matching(self):
        """Medicine name matching should be case-insensitive."""
        med = {"name": "amiodarone", "cpg_code": "D004"}
        result = tag_medicine_qualifications(med)
        assert "ICP" in result["qualifications_required"]

    def test_whitespace_tolerant_medicine_matching(self):
        """Medicine name matching should tolerate extra whitespace."""
        med = {"name": " Amiodarone ", "cpg_code": "D004"}
        result = tag_medicine_qualifications(med)
        assert "ICP" in result["qualifications_required"]

    def test_does_not_modify_original_medicine_dict(self):
        """Should not modify the input medicine dict."""
        med = {"name": "Adrenaline", "cpg_code": "D003"}
        original = dict(med)
        result = tag_medicine_qualifications(med)
        assert med == original
        assert "qualifications_required" in result
        assert "qualifications_required" not in med
