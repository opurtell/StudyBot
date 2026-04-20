"""
Tests for AT CPG narrative dose text extraction (dose_extractor.py).

These tests verify that the dose extractor can:
1. Find dose-related sections from guideline content
2. Parse dose information from narrative text using regex
3. Normalise dose entries to a valid schema
4. Handle AT-specific dose formats (dilution ratios, max doses, etc.)
"""

import pytest

from src.python.pipeline.at.dose_extractor import (
    extract_dose_sections,
    parse_dose_text,
    normalise_dose_entry,
)


class TestExtractDoseSections:
    """Test dose section identification from guideline content."""

    def test_extract_dose_sections_finds_dose_recommendations(self):
        """Should identify 'Dose Recommendations' section."""
        content = {
            "sections": [
                {"heading": "Dose Recommendations", "body": "Adult bolus: 1 mg IV..."},
                {"heading": "Pharmacology", "body": "No dose info here."},
            ]
        }
        dose_sections = extract_dose_sections(content)
        assert len(dose_sections) == 1
        assert "Adult bolus" in dose_sections[0]["body"]

    def test_extract_dose_sections_finds_dosing_heading(self):
        """Should identify 'Dosing' section."""
        content = {
            "sections": [
                {"heading": "Dosing", "body": "1 mg IV every 3-5 minutes."},
                {"heading": "Contraindications", "body": "None."},
            ]
        }
        dose_sections = extract_dose_sections(content)
        assert len(dose_sections) == 1
        assert "1 mg IV" in dose_sections[0]["body"]

    def test_extract_dose_sections_finds_administration_heading(self):
        """Should identify 'Administration' section."""
        content = {
            "sections": [
                {"heading": "Administration", "body": "Administer 1 mg IV."},
            ]
        }
        dose_sections = extract_dose_sections(content)
        assert len(dose_sections) == 1
        assert "Administer 1 mg" in dose_sections[0]["body"]

    def test_extract_dose_sections_finds_dose_heading(self):
        """Should identify 'Dose' section."""
        content = {
            "sections": [
                {"heading": "Dose", "body": "Adult: 1 mg IV."},
            ]
        }
        dose_sections = extract_dose_sections(content)
        assert len(dose_sections) == 1
        assert "Adult: 1 mg" in dose_sections[0]["body"]

    def test_extract_dose_sections_returns_empty_for_non_dose_content(self):
        """Should return empty list when no dose sections found."""
        content = {
            "sections": [
                {"heading": "Pharmacology", "body": "No dose info here."},
                {"heading": "Indications", "body": "Cardiac arrest."},
            ]
        }
        dose_sections = extract_dose_sections(content)
        assert len(dose_sections) == 0

    def test_extract_dose_sections_handles_multiple_dose_sections(self):
        """Should find multiple dose-related sections."""
        content = {
            "sections": [
                {"heading": "Dose", "body": "Adult: 1 mg IV."},
                {"heading": "Administration", "body": "Give 1 mg IV."},
                {"heading": "Pharmacology", "body": "No dose."},
            ]
        }
        dose_sections = extract_dose_sections(content)
        assert len(dose_sections) == 2


class TestParseDoseText:
    """Test dose information parsing from narrative text."""

    def test_parse_dose_text_extracts_simple_iv_dose(self):
        """Should extract simple IV dose with quantity."""
        text = "Adult bolus dosing: 1 mg IV every 3-5 minutes."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Cardiac Arrest")
        assert len(entries) >= 1
        assert entries[0]["medication"] == "Adrenaline"
        assert "1 mg" in entries[0]["dose"]

    def test_parse_dose_text_extracts_dilution_ratio(self):
        """Should extract dilution ratio (1:10,000 format)."""
        text = "Adult bolus: 1 mg (1:10,000) IV every 3-5 minutes."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Cardiac Arrest")
        assert len(entries) >= 1
        assert "1:10,000" in entries[0]["dose"] or "1:10 000" in entries[0]["dose"]

    def test_parse_dose_text_extracts_max_dose(self):
        """Should extract maximum dose information."""
        text = "Adult infusion: 2-10 microg/min. Max total 10 mg."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Anaphylaxis")
        assert len(entries) >= 1
        assert "max" in entries[0]["dose"].lower() or "maximum" in entries[0]["dose"].lower()

    def test_parse_dose_text_extracts_hard_max(self):
        """Should extract hard max dose information."""
        text = "Paediatric infusion: 1 microg/kg/min. Hard max 100 microg/min."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Paediatric")
        assert len(entries) >= 1
        assert "hard max" in entries[0]["dose"].lower() or "100 microg/min" in entries[0]["dose"]

    def test_parse_dose_text_extracts_multiple_routes(self):
        """Should extract doses for different routes."""
        text = "IV: 1 mg every 3-5 minutes. IO: 1 mg every 3-5 minutes. IM: 0.5 mg."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Cardiac Arrest")
        assert len(entries) >= 2
        routes = [e.get("route") for e in entries]
        assert "IV" in routes or "IO" in routes

    def test_parse_dose_text_extracts_infusion_dose(self):
        """Should extract infusion dose with range."""
        text = "Adult infusion: start at 2 microg/min, titrate to response. Max 10 microg/min."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Anaphylaxis")
        assert len(entries) >= 1
        assert "microg/min" in entries[0]["dose"]

    def test_parse_dose_text_handles_weight_based_dosing(self):
        """Should extract weight-based dose (mg/kg)."""
        text = "Paediatric bolus: 0.01 mg/kg IV (max 1 mg)."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Paediatric")
        assert len(entries) >= 1
        assert "mg/kg" in entries[0]["dose"] or "0.01" in entries[0]["dose"]

    def test_parse_dose_text_extracts_dilution_instructions(self):
        """Should extract dilution recipe instructions."""
        text = "Dilution: 1 mg in 100 mL NaCl (1:100,000)."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Infusion")
        assert len(entries) >= 1
        assert "dilution" in entries[0]["dose"].lower() or "1:100" in entries[0]["dose"]

    def test_parse_dose_text_handles_multiple_entries(self):
        """Should extract multiple dose entries from one section."""
        text = """
        Adult bolus: 1 mg IV every 3-5 minutes.
        Paediatric bolus: 0.01 mg/kg IV (max 1 mg).
        Adult infusion: 2-10 microg/min.
        """
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Cardiac Arrest")
        assert len(entries) >= 2

    def test_parse_dose_text_returns_empty_for_non_dose_text(self):
        """Should return empty list when no dose information found."""
        text = "This section contains no dose information. See pharmacology."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Cardiac Arrest")
        assert len(entries) == 0

    def test_parse_dose_text_handles_complex_narrative(self):
        """Should handle complex AT narrative format with dilution steps."""
        text = """
        Adult bolus dosing (1:10,000 dilution): 1 mg IV every 3-5 minutes.
        Maximum total dose: 10 mg.
        For infusion: dilute 1 mg in 100 mL NaCl to make 1:100,000 solution.
        Start at 2 microg/min and titrate to response. Hard max 100 microg/min.
        """
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Anaphylaxis")
        assert len(entries) >= 1


class TestNormaliseDoseEntry:
    """Test dose entry normalisation to schema-valid dict."""

    def test_normalise_dose_entry_produces_valid_schema(self):
        """Should produce dict with all required keys."""
        raw = {
            "medication": "Adrenaline",
            "indication": "Cardiac Arrest",
            "dose": "1 mg IV",
            "route": "IV",
        }
        result = normalise_dose_entry(raw)
        assert result["medication"] == "Adrenaline"
        assert result["route"] == "IV"
        assert "dose" in result
        assert "indication" in result

    def test_normalise_dose_entry_preserves_medication(self):
        """Should preserve medication name."""
        raw = {
            "medication": "Adrenaline",
            "indication": "Cardiac Arrest",
            "dose": "1 mg IV",
            "route": "IV",
        }
        result = normalise_dose_entry(raw)
        assert result["medication"] == "Adrenaline"

    def test_normalise_dose_entry_preserves_indication(self):
        """Should preserve indication."""
        raw = {
            "medication": "Adrenaline",
            "indication": "Anaphylaxis",
            "dose": "1 mg IV",
            "route": "IV",
        }
        result = normalise_dose_entry(raw)
        assert result["indication"] == "Anaphylaxis"

    def test_normalise_dose_entry_preserves_dose_text(self):
        """Should preserve dose description text."""
        raw = {
            "medication": "Adrenaline",
            "indication": "Cardiac Arrest",
            "dose": "1 mg IV every 3-5 minutes",
            "route": "IV",
        }
        result = normalise_dose_entry(raw)
        assert "1 mg" in result["dose"]

    def test_normalise_dose_entry_preserves_route(self):
        """Should preserve administration route."""
        raw = {
            "medication": "Adrenaline",
            "indication": "Cardiac Arrest",
            "dose": "1 mg IV",
            "route": "IO",
        }
        result = normalise_dose_entry(raw)
        assert result["route"] == "IO"

    def test_normalise_dose_entry_defaults_qualifications_to_empty(self):
        """Should default qualifications_required to empty list."""
        raw = {
            "medication": "Adrenaline",
            "indication": "Cardiac Arrest",
            "dose": "1 mg IV",
            "route": "IV",
        }
        result = normalise_dose_entry(raw)
        assert result.get("qualifications_required") == []

    def test_normalise_dose_entry_handles_missing_optional_fields(self):
        """Should handle missing optional fields gracefully."""
        raw = {
            "medication": "Adrenaline",
            "dose": "1 mg IV",
        }
        result = normalise_dose_entry(raw)
        assert result["medication"] == "Adrenaline"
        assert "1 mg" in result["dose"]


class TestATDoseFormats:
    """Test AT-specific dose format patterns."""

    def test_extracts_adult_bolus_format(self):
        """Should extract AT adult bolus format."""
        text = "Adult bolus dosing (1:10,000): 1 mg IV every 3-5 minutes."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Cardiac Arrest")
        assert len(entries) >= 1
        assert "bolus" in entries[0]["dose"].lower() or "1 mg" in entries[0]["dose"]

    def test_extracts_adult_infusion_format(self):
        """Should extract AT adult infusion format."""
        text = "Adult infusion (hard max 100 microg/min, 1:100,000 dilution)."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Anaphylaxis")
        assert len(entries) >= 1

    def test_extracts_paediatric_infusion_format(self):
        """Should extract AT paediatric infusion format."""
        text = "Paediatric infusion (hard max 1 microg/kg/min, double-dilution steps)."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Paediatric")
        assert len(entries) >= 1

    def test_extracts_paediatric_bolus_format(self):
        """Should extract AT paediatric bolus format."""
        text = "Paediatric bolus dosing (dilution steps)."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Paediatric")
        assert len(entries) >= 1

    def test_extracts_double_dilution_steps(self):
        """Should extract double-dilution step instructions."""
        text = "Double-dilution steps: first dilute 1:10,000, then 1:100,000."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Infusion")
        assert len(entries) >= 1


class TestRegexPatterns:
    """Test regex pattern matching for dose components."""

    def test_extracts_mg_dose_quantities(self):
        """Should extract mg quantities."""
        text = "Dose: 1 mg IV. Also 10 mg IM."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Test")
        assert len(entries) >= 1
        assert any("1 mg" in e["dose"] or "10 mg" in e["dose"] for e in entries)

    def test_extracts_mcg_dose_quantities(self):
        """Should extract mcg/microg quantities."""
        text = "Infusion: 2-10 microg/min."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Test")
        assert len(entries) >= 1
        assert "microg" in entries[0]["dose"] or "mcg" in entries[0]["dose"]

    def test_extracts_weight_based_dosing(self):
        """Should extract mg/kg and mcg/kg quantities."""
        text = "Paediatric: 0.01 mg/kg IV (max 1 mg). Infusion: 1 microg/kg/min."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Paediatric")
        assert len(entries) >= 1
        assert any("mg/kg" in e["dose"] or "microg/kg" in e["dose"] for e in entries)

    def test_extracts_iv_route(self):
        """Should identify IV route."""
        text = "1 mg IV every 3-5 minutes."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Test")
        assert len(entries) >= 1
        assert entries[0]["route"] == "IV"

    def test_extracts_io_route(self):
        """Should identify IO route."""
        text = "1 mg IO every 3-5 minutes."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Test")
        assert len(entries) >= 1
        assert entries[0]["route"] == "IO"

    def test_extracts_im_route(self):
        """Should identify IM route."""
        text = "0.5 mg IM."
        entries = parse_dose_text(text, medicine="Adrenaline", indication="Test")
        assert len(entries) >= 1
        assert entries[0]["route"] == "IM"

    def test_extracts_inhaled_route(self):
        """Should identify inhaled route."""
        text = "Salbutamol 2.5 mg inhaled via nebuliser."
        entries = parse_dose_text(text, medicine="Salbutamol", indication="Asthma")
        assert len(entries) >= 1
        assert entries[0]["route"] == "inhaled"

    def test_extracts_topical_route(self):
        """Should identify topical route."""
        text = "Apply 2 g topical to affected area."
        entries = parse_dose_text(text, medicine="Lignocaine", indication="Local anaesthetic")
        assert len(entries) >= 1
        assert entries[0]["route"] == "topical"
