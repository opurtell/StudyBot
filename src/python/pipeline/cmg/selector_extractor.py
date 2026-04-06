"""
Stage 2b: Selector-Based Template Extraction
Extracts clinical content from 7_common by mapping Angular component
selectors to their compiled template functions.
"""

import logging
import os
import re
from typing import List, Dict, Any, Optional

from .template_parser import (
    parse_template_instructions,
    _find_template_boundaries,
)

logger = logging.getLogger(__name__)

_COMMON_BUNDLE_RE = re.compile(r"^7_common\.[\w]+\.js$")

_SELECTOR_RE = re.compile(r'selectors:\[\["([^"]+)"\]\]')
_TEMPLATE_RE = re.compile(r"template:\s*function\s*\(\s*\w+\s*,\s*\w+\s*\)\s*\{")


def _find_common_bundle(directory: str) -> Optional[str]:
    for fname in os.listdir(directory):
        if _COMMON_BUNDLE_RE.match(fname):
            return os.path.join(directory, fname)
    return None


def selector_to_route(selector: str) -> str:
    return selector.removeprefix("app-")


def _extract_template_at(content: str, template_start: int) -> Optional[str]:
    _, end = _find_template_boundaries(content, template_start)
    block = content[template_start:end]
    results = parse_template_instructions(block)
    if results:
        return results[0]["html"]
    return None


def extract_selector_templates(
    bundle_path: str = "",
    investigation_dir: str = "data/cmgs/investigation/",
) -> List[Dict[str, Any]]:
    if bundle_path:
        paths = [bundle_path]
    else:
        paths = []
        for fname in sorted(os.listdir(investigation_dir)):
            if fname.endswith(".js") and not fname.startswith("0_"):
                paths.append(os.path.join(investigation_dir, fname))

    results: List[Dict[str, Any]] = []
    seen_selectors: set = set()

    for path in paths:
        if not os.path.exists(path):
            continue

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        selector_positions: List[tuple] = [
            (m.start(), m.group(1)) for m in _SELECTOR_RE.finditer(content)
        ]
        template_positions: List[int] = [
            m.start() for m in _TEMPLATE_RE.finditer(content)
        ]

        if not selector_positions or not template_positions:
            continue

        for sel_pos, sel_name in selector_positions:
            if sel_name in seen_selectors:
                continue

            nearest_template = None
            for tp in template_positions:
                if tp > sel_pos:
                    nearest_template = tp
                    break

            if nearest_template is None:
                continue

            html = _extract_template_at(content, nearest_template)
            if html:
                seen_selectors.add(sel_name)
                results.append(
                    {
                        "selector": sel_name,
                        "route_path": selector_to_route(sel_name),
                        "html": html,
                        "html_length": len(html),
                    }
                )

    logger.info(
        f"Extracted {len(results)} selector-mapped templates from {len(paths)} bundles"
    )
    return results
