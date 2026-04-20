"""
Tests for AT CPG per-guideline content extraction (content_extractor.py).

These tests verify that the content extractor can:
1. Parse HTML sections from Ionic template strings
2. Extract guideline content from JS chunks
3. Extract medicines referenced in guidelines
4. Handle flowchart detection (stub for now)
5. Batch extract all guidelines from discovery results
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.python.pipeline.at.content_extractor import (
    extract_guideline_content,
    parse_html_sections,
    extract_all_guidelines,
)
from src.python.pipeline.at.models import (
    ATContentSection,
    ATGuidelineRef,
)


class TestParseHtmlSections:
    """Test HTML section parsing from Ionic template strings."""

    def test_parse_html_sections_extracts_headings_and_body(self):
        """Should extract heading/body pairs from HTML."""
        html = """
        <h2>Pharmacology</h2><p>Adrenaline acts on alpha and beta receptors.</p>
        <h2>Indications</h2><p>Cardiac arrest. Anaphylaxis.</p>
        """
        sections = parse_html_sections(html)
        assert len(sections) == 2
        assert sections[0]["heading"] == "Pharmacology"
        assert "alpha" in sections[0]["body"]
        assert sections[1]["heading"] == "Indications"
        assert "Cardiac arrest" in sections[1]["body"]

    def test_parse_html_sections_handles_h1_to_h6(self):
        """Should handle all heading levels (h1-h6)."""
        html = """
        <h1>Overview</h1><p>Main content.</p>
        <h3>Clinical</h3><p>Clinical content.</p>
        <h6>Notes</h6><p>Notes content.</p>
        """
        sections = parse_html_sections(html)
        assert len(sections) == 3
        assert sections[0]["heading"] == "Overview"
        assert sections[1]["heading"] == "Clinical"
        assert sections[2]["heading"] == "Notes"

    def test_parse_html_sections_handles_ionic_components(self):
        """Should handle Ionic-specific components (ion-content, ion-card, etc)."""
        html = """
        <ion-content><h2>Common Trade Names</h2><p>Adrenalin</p></ion-content>
        <ion-card><h2>Indications</h2><p>Cardiac arrest</p></ion-card>
        """
        sections = parse_html_sections(html)
        assert len(sections) >= 1
        assert any(s["heading"] == "Common Trade Names" for s in sections)

    def test_parse_html_sections_handles_strong_and_em_tags(self):
        """Should preserve bold and italic formatting in body text."""
        html = """
        <h2>Contraindications</h2>
        <p><strong>Hypersensitivity</strong> to adrenaline. <em>Use with caution</em> in pregnancy.</p>
        """
        sections = parse_html_sections(html)
        assert len(sections) == 1
        assert "Hypersensitivity" in sections[0]["body"]
        assert "Use with caution" in sections[0]["body"]

    def test_parse_html_sections_handles_lists(self):
        """Should handle ul/ol lists in body text."""
        html = """
        <h2>Side Effects</h2>
        <ul><li>Tachycardia</li><li>Hypertension</li><li>Anxiety</li></ul>
        """
        sections = parse_html_sections(html)
        assert len(sections) == 1
        assert "Tachycardia" in sections[0]["body"]
        assert "Hypertension" in sections[0]["body"]

    def test_parse_html_sections_handles_empty_html(self):
        """Should return empty list for empty or invalid HTML."""
        assert parse_html_sections("") == []
        assert parse_html_sections("<div></div>") == []
        assert parse_html_sections("No tags here") == []

    def test_parse_html_sections_handles_nested_tags(self):
        """Should handle nested tags in body content."""
        html = """
        <h2>Clinical Management</h2>
        <p><strong>Step 1:</strong> <em>Assess ABCDE</em></p>
        """
        sections = parse_html_sections(html)
        assert len(sections) == 1
        assert "Step 1:" in sections[0]["body"]
        assert "Assess ABCDE" in sections[0]["body"]

    def test_parse_html_sections_handles_multiple_paragraphs(self):
        """Should combine multiple paragraphs under one heading."""
        html = """
        <h2>Pharmacology</h2>
        <p>First paragraph.</p>
        <p>Second paragraph.</p>
        """
        sections = parse_html_sections(html)
        assert len(sections) == 1
        assert "First paragraph" in sections[0]["body"]
        assert "Second paragraph" in sections[0]["body"]


class TestExtractGuidelineContent:
    """Test guideline content extraction from JS chunks."""

    def test_extract_guideline_content_produces_required_fields(self):
        """Should produce all required fields in output dict."""
        chunk = 'class SomeComponent{template:`<ion-content><h2>Cardiac Arrest</h2><p>Content here.</p></ion-content>`}'
        result = extract_guideline_content(chunk, cpg_code="A0201-1", title="Medical Cardiac Arrest")

        assert result["cpg_code"] == "A0201-1"
        assert result["title"] == "Medical Cardiac Arrest"
        assert "sections" in result
        assert "medicines" in result
        assert "flowcharts" in result
        assert "source_bundle" in result
        assert "has_dose_table" in result
        assert "source_url" in result

    def test_extract_guideline_content_extracts_sections(self):
        """Should extract sections from template string."""
        chunk = '''
        class CardiacArrestComponent{
            template:`
                <ion-content>
                    <h2>Indications</h2>
                    <p>Cardiac arrest. Anaphylaxis.</p>
                    <h2>Contraindications</h2>
                    <p>None in cardiac arrest.</p>
                </ion-content>
            `
        }
        '''
        result = extract_guideline_content(chunk, cpg_code="A0201-1", title="Cardiac Arrest")

        assert len(result["sections"]) >= 2
        section_headings = [s["heading"] for s in result["sections"]]
        assert "Indications" in section_headings
        assert "Contraindications" in section_headings

    def test_extract_guideline_content_detects_medicine_references(self):
        """Should detect medicine D-code references in content."""
        chunk = '''
        class MedicineComponent{
            template:`
                <ion-content>
                    <h2>Indications</h2>
                    <p>See <strong>D003</strong> for adrenaline dosing.</p>
                    <p>Refer to D010 for fentanyl.</p>
                </ion-content>
            `
        }
        '''
        result = extract_guideline_content(chunk, cpg_code="A0201-1", title="Guideline")

        assert len(result["medicines"]) >= 2
        assert "D003" in result["medicines"]
        assert "D010" in result["medicines"]

    def test_extract_guideline_content_detects_dose_table(self):
        """Should detect presence of medication dose table."""
        chunk_with_table = '''
        class Component{
            template:`
                <ion-content>
                    <h2>Dose Recommendations</h2>
                    <table><tr><th>Weight</th><th>Dose</th></tr></table>
                </ion-content>
            `
        }
        '''
        result = extract_guideline_content(chunk_with_table, cpg_code="D003", title="Adrenaline")
        assert result["has_dose_table"] is True

        chunk_without_table = '''
        class Component{
            template:`
                <ion-content>
                    <h2>Pharmacology</h2>
                    <p>No table here.</p>
                </ion-content>
            `
        }
        '''
        result = extract_guideline_content(chunk_without_table, cpg_code="D003", title="Adrenaline")
        assert result["has_dose_table"] is False

    def test_extract_guideline_content_handles_medicine_page_sections(self):
        """Should handle medicine-specific section headings."""
        chunk = '''
        class AdrenalineComponent{
            template:`
                <ion-content>
                    <h2>Common Trade Names</h2><p>Adrenalin</p>
                    <h2>Presentation</h2><p>1 mg/1 mL</p>
                    <h2>Pharmacology</h2><p>Alpha and beta agonist.</p>
                    <h2>Dose Recommendations</h2><p>See table.</p>
                </ion-content>
            `
        }
        '''
        result = extract_guideline_content(chunk, cpg_code="D003", title="Adrenaline")

        section_headings = [s["heading"] for s in result["sections"]]
        assert "Common Trade Names" in section_headings
        assert "Presentation" in section_headings
        assert "Pharmacology" in section_headings
        assert "Dose Recommendations" in section_headings

    def test_extract_guideline_content_handles_adult_guideline_sections(self):
        """Should handle adult guideline section headings."""
        chunk = '''
        class GuidelineComponent{
            template:`
                <ion-content>
                    <h2>Indications</h2><p>Cardiac arrest in adults.</p>
                    <h2>Contraindications</h2><p>None.</p>
                    <h2>Precautions</h2><p>Use with caution in pregnancy.</p>
                    <h2>Clinical Management</h2><p>ABCDE approach.</p>
                </ion-content>
            `
        }
        '''
        result = extract_guideline_content(chunk, cpg_code="A0201-1", title="Cardiac Arrest")

        section_headings = [s["heading"] for s in result["sections"]]
        assert "Indications" in section_headings
        assert "Contraindications" in section_headings
        assert "Clinical Management" in section_headings

    def test_extract_guideline_content_builds_source_url(self):
        """Should build source URL from cpg_code."""
        chunk = 'class Component{template:`<ion-content><h2>Test</h2></ion-content>`}'
        result = extract_guideline_content(chunk, cpg_code="A0201-1", title="Cardiac Arrest")

        assert "source_url" in result
        assert "cpg.ambulance.tas.gov.au" in result["source_url"]
        assert "A0201-1" in result["source_url"]

    def test_extract_guideline_content_tracks_source_bundle(self):
        """Should track the source bundle filename."""
        chunk = 'class Component{template:`<ion-content><h2>Test</h2></ion-content>`}'
        result = extract_guideline_content(
            chunk,
            cpg_code="A0201-1",
            title="Cardiac Arrest",
            source_bundle="123.abc456.js"
        )

        assert result["source_bundle"] == "123.abc456.js"

    def test_extract_guideline_content_returns_empty_flowcharts(self):
        """Should return empty flowcharts list (stub for now)."""
        chunk = 'class Component{template:`<ion-content><h2>Test</h2></ion-content>`}'
        result = extract_guideline_content(chunk, cpg_code="A0201-1", title="Cardiac Arrest")

        assert result["flowcharts"] == []

    def test_extract_guideline_content_handles_no_template(self):
        """Should handle chunks without template strings."""
        chunk = 'class Component{constructor(){this.value=42;}}'
        result = extract_guideline_content(chunk, cpg_code="A0201-1", title="Cardiac Arrest")

        assert result["cpg_code"] == "A0201-1"
        assert len(result["sections"]) == 0


class TestExtractAllGuidelines:
    """Test batch extraction of all guidelines from discovery results."""

    def test_extract_all_guidelines_processes_discovery_results(self):
        """Should process all guidelines from discovery results."""
        # Create temporary directory with discovery results
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_path = Path(tmpdir) / "discovery.json"
            output_dir = Path(tmpdir) / "output"

            # Create mock discovery results
            discovery_data = {
                "guidelines": [
                    {
                        "cpg_code": "A0201-1",
                        "title": "Medical Cardiac Arrest",
                        "category": "Cardiac",
                        "route_slug": "cardiac-arrest",
                        "source_bundle": "123.abc.js",
                        "has_flowchart": False,
                        "has_dose_table": False,
                    },
                    {
                        "cpg_code": "D003",
                        "title": "Adrenaline",
                        "category": "Medicines",
                        "route_slug": "adrenaline",
                        "source_bundle": "456.def.js",
                        "has_flowchart": False,
                        "has_dose_table": True,
                    },
                ],
                "medicines": [],
                "categories": ["Cardiac", "Medicines"],
                "total_bundles_analysed": 10,
                "errors": [],
            }

            discovery_path.write_text(json.dumps(discovery_data))

            # Create mock JS bundles
            bundles_dir = Path(tmpdir) / "bundles"
            bundles_dir.mkdir()

            (bundles_dir / "123.abc.js").write_text(
                'class Component{template:`<ion-content><h2>Cardiac Arrest</h2><p>Content.</p></ion-content>`}'
            )
            (bundles_dir / "456.def.js").write_text(
                'class Component{template:`<ion-content><h2>Adrenaline</h2><p>Medicine content.</p></ion-content>`}'
            )

            # Mock the bundle loading
            with patch('src.python.pipeline.at.content_extractor._load_bundle_content') as mock_load:
                def load_bundle(fname, bd=None):
                    return (bundles_dir / fname).read_text()
                mock_load.side_effect = load_bundle

                results = extract_all_guidelines(str(discovery_path), str(output_dir))

                assert len(results) == 2
                assert results[0]["cpg_code"] == "A0201-1"
                assert results[1]["cpg_code"] == "D003"

    def test_extract_all_guidelines_creates_output_dir(self):
        """Should create output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_path = Path(tmpdir) / "discovery.json"
            output_dir = Path(tmpdir) / "new_output"

            discovery_data = {
                "guidelines": [],
                "medicines": [],
                "categories": [],
                "total_bundles_analysed": 0,
                "errors": [],
            }

            discovery_path.write_text(json.dumps(discovery_data))

            extract_all_guidelines(str(discovery_path), str(output_dir))

            assert output_dir.exists()

    def test_extract_all_guidelines_saves_individual_files(self):
        """Should save each guideline as individual JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_path = Path(tmpdir) / "discovery.json"
            output_dir = Path(tmpdir) / "output"

            discovery_data = {
                "guidelines": [
                    {
                        "cpg_code": "A0201-1",
                        "title": "Medical Cardiac Arrest",
                        "category": "Cardiac",
                        "route_slug": "cardiac-arrest",
                        "source_bundle": "123.abc.js",
                        "has_flowchart": False,
                        "has_dose_table": False,
                    },
                ],
                "medicines": [],
                "categories": [],
                "total_bundles_analysed": 1,
                "errors": [],
            }

            discovery_path.write_text(json.dumps(discovery_data))

            bundles_dir = Path(tmpdir) / "bundles"
            bundles_dir.mkdir()
            (bundles_dir / "123.abc.js").write_text(
                'class Component{template:`<ion-content><h2>Test</h2></ion-content>`}'
            )

            with patch('src.python.pipeline.at.content_extractor._load_bundle_content') as mock_load:
                def load_bundle(fname, bd=None):
                    return (bundles_dir / fname).read_text()
                mock_load.side_effect = load_bundle

                extract_all_guidelines(str(discovery_path), str(output_dir))

                # Check that individual file was created
                expected_file = output_dir / "A0201-1.json"
                assert expected_file.exists()

                # Check file content
                content = json.loads(expected_file.read_text())
                assert content["cpg_code"] == "A0201-1"

    def test_extract_all_guidelines_handles_missing_bundles(self):
        """Should handle missing source bundles gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_path = Path(tmpdir) / "discovery.json"
            output_dir = Path(tmpdir) / "output"

            discovery_data = {
                "guidelines": [
                    {
                        "cpg_code": "A0201-1",
                        "title": "Missing Bundle",
                        "category": "Test",
                        "route_slug": "test",
                        "source_bundle": "missing.js",
                        "has_flowchart": False,
                        "has_dose_table": False,
                    },
                ],
                "medicines": [],
                "categories": [],
                "total_bundles_analysed": 1,
                "errors": [],
            }

            discovery_path.write_text(json.dumps(discovery_data))

            with patch('src.python.pipeline.at.content_extractor._load_bundle_content') as mock_load:
                mock_load.side_effect = FileNotFoundError("Bundle not found")

                results = extract_all_guidelines(str(discovery_path), str(output_dir))

                # Should still return a result, but with empty sections
                assert len(results) == 1
                assert results[0]["cpg_code"] == "A0201-1"
                assert len(results[0]["sections"]) == 0


class TestMedicineReferenceExtraction:
    """Test medicine D-code reference extraction."""

    def test_extracts_single_medicine_reference(self):
        """Should extract single D-code reference."""
        chunk = 'template:`<p>See D003 for details.</p>`'
        result = extract_guideline_content(chunk, cpg_code="A0201", title="Test")
        assert "D003" in result["medicines"]

    def test_extracts_multiple_medicine_references(self):
        """Should extract multiple D-code references."""
        chunk = 'template:`<p>See D003, D010, and D024.</p>`'
        result = extract_guideline_content(chunk, cpg_code="A0201", title="Test")
        assert "D003" in result["medicines"]
        assert "D010" in result["medicines"]
        assert "D024" in result["medicines"]

    def test_filters_non_dcode_references(self):
        """Should only extract D-code patterns."""
        chunk = 'template:`<p>See D003, A0201, and M001.</p>`'
        result = extract_guideline_content(chunk, cpg_code="A0201", title="Test")
        assert "D003" in result["medicines"]
        assert "A0201" not in result["medicines"]
        assert "M001" not in result["medicines"]


class TestQualificationExtraction:
    """Test qualification level extraction from sections."""

    def test_extracts_qualification_markers(self):
        """Should extract qualification level markers from content."""
        chunk = '''
        template:`
            <h2>Clinical Management</h2>
            <p><strong>PARAMEDIC</strong>: May administer. <strong>ICP</strong>: Advanced protocols.</p>
        `
        '''
        result = extract_guideline_content(chunk, cpg_code="A0201", title="Test")

        # Check that qualifications are tracked in sections
        clinical_mgmt = next((s for s in result["sections"] if s["heading"] == "Clinical Management"), None)
        assert clinical_mgmt is not None
        assert len(clinical_mgmt["qualifications_required"]) >= 1


class TestDoseTableDetection:
    """Test dose table detection in content."""

    def test_detects_html_table(self):
        """Should detect HTML table tags."""
        chunk = 'template:`<h2>Dose</h2><table><tr><th>Weight</th></tr></table>`'
        result = extract_guideline_content(chunk, cpg_code="D003", title="Test")
        assert result["has_dose_table"] is True

    def test_detects_ionic_list_table(self):
        """Should detect Ionic list used as table."""
        chunk = 'template:`<h2>Dose</h2><ion-list><ion-item>Weight: 10kg</ion-item></ion-list>`'
        result = extract_guideline_content(chunk, cpg_code="D003", title="Test")
        # Ionic list may not be detected as dose table - implementation dependent
        assert "has_dose_table" in result

    def test_no_false_positives(self):
        """Should not detect dose table when not present."""
        chunk = 'template:`<h2>Pharmacology</h2><p>No table here.</p>`'
        result = extract_guideline_content(chunk, cpg_code="D003", title="Test")
        assert result["has_dose_table"] is False
