"""Shared utilities for AT CPG scraper scripts."""

import json
import re
import time
from pathlib import Path

STRUCTURED_DIR = Path("data/services/at/structured")
STUB_MARKER = "Content pending extraction."


def dismiss_modals(page) -> None:
    """Remove any blocking modals from the DOM."""
    try:
        ok = page.locator("button:has-text('OK')").first
        if ok.is_visible(timeout=500):
            ok.click(force=True, timeout=1000)
            time.sleep(0.3)
    except Exception:
        pass
    try:
        page.evaluate("""
            document.querySelectorAll('ion-modal, ion-backdrop').forEach(m => {
                m.style.display = 'none'; m.remove();
            });
        """)
    except Exception:
        pass


def extract_page_content(page) -> dict:
    """Extract structured content from a rendered guideline/medicine page."""
    content = {
        "title": "",
        "url": page.url,
        "sections": [],
        "full_text": "",
    }

    try:
        title_el = page.query_selector("ion-toolbar ion-title")
        if title_el:
            content["title"] = (title_el.inner_text() or "").strip()
    except Exception:
        pass

    try:
        main_content = page.query_selector("ion-content")
        if not main_content:
            main_content = page.query_selector("body")

        if main_content:
            sections = []
            current_heading = None
            current_body_parts = []

            children = main_content.query_selector_all(
                "h1, h2, h3, h4, h5, h6, p, ul, ol, section, article, .section, ion-card"
            )

            for child in children:
                tag = child.evaluate("el => el.tagName.toLowerCase()")
                text = (child.inner_text() or "").strip()

                if not text:
                    continue

                if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    if current_heading and current_body_parts:
                        sections.append({
                            "heading": current_heading,
                            "body": "\n".join(current_body_parts).strip(),
                        })
                    current_heading = text
                    current_body_parts = []
                elif tag == "ion-card":
                    card_heading = child.query_selector("h1, h2, h3, h4, h5, h6")
                    if card_heading:
                        if current_heading and current_body_parts:
                            sections.append({
                                "heading": current_heading,
                                "body": "\n".join(current_body_parts).strip(),
                            })
                        current_heading = (card_heading.inner_text() or "").strip()
                        current_body_parts = []
                    else:
                        current_body_parts.append(text)
                else:
                    current_body_parts.append(text)

            if current_heading and current_body_parts:
                sections.append({
                    "heading": current_heading,
                    "body": "\n".join(current_body_parts).strip(),
                })

            content["sections"] = sections
            content["full_text"] = (main_content.inner_text() or "").strip()

    except Exception as e:
        content["error"] = str(e)

    return content


def build_markdown_from_sections(sections: list[dict], full_text: str) -> str:
    """Build markdown content from scraped sections."""
    if not sections:
        return full_text

    parts = []
    for s in sections:
        heading = s.get("heading", "")
        body = s.get("body", "")
        if heading:
            parts.append(f"## {heading}\n\n{body}")
        elif body:
            parts.append(body)

    return "\n\n".join(parts)


def is_stub(content_markdown: str) -> bool:
    """Check if content_markdown is a stub (empty or contains the pending marker)."""
    text = content_markdown.strip()
    return len(text) < 100 or STUB_MARKER in text


def cpg_code_to_filename(code: str) -> str:
    """Convert a CPG code like 'A0201-1' to a filename like 'CPG_A0201_1.json'."""
    return f"CPG_{code.replace('-', '_')}.json"


def extract_cpg_code(scraped: dict) -> str | None:
    """Extract CPG code from scraped page title or full text."""
    for field in ("title", "full_text"):
        match = re.search(r'CPG\s+([A-Z]\d+(?:-\d+)?)', scraped.get(field, ""))
        if match:
            return match.group(1)
    return None


def update_structured_file(
    scraped: dict,
    cpg_code: str | None = None,
    agent_version: str = "at-pipeline-2.0",
) -> bool:
    """Find and update the matching CPG_*.json structured file with scraped content.

    If cpg_code is not provided, extracts it from the scraped title/full_text.
    Skips writes where content is shorter than 100 chars to avoid overwriting
    good stubs with empty scrapes.
    """
    if not cpg_code:
        cpg_code = extract_cpg_code(scraped)

    if not cpg_code:
        return False

    filepath = STRUCTURED_DIR / cpg_code_to_filename(cpg_code)
    if not filepath.exists():
        return False

    content_md = build_markdown_from_sections(
        scraped.get("sections", []),
        scraped.get("full_text", ""),
    )

    if len(content_md.strip()) < 100:
        return False

    data = json.loads(filepath.read_text())
    data["content_markdown"] = content_md
    data["extraction_metadata"] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
        "source_type": "scraped",
        "agent_version": agent_version,
        "source_url": scraped.get("url", ""),
        "content_flag": "scraped",
    }

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return True
