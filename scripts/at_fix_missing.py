"""Fix remaining issues from the AT CPG leaf scraper run.

1. CPG_P0901 — raw content exists but update failed (empty title, no CPG code match)
2. CPG_A0801 — URL had literal single quotes; retry with cleaned URL
3. clinical-practice-update — scraped empty shell; retry with longer wait
4. CPG_P0105 — category header with no leaf page; mark as known category stub
5. CPG_P0703 — scraped fine but empty title caused CPG code match to fail

Usage:
    python3 scripts/at_fix_missing.py
"""

import json
import re
import time
from pathlib import Path

from at_scrape_utils import (
    STUB_MARKER,
    dismiss_modals,
    extract_page_content,
    is_stub,
    update_structured_file,
)

STRUCTURED_DIR = Path("data/services/at/structured")
RAW_DIR = Path("data/at/raw")
BASE_URL = "https://cpg.ambulance.tas.gov.au"


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
    return update_structured_file(scraped, cpg_code="P0901", agent_version="at-pipeline-2.1-fix")


def fix_p0703() -> bool:
    """P0703 was scraped with empty title so CPG code extraction failed.

    The shared module now checks full_text too, but this applies it explicitly.
    """
    print("\n--- Fix: CPG_P0703 (Continuous or Recurrent Seizures Paediatric) ---")
    raw_path = RAW_DIR / "continuous-or-recurrent-seizures-paediatric.json"
    if not raw_path.exists():
        print("  SKIP — raw file missing")
        return False

    scraped = json.loads(raw_path.read_text())
    return update_structured_file(scraped, cpg_code="P0703", agent_version="at-pipeline-2.1-fix")


def fix_p0105() -> bool:
    """P0105 is a category header (Assessment Paediatric) with no leaf page.

    Mark it as a known category stub so it's not confused with a failed scrape.
    """
    print("\n--- Fix: CPG_P0105 (Assessment Paediatric — category header) ---")
    filepath = STRUCTURED_DIR / "CPG_P0105.json"
    if not filepath.exists():
        print("  SKIP — structured file missing")
        return False

    data = json.loads(filepath.read_text())
    data["content_markdown"] = (
        "# Assessment (Paediatric)\n\n"
        "CPG Reference: CPG P0105\n\n"
        "This is a category header page — it lists individual paediatric assessment "
        "guidelines (P0101–P0104) but has no standalone clinical content. "
        "See individual CPG P0101–P0104 entries for assessment details."
    )
    data["extraction_metadata"] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
        "source_type": "category_header",
        "agent_version": "at-pipeline-2.1-fix",
        "source_url": "",
        "content_flag": "category_header",
    }
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  MARKED as category header: {filepath.name}")
    return True


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

            raw_out = RAW_DIR / f"{t['slug']}_fixed.json"
            raw_out.write_text(json.dumps(scraped, indent=2, ensure_ascii=False))

            if t["cpg_code"] and full_text_len > 200:
                update_structured_file(scraped, cpg_code=t["cpg_code"], agent_version="at-pipeline-2.1-fix")
            elif not t["cpg_code"]:
                print(f"  No CPG code — standalone reference page (no structured file to update)")

            results[t["slug"]] = scraped

        except Exception as e:
            print(f"  ERROR: {e}")
            results[t["slug"]] = {"error": str(e)}

    return results


def main():
    from playwright.sync_api import sync_playwright

    # Fixes that don't need a browser
    fix_p0901()
    fix_p0703()
    fix_p0105()

    # Fixes that need a browser
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

    # Final check using is_stub (checks exact marker, not bare "pending" substring)
    print("\n=== Final coverage check ===")
    full = stubs = 0
    remaining = []
    for f in sorted(STRUCTURED_DIR.glob("CPG_*.json")):
        d = json.loads(f.read_text())
        if not is_stub(d.get("content_markdown", "")):
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
