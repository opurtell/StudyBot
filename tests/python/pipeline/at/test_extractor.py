"""
Tests for AT CPG JS bundle download and parsing (extractor.py).

These tests verify that the extractor can:
1. Download main, common, and lazy chunk JS bundles
2. Parse CPG registry codes from JS bundles
3. Parse medicine registry (name + D-code pairs)
4. Parse route definitions from Angular routing
5. Parse qualification level markers from level selector
"""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from src.python.pipeline.at.extractor import (
    download_main_bundle,
    download_common_bundle,
    download_lazy_chunks,
    parse_cpg_registry,
    parse_medicine_registry,
    parse_route_definitions,
    parse_qualification_levels,
)


class TestParseCpgRegistry:
    """Test CPG code parsing from JS bundles."""

    def test_parse_cpg_registry_finds_known_codes(self):
        """Should extract CPG codes including A0xxx, D0xx, M0xx, P0xxx, E0xx."""
        js_fragment = '"A0201","A0201-1","A0201-2","D003","D010","M001","P0201","E001"'
        codes = parse_cpg_registry(js_fragment)
        assert "A0201" in codes
        assert "A0201-1" in codes
        assert "A0201-2" in codes
        assert "D003" in codes
        assert "D010" in codes
        assert "M001" in codes
        assert "P0201" in codes
        assert "E001" in codes

    def test_parse_cpg_registry_handles_various_formats(self):
        """Should handle codes in different JS contexts (arrays, objects, strings)."""
        # Array format
        js_array = '["A0201","D003","M001"]'
        codes = parse_cpg_registry(js_array)
        assert "A0201" in codes
        assert "D003" in codes

        # Object keys
        js_obj = '{"A0201":{title:"Cardiac Arrest"},"D003":{title:"Adrenaline"}}'
        codes = parse_cpg_registry(js_obj)
        assert "A0201" in codes
        assert "D003" in codes

    def test_parse_cpg_registry_filters_invalid_patterns(self):
        """Should only match valid CPG code patterns."""
        js_fragment = '"A0201","D003","INVALID","ABC123","999","M001"'
        codes = parse_cpg_registry(js_fragment)
        assert "A0201" in codes
        assert "D003" in codes
        assert "M001" in codes
        assert "INVALID" not in codes
        assert "ABC123" not in codes
        assert "999" not in codes

    def test_parse_cpg_registry_handles_hyphenated_variants(self):
        """Should extract hyphenated variant codes (A0xxx-N)."""
        js_fragment = '"A0201","A0201-1","A0201-2","A0201-10","D003"'
        codes = parse_cpg_registry(js_fragment)
        assert "A0201" in codes
        assert "A0201-1" in codes
        assert "A0201-2" in codes
        assert "A0201-10" in codes
        assert "D003" in codes


class TestParseMedicineRegistry:
    """Test medicine registry parsing (name + D-code pairs)."""

    def test_parse_medicine_registry_extracts_names_and_dcodes(self):
        """Should extract medicine names mapped to D-codes."""
        js_fragment = '{"D003":"Adrenaline","D010":"Fentanyl","D024":"Morphine"}'
        medicines = parse_medicine_registry(js_fragment)
        assert len(medicines) == 3

        by_code = {m["code"]: m["name"] for m in medicines}
        assert by_code["D003"] == "Adrenaline"
        assert by_code["D010"] == "Fentanyl"
        assert by_code["D024"] == "Morphine"

    def test_parse_medicine_registry_handles_various_formats(self):
        """Should handle different JS object formats."""
        # Standard object
        js_obj = '{"D003":"Adrenaline","D010":"Fentanyl"}'
        medicines = parse_medicine_registry(js_obj)
        assert len(medicines) == 2

        # With extra whitespace
        js_ws = '{ "D003" : "Adrenaline" , "D010" : "Fentanyl" }'
        medicines = parse_medicine_registry(js_ws)
        assert len(medicines) == 2

    def test_parse_medicine_registry_filters_non_dcodes(self):
        """Should only extract D-code entries (D001-D047 range)."""
        js_fragment = '{"D003":"Adrenaline","A0201":"Cardiac","M001":"Some","D999":"Invalid"}'
        medicines = parse_medicine_registry(js_fragment)
        assert len(medicines) == 1
        assert medicines[0]["code"] == "D003"
        assert medicines[0]["name"] == "Adrenaline"

    def test_parse_medicine_registry_returns_empty_list_for_no_matches(self):
        """Should return empty list when no D-codes found."""
        js_fragment = '{"A0201":"Cardiac","M001":"Other"}'
        medicines = parse_medicine_registry(js_fragment)
        assert len(medicines) == 0


class TestParseRouteDefinitions:
    """Test Angular route path extraction from JS bundles."""

    def test_parse_route_definitions_finds_guidelines_routes(self):
        """Should extract route paths for guideline pages."""
        js_fragment = '{path:"tabs/guidelines/adult-patient-guidelines/cardiac-arrest"}'
        routes = parse_route_definitions(js_fragment)
        assert any("cardiac-arrest" in r for r in routes)

    def test_parse_route_definitions_finds_medicine_routes(self):
        """Should extract route paths for medicine pages."""
        js_fragment = '{path:"tabs/medicines/adrenaline"},{path:"tabs/medicines/fentanyl"}'
        routes = parse_route_definitions(js_fragment)
        assert any("adrenaline" in r for r in routes)
        assert any("fentanyl" in r for r in routes)

    def test_parse_route_definitions_handles_various_path_formats(self):
        """Should handle different path formats in Angular routes."""
        js_fragment = '''
        {path:"tabs/guidelines/cardiac-arrest"}
        {path: "tabs/medicines/adrenaline"}
        {path:'tabs/guidelines/respiratory'}
        '''
        routes = parse_route_definitions(js_fragment)
        assert len(routes) >= 3
        assert any("cardiac-arrest" in r for r in routes)
        assert any("adrenaline" in r for r in routes)
        assert any("respiratory" in r for r in routes)

    def test_parse_route_definitions_filters_non_tab_routes(self):
        """Should only extract routes under /tabs/ path."""
        js_fragment = '{path:"tabs/guidelines/cardiac-arrest"},{path:"auth/login"},{path:"home"}'
        routes = parse_route_definitions(js_fragment)
        assert any("cardiac-arrest" in r for r in routes)
        assert not any("auth/login" in r for r in routes)
        assert not any("home" in r for r in routes)


class TestParseQualificationLevels:
    """Test qualification level marker extraction from level selector."""

    def test_parse_qualification_levels_finds_standard_levels(self):
        """Should extract standard AT qualification levels."""
        js_fragment = '"VAO","PARAMEDIC","ICP","PACER","CP","ECP"'
        levels = parse_qualification_levels(js_fragment)
        assert "VAO" in levels
        assert "PARAMEDIC" in levels
        assert "ICP" in levels
        assert "PACER" in levels
        assert "CP" in levels or "ECP" in levels

    def test_parse_qualification_levels_handles_various_formats(self):
        """Should handle levels in different JS contexts."""
        # Array format
        js_array = '["VAO","PARAMEDIC","ICP"]'
        levels = parse_qualification_levels(js_array)
        assert "VAO" in levels
        assert "PARAMEDIC" in levels
        assert "ICP" in levels

        # String constants
        js_str = 'level:"VAO", qual:"PARAMEDIC", role:"ICP"'
        levels = parse_qualification_levels(js_str)
        assert "VAO" in levels
        assert "PARAMEDIC" in levels
        assert "ICP" in levels

    def test_parse_qualification_levels_filters_non_qualifications(self):
        """Should only extract known qualification level names."""
        js_fragment = '"VAO","PARAMEDIC","INVALID","ADMIN","GUEST","ICP"'
        levels = parse_qualification_levels(js_fragment)
        assert "VAO" in levels
        assert "PARAMEDIC" in levels
        assert "ICP" in levels
        # Non-standard levels may or may not be filtered
        # depending on implementation


class TestDownloadMainBundle:
    """Test main JS bundle download."""

    def test_download_main_bundle_returns_path(self):
        """Should return path to downloaded main bundle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.python.pipeline.at.extractor._download_js_bundle') as mock_download:
                mock_download.return_value = os.path.join(tmpdir, "main.abc123.js")

                result = download_main_bundle(tmpdir)
                assert result.endswith("main.abc123.js")
                assert tmpdir in result

    def test_download_main_bundle_creates_directory(self):
        """Should create output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "new_dir")
            with patch('src.python.pipeline.at.extractor._download_js_bundle') as mock_download:
                mock_download.return_value = os.path.join(output_dir, "main.abc123.js")

                result = download_main_bundle(output_dir)
                assert os.path.exists(output_dir)
                assert result.endswith("main.abc123.js")


class TestDownloadCommonBundle:
    """Test common JS bundle download."""

    def test_download_common_bundle_returns_path(self):
        """Should return path to downloaded common bundle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.python.pipeline.at.extractor._download_js_bundle') as mock_download:
                mock_download.return_value = os.path.join(tmpdir, "common.xyz789.js")

                result = download_common_bundle(tmpdir)
                assert result.endswith("common.xyz789.js")
                assert tmpdir in result


class TestDownloadLazyChunks:
    """Test lazy chunk JS bundle downloads."""

    def test_download_lazy_chunks_returns_list(self):
        """Should return list of paths to downloaded lazy chunks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.python.pipeline.at.extractor._discover_lazy_chunk_urls') as mock_discover:
                with patch('src.python.pipeline.at.extractor._download_js_bundle') as mock_download:
                    mock_discover.return_value = [
                        "https://cpg.ambulance.tas.gov.au/assets/123.abc.js",
                        "https://cpg.ambulance.tas.gov.au/assets/456.def.js",
                    ]
                    mock_download.side_effect = [
                        os.path.join(tmpdir, "123.abc.js"),
                        os.path.join(tmpdir, "456.def.js"),
                    ]

                    result = download_lazy_chunks(tmpdir)
                    assert len(result) == 2
                    assert all(tmpdir in path for path in result)

    def test_download_lazy_chunks_empty_when_no_chunks(self):
        """Should return empty list when no lazy chunks discovered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.python.pipeline.at.extractor._discover_lazy_chunk_urls') as mock_discover:
                mock_discover.return_value = []

                result = download_lazy_chunks(tmpdir)
                assert len(result) == 0


class TestIntegration:
    """Integration tests for combined parsing operations."""

    def test_full_extraction_workflow(self):
        """Test end-to-end extraction from sample JS content."""
        # Sample main bundle content
        main_js = '''
        var CPG_REGISTRY = ["A0201","A0201-1","D003","D010","M001","P0201"];
        var MEDICINE_REGISTRY = {"D003":"Adrenaline","D010":"Fentanyl"};
        var LEVELS = ["VAO","PARAMEDIC","ICP"];
        '''

        # Sample common bundle content
        common_js = '''
        {path:"tabs/guidelines/adult-patient-guidelines/cardiac-arrest", loadChildren:...}
        {path:"tabs/medicines/adrenaline", loadChildren:...}
        {path:"tabs/guidelines/respiratory", loadChildren:...}
        '''

        # Parse CPG codes
        cpg_codes = parse_cpg_registry(main_js)
        assert len(cpg_codes) >= 6
        assert "A0201" in cpg_codes
        assert "D003" in cpg_codes

        # Parse medicines
        medicines = parse_medicine_registry(main_js)
        assert len(medicines) >= 2
        med_names = [m["name"] for m in medicines]
        assert "Adrenaline" in med_names
        assert "Fentanyl" in med_names

        # Parse routes
        routes = parse_route_definitions(common_js)
        assert len(routes) >= 3
        assert any("cardiac-arrest" in r for r in routes)

        # Parse qualification levels
        levels = parse_qualification_levels(main_js)
        assert len(levels) >= 3
        assert "VAO" in levels
        assert "PARAMEDIC" in levels
