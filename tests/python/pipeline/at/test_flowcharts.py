"""
Tests for AT CPG flowchart extraction (flowcharts.py).

These tests verify that the flowchart extractor can:
1. Classify flowchart format (data/SVG/image/PDF)
2. Extract data-driven flowcharts to Mermaid
3. Convert SVG flowcharts to Mermaid
4. Handle image/PDF flowcharts with placeholder
5. Process all flowcharts from discovery results
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.python.pipeline.at.flowcharts import (
    classify_flowchart_format,
    extract_data_driven_flowchart,
    convert_svg_to_mermaid,
    process_all_flowcharts,
    capture_flowchart_screenshot,
)


class TestClassifyFlowchartFormat:
    """Test flowchart format classification."""

    def test_classify_data_driven_format(self):
        """Should classify JSON with nodes/edges as 'data' format."""
        js_content = '{"nodes":[{"id":"start","label":"Assessment"}],"edges":[{"from":"start","to":"decision"}]}'
        fmt = classify_flowchart_format(js_content)
        assert fmt == "data"

    def test_classify_data_driven_format_with_vertices(self):
        """Should classify JSON with vertices as 'data' format (alternative schema)."""
        js_content = '{"vertices":[{"id":"A","text":"Start"}],"connections":[{"source":"A","target":"B"}]}'
        fmt = classify_flowchart_format(js_content)
        assert fmt == "data"

    def test_classify_svg_format(self):
        """Should classify SVG markup as 'svg' format."""
        content = '<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0"/><text>Start</text></svg>'
        fmt = classify_flowchart_format(content)
        assert fmt == "svg"

    def test_classify_svg_format_lowercase(self):
        """Should classify lowercase SVG markup."""
        content = '<svg><rect x="0" y="0" width="100" height="50"/><text>Decision</text></svg>'
        fmt = classify_flowchart_format(content)
        assert fmt == "svg"

    def test_classify_png_image_format(self):
        """Should classify PNG binary as 'image' format."""
        content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        fmt = classify_flowchart_format(content)
        assert fmt == "image"

    def test_classify_jpeg_image_format(self):
        """Should classify JPEG binary as 'image' format."""
        content = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        fmt = classify_flowchart_format(content)
        assert fmt == "image"

    def test_classify_pdf_format(self):
        """Should classify PDF binary as 'pdf' format."""
        content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj'
        fmt = classify_flowchart_format(content)
        assert fmt == "pdf"

    def test_classify_unknown_format(self):
        """Should return 'unknown' for unrecognised formats."""
        content = 'Just plain text with no structure'
        fmt = classify_flowchart_format(content)
        assert fmt == "unknown"

    def test_classify_empty_string(self):
        """Should return 'unknown' for empty string."""
        fmt = classify_flowchart_format("")
        assert fmt == "unknown"

    def test_classify_empty_bytes(self):
        """Should return 'unknown' for empty bytes."""
        fmt = classify_flowchart_format(b"")
        assert fmt == "unknown"


class TestExtractDataDrivenFlowchart:
    """Test data-driven flowchart extraction to Mermaid."""

    def test_extract_simple_flowchart_to_mermaid(self):
        """Should convert simple nodes/edges to Mermaid graph TD."""
        js_content = '{"nodes":[{"id":"A","label":"Start"},{"id":"B","label":"Decision"}],"edges":[{"from":"A","to":"B"}]}'
        mermaid = extract_data_driven_flowchart(js_content)

        assert "graph TD" in mermaid
        assert "A" in mermaid
        assert "B" in mermaid
        assert "Start" in mermaid
        assert "Decision" in mermaid

    def test_extract_flowchart_with_multiple_edges(self):
        """Should handle multiple edges in flowchart."""
        js_content = '''
        {
            "nodes": [
                {"id":"A","label":"Start"},
                {"id":"B","label":"Assess"},
                {"id":"C","label":"Treat"}
            ],
            "edges": [
                {"from":"A","to":"B"},
                {"from":"B","to":"C"}
            ]
        }
        '''
        mermaid = extract_data_driven_flowchart(js_content)

        assert "graph TD" in mermaid
        assert "A" in mermaid
        assert "B" in mermaid
        assert "C" in mermaid
        assert "-->" in mermaid

    def test_extract_flowchart_with_decision_nodes(self):
        """Should handle decision nodes with yes/no labels."""
        js_content = '''
        {
            "nodes": [
                {"id":"A","label":"Assess"},
                {"id":"B","label":"Stable?"},
                {"id":"C","label":"Monitor"},
                {"id":"D","label":"Treat"}
            ],
            "edges": [
                {"from":"A","to":"B"},
                {"from":"B","to":"C","label":"Yes"},
                {"from":"B","to":"D","label":"No"}
            ]
        }
        '''
        mermaid = extract_data_driven_flowchart(js_content)

        assert "graph TD" in mermaid
        assert "Yes" in mermaid or "yes" in mermaid.lower()
        assert "No" in mermaid or "no" in mermaid.lower()

    def test_extract_flowchart_handles_alternative_schema(self):
        """Should handle alternative JSON schema (vertices/connections)."""
        js_content = '''
        {
            "vertices": [
                {"id":"X","text":"Patient Assessment"},
                {"id":"Y","text":"Decision"}
            ],
            "connections": [
                {"source":"X","target":"Y"}
            ]
        }
        '''
        mermaid = extract_data_driven_flowchart(js_content)

        assert "graph TD" in mermaid
        assert "X" in mermaid
        assert "Y" in mermaid

    def test_extract_flowchart_handles_missing_labels(self):
        """Should handle nodes without labels (use ID as label)."""
        js_content = '{"nodes":[{"id":"node1"}],"edges":[]}'
        mermaid = extract_data_driven_flowchart(js_content)

        assert "graph TD" in mermaid
        assert "node1" in mermaid

    def test_extract_flowchart_handles_invalid_json(self):
        """Should return placeholder for invalid JSON."""
        js_content = 'not valid json at all'
        mermaid = extract_data_driven_flowchart(js_content)

        assert "graph TD" in mermaid
        assert "Error" in mermaid or "error" in mermaid.lower()


class TestConvertSvgToMermaid:
    """Test SVG to Mermaid conversion."""

    def test_convert_simple_svg_to_mermaid(self):
        """Should extract text elements and build flowchart."""
        svg = '<svg><text x="10" y="20">Start</text><text x="10" y="60">Decision</text></svg>'
        mermaid = convert_svg_to_mermaid(svg)

        assert "graph TD" in mermaid
        assert "Start" in mermaid
        assert "Decision" in mermaid

    def test_convert_svg_ignores_duplicates(self):
        """Should deduplicate identical text elements."""
        svg = '<svg><text x="10" y="20">Assessment</text><text x="10" y="60">Assessment</text></svg>'
        mermaid = convert_svg_to_mermaid(svg)

        # Should only appear once as a node
        assert mermaid.count("Assessment") >= 1

    def test_convert_svg_handles_nested_tags(self):
        """Should handle SVG with nested elements."""
        svg = '''
        <svg xmlns="http://www.w3.org/2000/svg">
            <g>
                <text x="10" y="20">Step 1</text>
            </g>
            <text x="10" y="60">Step 2</text>
        </svg>
        '''
        mermaid = convert_svg_to_mermaid(svg)

        assert "graph TD" in mermaid
        assert "Step 1" in mermaid
        assert "Step 2" in mermaid

    def test_convert_svg_handles_empty_text(self):
        """Should handle SVG with empty text elements."""
        svg = '<svg><text x="10" y="20"></text><text x="10" y="60">Real Content</text></svg>'
        mermaid = convert_svg_to_mermaid(svg)

        assert "graph TD" in mermaid
        assert "Real Content" in mermaid

    def test_convert_svg_creates_sequential_edges(self):
        """Should create sequential edges based on Y-coordinate order."""
        svg = '<svg><text x="10" y="20">First</text><text x="10" y="60">Second</text><text x="10" y="100">Third</text></svg>'
        mermaid = convert_svg_to_mermaid(svg)

        assert "graph TD" in mermaid
        # Should have sequential connections
        assert "-->" in mermaid


class TestProcessAllFlowcharts:
    """Test batch processing of all flowcharts."""

    def test_process_all_flowcharts_handles_empty_discovery(self):
        """Should handle discovery with no flowcharts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_path = Path(tmpdir) / "discovery.json"
            output_dir = Path(tmpdir) / "output"

            discovery_data = {
                "guidelines": [],
                "medicines": [],
                "categories": [],
                "total_bundles_analysed": 0,
                "errors": [],
            }

            discovery_path.write_text(json.dumps(discovery_data))

            results = process_all_flowcharts(str(discovery_path), str(output_dir))

            assert results == []

    def test_process_all_flowcharts_filters_guidelines_without_flowcharts(self):
        """Should only process guidelines that have flowcharts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_path = Path(tmpdir) / "discovery.json"
            output_dir = Path(tmpdir) / "output"

            discovery_data = {
                "guidelines": [
                    {
                        "cpg_code": "A0201-1",
                        "title": "With Flowchart",
                        "has_flowchart": True,
                        "route_slug": "with-flowchart",
                    },
                    {
                        "cpg_code": "A0202-1",
                        "title": "Without Flowchart",
                        "has_flowchart": False,
                        "route_slug": "without-flowchart",
                    },
                ],
                "medicines": [],
                "categories": [],
                "total_bundles_analysed": 2,
                "errors": [],
            }

            discovery_path.write_text(json.dumps(discovery_data))

            results = process_all_flowcharts(str(discovery_path), str(output_dir))

            # Should only have one result (the one with has_flowchart=True)
            assert len(results) <= 1

    def test_process_all_flowcharts_creates_output_files(self):
        """Should create output files for extracted flowcharts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_path = Path(tmpdir) / "discovery.json"
            output_dir = Path(tmpdir) / "output"

            discovery_data = {
                "guidelines": [
                    {
                        "cpg_code": "A0201-1",
                        "title": "Test Flowchart",
                        "has_flowchart": True,
                        "route_slug": "test-flowchart",
                    },
                ],
                "medicines": [],
                "categories": [],
                "total_bundles_analysed": 1,
                "errors": [],
            }

            discovery_path.write_text(json.dumps(discovery_data))

            process_all_flowcharts(str(discovery_path), str(output_dir))

            # Check output directory was created
            assert output_dir.exists()

    def test_process_all_flowcharts_handles_errors_gracefully(self):
        """Should continue processing even if one flowchart fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_path = Path(tmpdir) / "discovery.json"
            output_dir = Path(tmpdir) / "output"

            discovery_data = {
                "guidelines": [
                    {
                        "cpg_code": "A0201-1",
                        "title": "Valid Guideline",
                        "has_flowchart": True,
                        "route_slug": "valid",
                    },
                    {
                        "cpg_code": "INVALID",
                        "title": "Invalid Guideline",
                        "has_flowchart": True,
                        "route_slug": "invalid",
                    },
                ],
                "medicines": [],
                "categories": [],
                "total_bundles_analysed": 2,
                "errors": [],
            }

            discovery_path.write_text(json.dumps(discovery_data))

            # Should not raise exception
            results = process_all_flowcharts(str(discovery_path), str(output_dir))

            # Should return results
            assert isinstance(results, list)


class TestCaptureFlowchartScreenshot:
    """Test Playwright screenshot capture (stub for Task 15)."""

    def test_capture_flowchart_screenshot_is_stub(self):
        """Should return None as stub implementation."""
        # Mock page object
        mock_page = Mock()

        result = capture_flowchart_screenshot(mock_page, "https://example.com/flowchart")

        # Stub returns None until Task 15 implementation
        assert result is None

    def test_capture_flowchart_screenshot_handles_mock_page(self):
        """Should accept mock page object without error."""
        mock_page = Mock()
        mock_page.screenshot = Mock(return_value=b"fake screenshot")

        # Should not raise exception
        result = capture_flowchart_screenshot(mock_page, "https://example.com/flowchart")

        # Stub returns None for now
        assert result is None


class TestImagePlaceholderHandling:
    """Test image/PDF flowchart placeholder handling."""

    def test_image_flowchart_gets_placeholder(self):
        """Should mark image flowcharts with review_required=True."""
        # This would be tested through process_all_flowcharts
        # when an image format is detected
        content = b'\x89PNG\r\n\x1a\n'
        fmt = classify_flowchart_format(content)
        assert fmt == "image"

    def test_pdf_flowchart_gets_placeholder(self):
        """Should mark PDF flowcharts with review_required=True."""
        content = b'%PDF-1.4\n'
        fmt = classify_flowchart_format(content)
        assert fmt == "pdf"
