"""
Flowchart Extractor for AT CPG Pipeline

Extracts flowcharts and algorithm diagrams from AT CPG content with support
for multiple source formats:
- Data-driven: JSON with nodes/edges structure
- SVG: Vector graphics with text elements
- Image: Raster images (PNG/JPG) requiring vision LLM
- PDF: PDF documents requiring vision LLM

This module handles:
- Format classification via magic byte detection
- Deterministic Mermaid conversion for data/SVG formats
- Placeholder generation for image/PDF formats (vision LLM in Task 15)
- Batch processing of all flowcharts from discovery results
"""

import json
import logging
import os
import re
from typing import List, Dict, Any, Optional, Literal
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import ATFlowchart, ATGuidelineRef

logger = logging.getLogger(__name__)

# AT CPG site base URL
AT_BASE_URL = "https://cpg.ambulance.tas.gov.au"

# Magic byte signatures for binary format detection
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
JPEG_MAGIC = b'\xff\xd8\xff'
PDF_MAGIC = b'%PDF-'

# Mermaid graph direction
GRAPH_DIRECTION = "TD"  # Top-Down


def classify_flowchart_format(content: str | bytes) -> Literal["data", "svg", "image", "pdf", "unknown"]:
    """Determine the format of flowchart content.

    Args:
        content: Flowchart content (string for JSON/SVG, bytes for binary)

    Returns:
        Format classification: "data" | "svg" | "image" | "pdf" | "unknown"
    """
    # Check for binary formats first
    if isinstance(content, bytes):
        # Check for PNG
        if content.startswith(PNG_MAGIC):
            return "image"
        # Check for JPEG
        if content.startswith(JPEG_MAGIC):
            return "image"
        # Check for PDF
        if content.startswith(PDF_MAGIC):
            return "pdf"
        # Unknown binary format
        return "unknown"

    # String content - check for JSON or SVG
    if isinstance(content, str):
        content_stripped = content.strip()

        # Check for SVG
        if content_stripped.lower().startswith('<svg'):
            return "svg"

        # Check for data-driven JSON (nodes/edges or vertices/connections)
        try:
            data = json.loads(content_stripped)
            # Check for nodes/edges schema
            if "nodes" in data or "edges" in data:
                return "data"
            # Check for alternative vertices/connections schema
            if "vertices" in data or "connections" in data:
                return "data"
        except (json.JSONDecodeError, TypeError):
            pass

    return "unknown"


def extract_data_driven_flowchart(js_content: str) -> str:
    """Convert data-driven flowchart JSON to Mermaid syntax.

    Performs deterministic transformation of JSON nodes/edges to Mermaid
    graph TD syntax. No LLM required.

    Args:
        js_content: JSON string with nodes/edges or vertices/connections

    Returns:
        Mermaid.js syntax string
    """
    try:
        data = json.loads(js_content)
    except (json.JSONDecodeError, TypeError):
        # Return error placeholder
        return f"graph TD\n    Error[\"Invalid flowchart JSON\"]\n"

    mermaid_lines = [f"graph {GRAPH_DIRECTION}"]

    # Support multiple schema variations
    nodes = data.get("nodes", []) or data.get("vertices", [])
    edges = data.get("edges", []) or data.get("connections", [])

    # Build node lookup for labels
    node_labels = {}
    for node in nodes:
        node_id = node.get("id") or node.get("name", "")
        # Try multiple label field names
        label = (
            node.get("label") or
            node.get("text") or
            node.get("title") or
            node.get("name") or
            node_id
        )
        if node_id:
            # Sanitise label for Mermaid
            label_sanitised = label.replace('"', "'")
            node_labels[node_id] = label_sanitised

    # Add nodes to Mermaid
    for node_id, label in node_labels.items():
        # Use ID if label is empty
        display_label = label if label else node_id
        # Escape special characters
        display_label = display_label.replace('"', "'")
        mermaid_lines.append(f'    {node_id}["{display_label}"]')

    # Add edges to Mermaid
    for edge in edges:
        # Support multiple edge schemas
        from_node = edge.get("from") or edge.get("source") or ""
        to_node = edge.get("to") or edge.get("target") or ""

        if from_node and to_node:
            edge_label = edge.get("label") or ""
            if edge_label:
                # Sanitise label
                edge_label = edge_label.replace('"', "'")
                mermaid_lines.append(f'    {from_node} -->|"{edge_label}"| {to_node}')
            else:
                mermaid_lines.append(f'    {from_node} --> {to_node}')

    return "\n".join(mermaid_lines)


def convert_svg_to_mermaid(svg_content: str) -> str:
    """Convert SVG flowchart to Mermaid syntax.

    Parses SVG <text> elements and builds a flowchart based on
    Y-coordinate ordering (text lower on screen comes later in flow).

    Args:
        svg_content: SVG markup string

    Returns:
        Mermaid.js syntax string
    """
    try:
        # Parse SVG
        root = ET.fromstring(svg_content)

        # Find all text elements
        text_elements = []
        for elem in root.iter():
            # Check for text elements (including namespaced)
            if elem.tag.endswith('text'):
                text_content = elem.text or ""
                text_content = text_content.strip()

                if text_content:
                    # Extract Y coordinate for ordering
                    y_coord = elem.get('y', '0')
                    try:
                        y_pos = float(y_coord)
                    except (ValueError, TypeError):
                        y_pos = 0

                    text_elements.append({
                        'text': text_content,
                        'y': y_pos
                    })

        # Sort by Y coordinate to infer flow order
        text_elements.sort(key=lambda x: x['y'])

        # Build Mermaid graph
        mermaid_lines = [f"graph {GRAPH_DIRECTION}"]

        # Deduplicate text while preserving order
        seen_texts = set()
        unique_texts = []
        for item in text_elements:
            if item['text'] not in seen_texts:
                seen_texts.add(item['text'])
                unique_texts.append(item['text'])

        # Create nodes
        node_ids = []
        for i, text in enumerate(unique_texts):
            # Sanitise text for node ID
            node_id = f"node{i}"
            text_sanitised = text.replace('"', "'")
            mermaid_lines.append(f'    {node_id}["{text_sanitised}"]')
            node_ids.append(node_id)

        # Create sequential edges
        for i in range(len(node_ids) - 1):
            mermaid_lines.append(f'    {node_ids[i]} --> {node_ids[i + 1]}')

        return "\n".join(mermaid_lines)

    except ET.ParseError as e:
        logger.warning(f"Failed to parse SVG: {e}")
        return f"graph TD\n    Error[\"Invalid SVG: {str(e)}\"]\n"


def _create_placeholder_mermaid(format_type: str) -> str:
    """Create placeholder Mermaid content for vision-based formats.

    Args:
        format_type: Format type ("image" or "pdf")

    Returns:
        Placeholder Mermaid string
    """
    return f"%% {format_type.capitalize()} flowchart - requires vision LLM processing\ngraph TD\n    Pending[\"Flowchart extraction pending vision LLM processing\"]\n"


def capture_flowchart_screenshot(page, url: str) -> Optional[bytes]:
    """Capture screenshot of flowchart page using Playwright.

    This is a stub implementation - full implementation requires Playwright
    async context management (will be completed in Task 15).

    Args:
        page: Playwright page object
        url: URL of the flowchart page

    Returns:
        Screenshot as bytes, or None if capture fails
    """
    try:
        # Stub implementation - in Task 15, this will:
        # 1. Navigate to URL
        # 2. Wait for flowchart to render
        # 3. Take screenshot
        # 4. Return bytes

        # For now, return None to indicate not implemented
        logger.warning(f"Screenshot capture not yet implemented for: {url}")
        return None

    except Exception as e:
        logger.error(f"Screenshot capture failed for {url}: {e}")
        return None


def process_all_flowcharts(
    discovery_path: str,
    output_dir: str,
) -> List[Dict[str, Any]]:
    """Process all flowcharts from discovery results.

    Iterates through guidelines with flowcharts, extracts flowchart content,
    and saves to output directory.

    Args:
        discovery_path: Path to discovery results JSON file
        output_dir: Directory to save flowchart JSON files

    Returns:
        List of flowchart dicts
    """
    # Load discovery results
    with open(discovery_path, 'r', encoding='utf-8') as f:
        discovery = json.load(f)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    results = []
    guidelines = discovery.get("guidelines", [])

    # Filter to guidelines with flowcharts
    flowchart_guidelines = [g for g in guidelines if g.get("has_flowchart", False)]

    logger.info(f"Processing {len(flowchart_guidelines)} flowcharts")

    for guideline in flowchart_guidelines:
        cpg_code = guideline.get("cpg_code")
        title = guideline.get("title", "Unknown Flowchart")
        route_slug = guideline.get("route_slug", "")

        if not cpg_code:
            logger.warning(f"Skipping guideline with missing cpg_code: {guideline}")
            continue

        try:
            # Build flowchart URL
            flowchart_url = f"{AT_BASE_URL}/flowchart/{route_slug}"

            # For now, create placeholder entries
            # In full implementation, we would:
            # 1. Fetch flowchart content from URL
            # 2. Classify format
            # 3. Extract accordingly
            # 4. Use vision LLM for image/PDF if needed

            flowchart_data = {
                "cpg_code": cpg_code,
                "title": f"{title} - Flowchart",
                "source_format": "unknown",
                "mermaid": _create_placeholder_mermaid("unknown"),
                "asset_ref": flowchart_url,
                "review_required": True,  # Will be updated after extraction
            }

            results.append(flowchart_data)

            # Save individual file
            output_file = Path(output_dir) / f"{cpg_code}_flowchart.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(flowchart_data, f, indent=2)

            logger.info(f"Processed flowchart for {cpg_code}: {title}")

        except Exception as e:
            logger.error(f"Failed to process flowchart for {cpg_code}: {e}")

            # Add error entry
            results.append({
                "cpg_code": cpg_code,
                "title": f"{title} - Flowchart (Error)",
                "source_format": "unknown",
                "mermaid": f"%% Error processing flowchart: {str(e)}",
                "asset_ref": None,
                "review_required": True,
                "error": str(e),
            })

    logger.info(f"Processed {len(results)} flowcharts total")

    # Save summary
    summary_file = Path(output_dir) / "_flowcharts_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_flowcharts": len(results),
            "successful_extractions": sum(1 for r in results if "error" not in r),
            "failed_extractions": sum(1 for r in results if "error" in r),
            "flowcharts": results,
        }, f, indent=2)

    return results


def extract_flowchart_from_content(
    content: str | bytes,
    cpg_code: str,
    title: str,
) -> ATFlowchart:
    """Extract flowchart from content with appropriate method.

    Args:
        content: Flowchart content (JSON, SVG, or binary)
        cpg_code: Parent CPG code
        title: Flowchart title

    Returns:
        ATFlowchart object
    """
    # Classify format
    fmt = classify_flowchart_format(content)

    # Extract based on format
    if fmt == "data":
        mermaid = extract_data_driven_flowchart(content)  # type: ignore
        review_required = False
        asset_ref = None
    elif fmt == "svg":
        mermaid = convert_svg_to_mermaid(content)  # type: ignore
        review_required = False
        asset_ref = None
    elif fmt in ("image", "pdf"):
        mermaid = _create_placeholder_mermaid(fmt)
        review_required = True
        asset_ref = None  # Will be set to bundle path or URL
    else:
        mermaid = _create_placeholder_mermaid("unknown")
        review_required = True
        asset_ref = None

    return ATFlowchart(
        cpg_code=cpg_code,
        title=title,
        source_format=fmt,  # type: ignore
        mermaid=mermaid,
        asset_ref=asset_ref,
        review_required=review_required,
    )
