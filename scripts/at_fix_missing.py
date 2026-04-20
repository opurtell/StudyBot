"""Fix the 3 remaining issues from the AT CPG leaf scraper run.

1. CPG_P0901 — raw content exists but update failed (empty title, no CPG code match)
2. CPG_A0801 — URL had literal single quotes; retry with cleaned URL
3. clinical-practice-update — scraped empty shell; retry with longer wait

Usage:
    python3 scripts/at_fix_missing.py
"""

import json
import re
import time
from pathlib import Path

STRUCTURED_DIR = Path("data/services/at/structured")
RAW_DIR = Path("data/at/raw")
BASE_URL = "https://cpg.ambulance.tas.gov.au"


def build_markdown_from_sections(sections: list[dict], full_text: str) -> str:
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


def write_to_structured(cpg_code: str, scraped: dict, source_url: str) -> bool:
    normalized = cpg_code.replace("-", "_")
    filepath = STRUCTURED_DIR / f"CPG_{normalized}.json"
    if not filepath.exists():
        print(f"  SKIP — no structured file for {cpg_code}")
        return False

    data = json.loads(filepath.read_text())
    content_md = build_markdown_from_sections(
        scraped.get("sections", []),
        scraped.get("full_text", ""),
    )

    if len(content_md.strip()) < 100:
        print(f"  SKIP — content too short ({len(content_md)} chars) for {cpg_code}")
        return False

    data["content_markdown"] = content_md
    data["extraction_metadata"] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
        "source_type": "scraped",
        "agent_version": "at-pipeline-2.1-fix",
        "source_url": source_url,
        "content_flag": "scraped",
    }

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  UPDATED {filepath.name} ({len(content_md)} chars)")
    return True


def dismiss_modals(page) -> None:
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
    content = {"title": "", "url": page.url, "sections": [], "full_text": ""}

    try:
        title_el = page.query_selector("ion-toolbar ion-title")
        if title_el:
            content["title"] = (title_el.inner_text() or "").strip()
    except Exception:
        pass

    try:
        main_content = page.query_selector("ion-content") or page.query_selector("body")
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
                        sections.append({"heading": current_heading, "body": "\n".join(current_body_parts).strip()})
                    current_heading = text
                    current_body_parts = []
                elif tag == "ion-card":
                    card_heading = child.query_selector("h1, h2, h3, h4, h5, h6")
                    if card_heading:
                        if current_heading and current_body_parts:
                            sections.append({"heading": current_heading, "body": "\n".join(current_body_parts).strip()})
                        current_heading = (card_heading.inner_text() or "").strip()
                        current_body_parts = []
                    else:
                        current_body_parts.append(text)
                else:
                    current_body_parts.append(text)

            if current_heading and current_body_parts:
                sections.append({"heading": current_heading, "body": "\n".join(current_body_parts).strip()})

            content["sections"] = sections
            content["full_text"] = (main_content.inner_text() or "").strip()
    except Exception as e:
        content["error"] = str(e)

    return content


def fix_p0901() -> bool:
    """P0901 was scraped successfully but update_structured_file couldn't match it.

    The raw file has good content — use it directly.
    """
    print("\n--- Fix 1: CPG_P0901 (Hypothermia/Cold Exposure Paediatric) ---")
    raw_path = RAW_DIR / "hypothermia-cold-exposure-paediatric.json"
    if not raw_path.exists():
        print("  SKIP — raw file missing")
        return False

    scraped = json.loads(raw_path.read_text())
    source_url = "https://cpg.ambulance.tas.gov.au/tabs/guidelines/paediatric-patient-guidelines/environment-paediatric/page/hypothermia-cold-exposure-paediatric"
    return write_to_structured("P0901", scraped, source_url)


def fix_a0801_and_clinical(page) -> dict:
    """Retry A0801 (clean URL) and clinical-practice-update (longer wait)."""
    results = {}

    targets = [
        {
            "cpg_code": "A0801",
            "url": f"{BASE_URL}/tabs/guidelines/adult-patient-guidelines/trauma/page/inadequate-perfusion-hypovolaemia",
            "slug": "inadequate-perfusion-hypovolaemia",
            "label": "CPG_A0801 (Inadequate Perfusion / Hypovolaemia)",
        },
        {
            "cpg_code": None,
            "url": f"{BASE_URL}/tabs/guidelines/reference-notes/page/clinical-practice-update",
            "slug": "clinical-practice-update",
            "label": "clinical-practice-update",
        },
    ]

    for t in targets:
        print(f"\n--- Fix: {t['label']} ---")
        try:
            page.goto(t["url"], wait_until="networkidle", timeout=30000)
            time.sleep(3)
            dismiss_modals(page)
            time.sleep(1)

            scraped = extract_page_content(page)
            full_text_len = len(scraped.get("full_text", ""))
            print(f"  Scraped: title={repr(scraped['title'])}, len={full_text_len}, sections={len(scraped['sections'])}")

            # Save raw
            raw_out = RAW_DIR / f"{t['slug']}_fixed.json"
            raw_out.write_text(json.dumps(scraped, indent=2, ensure_ascii=False))

            if t["cpg_code"] and full_text_len > 200:
                write_to_structured(t["cpg_code"], scraped, t["url"])
            elif not t["cpg_code"]:
                # clinical-practice-update: try CPG code from full_text
                match = re.search(r'CPG\s+([A-Z]\d+(?:-\d+)?)', scraped.get("full_text", ""))
                if match:
                    code = match.group(1)
                    print(f"  Found CPG code in text: {code}")
                    write_to_structured(code, scraped, t["url"])
                else:
                    print(f"  No CPG code found — standalone reference page (no structured file to update)")
                    print(f"  Content preview: {repr(scraped.get('full_text','')[:300])}")

            results[t["slug"]] = scraped

        except Exception as e:
            print(f"  ERROR: {e}")
            results[t["slug"]] = {"error": str(e)}

    return results


def main():
    from playwright.sync_api import sync_playwright

    # Fix 1: P0901 (no browser needed — raw data already exists)
    p0901_ok = fix_p0901()

    # Fix 2 & 3: A0801 + clinical-practice-update (need browser)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        fix_a0801_and_clinical(page)
        browser.close()

    # Final check
    print("\n=== Final coverage check ===")
    full = stubs = 0
    remaining = []
    for f in sorted(STRUCTURED_DIR.glob("CPG_*.json")):
        d = json.loads(f.read_text())
        if len(d.get("content_markdown", "").strip()) > 100 and "pending" not in d.get("content_markdown", ""):
            full += 1
        else:
            stubs += 1
            remaining.append(f"{f.name}: {d.get('title','')}")

    print(f"Structured files with content: {full}")
    print(f"Remaining stubs: {stubs}")
    for s in remaining:
        print(f"  {s}")


if __name__ == "__main__":
    main()
