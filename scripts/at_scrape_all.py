"""Scrape all AT CPG guidelines and medicines via Playwright.

Renders each leaf guideline page, extracts structured text content, and saves as JSON.

Usage:
    python3 scripts/at_scrape_all.py
"""

import json
import re
import time
from pathlib import Path

from at_scrape_utils import (
    dismiss_modals,
    extract_page_content,
    update_structured_file,
)

BASE_URL = "https://cpg.ambulance.tas.gov.au"
OUTPUT_DIR = Path("data/at/raw")
STRUCTURED_DIR = Path("data/services/at/structured")
DISCOVERY_OUT = Path("data/at/investigation/leaf_urls.json")

# Fallback: category slugs for Playwright discovery when bundle data is absent
GUIDELINE_SECTIONS = {
    "adult-patient-guidelines": {
        "label": "Adult Patient Guidelines",
        "path": "tabs/guidelines/adult-patient-guidelines",
    },
    "paediatric-patient-guidelines": {
        "label": "Paediatric Patient Guidelines",
        "path": "tabs/guidelines/paediatric-patient-guidelines",
    },
    "maternity-guidelines": {
        "label": "Maternity",
        "path": "tabs/guidelines/maternity-guidelines",
    },
    "reference-notes": {
        "label": "Reference Notes",
        "path": "tabs/guidelines/reference-notes",
    },
    "in-field-referrals": {
        "label": "In Field Referrals",
        "path": "tabs/guidelines/in-field-referrals",
    },
}


def sanitize_slug(slug: str) -> str:
    """Strip special characters from a URL slug for use as a filename."""
    return re.sub(r"[^a-z0-9-]", "", slug)


# --- Playwright fallback discovery (used only when bundle data is absent) ---

def _collect_item_texts(page) -> list[str]:
    """Collect the display texts of all visible ion-items on the current page."""
    items = page.query_selector_all("ion-item")
    texts = []
    for item in items:
        text = (item.inner_text() or "").strip()
        if text and len(text) <= 200:
            texts.append(text.split("\n")[0].strip())
    return texts


def _is_leaf_page(page) -> bool:
    """Return True if the current page looks like a leaf content page."""
    main_content = page.query_selector("ion-content")
    if not main_content:
        return False
    full_text = (main_content.inner_text() or "").strip()
    has_headings = bool(page.query_selector(
        "ion-content h1, ion-content h2, ion-content h3, ion-content h4"
    ))
    return has_headings or len(full_text) > 500


def _click_item_by_text(page, display_text: str) -> bool:
    """Click the ion-item matching display_text. Returns True if click succeeded."""
    try:
        items = page.query_selector_all("ion-item")
        for item in items:
            text = (item.inner_text() or "").strip()
            first_line = text.split("\n")[0].strip()
            if first_line == display_text:
                item.scroll_into_view_if_needed(timeout=3000)
                item.click(force=True, timeout=5000)
                return True
    except Exception:
        pass
    return False


def discover_leaf_urls(page, section_slug: str, section_info: dict) -> list[dict]:
    """Navigate a guideline section and discover all leaf-level page URLs.

    Collects item display texts first (avoiding stale handles), then navigates
    into each item by re-querying fresh elements after every go_back().
    """
    leaves = []
    cat_url = f"{BASE_URL}/{section_info['path']}"

    try:
        page.goto(cat_url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1)
        dismiss_modals(page)
    except Exception as e:
        print(f"  FAILED to load {cat_url}: {e}")
        return leaves

    item_texts = _collect_item_texts(page)
    print(f"  Found {len(item_texts)} items on {section_slug}")

    for display_text in item_texts:
        before_url = page.url
        try:
            clicked = _click_item_by_text(page, display_text)
            if not clicked:
                print(f"    SKIP (could not click): {display_text}")
                continue

            time.sleep(1)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            time.sleep(0.5)
            dismiss_modals(page)

            current_url = page.url
            if current_url == before_url:
                print(f"    SKIP (no navigation): {display_text}")
                continue

            if _is_leaf_page(page):
                leaf_entry = {
                    "url": current_url,
                    "display_text": display_text,
                    "section": section_info["label"],
                    "section_slug": section_slug,
                }
                leaves.append(leaf_entry)
                print(f"    LEAF: {display_text} -> {current_url}")
            else:
                print(f"    SUB-CATEGORY: {display_text}")
                sub_leaves = _discover_subcategory_leaves(
                    page, display_text, section_info["label"], depth=1
                )
                leaves.extend(sub_leaves)

            page.goto(cat_url, wait_until="domcontentloaded", timeout=12000)
            time.sleep(0.8)
            dismiss_modals(page)

        except Exception as e:
            print(f"    ERROR on '{display_text}': {e}")
            try:
                page.goto(cat_url, wait_until="domcontentloaded", timeout=12000)
                time.sleep(0.5)
                dismiss_modals(page)
            except Exception:
                pass

    return leaves


def _discover_subcategory_leaves(
    page, parent_name: str, section_label: str, depth: int = 1
) -> list[dict]:
    """Discover leaf pages within a sub-category page (already navigated to it)."""
    if depth > 3:
        print(f"{'  ' * (depth+2)}MAX DEPTH reached, skipping '{parent_name}'")
        return []

    leaves = []
    subcat_url = page.url
    indent = "  " * (depth + 2)

    item_texts = _collect_item_texts(page)
    print(f"{indent}{len(item_texts)} sub-items in '{parent_name}'")

    for display_text in item_texts:
        try:
            clicked = _click_item_by_text(page, display_text)
            if not clicked:
                print(f"{indent}  SKIP (could not click): {display_text}")
                continue

            time.sleep(1)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            time.sleep(0.5)
            dismiss_modals(page)

            current_url = page.url
            if current_url == subcat_url:
                print(f"{indent}  SKIP (no navigation): {display_text}")
                continue

            if _is_leaf_page(page):
                leaves.append({
                    "url": current_url,
                    "display_text": display_text,
                    "section": section_label,
                    "section_slug": "",
                })
                print(f"{indent}  LEAF: {display_text}")
            else:
                deeper = _discover_subcategory_leaves(
                    page, display_text, section_label, depth + 1
                )
                leaves.extend(deeper)

            page.goto(subcat_url, wait_until="domcontentloaded", timeout=12000)
            time.sleep(0.5)
            dismiss_modals(page)

        except Exception as e:
            print(f"{indent}  ERROR on '{display_text}': {e}")
            try:
                page.goto(subcat_url, wait_until="domcontentloaded", timeout=12000)
                time.sleep(0.3)
                dismiss_modals(page)
            except Exception:
                pass

    return leaves


def scrape_leaf_page(page, url: str) -> dict | None:
    """Navigate to a leaf page URL and extract its content."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1)
        dismiss_modals(page)
        return extract_page_content(page)
    except Exception as e:
        print(f"  FAILED to scrape {url}: {e}")
        return None


# --- Bundle-based discovery ---

BUNDLE_NAV_JSON = Path("data/at/investigation/guidelines_nav.json")
BUNDLE_LEAF_URLS = Path("data/at/investigation/leaf_urls_from_bundle.json")


def extract_leaf_urls_from_bundle() -> list[dict]:
    """Extract all leaf guideline URLs from the pre-parsed navigation bundle JSON."""
    import re as _re

    def title_to_url(page_obj: dict) -> str:
        raw = (page_obj.get("url") or page_obj.get("title", "")).lower()
        raw = _re.sub(r"[^a-z0-9]", " ", raw).strip()
        return _re.sub(r"\s+", "-", raw)

    def recurse(pages: list, parent_path: str, parent_title: str) -> list[dict]:
        results = []
        for page_obj in pages:
            if page_obj.get("hidden") or page_obj.get("doNotIndex"):
                continue
            url_slug = title_to_url(page_obj)
            if page_obj.get("pages"):
                sub_path = f"{parent_path}/{url_slug}"
                results.extend(recurse(page_obj["pages"], sub_path, page_obj.get("title", "")))
            else:
                full_path = f"{parent_path}/page/{url_slug}"
                results.append({
                    "url": BASE_URL + full_path,
                    "display_text": page_obj.get("title", ""),
                    "section": parent_title,
                    "section_slug": "",
                    "atp": page_obj.get("atp", []),
                    "cpg_section": page_obj.get("section", ""),
                })
        return results

    nav_data = json.loads(BUNDLE_NAV_JSON.read_text())
    return recurse(nav_data.get("pages", []), f"/tabs/{nav_data['url']}", "Guidelines")


def main():
    from playwright.sync_api import sync_playwright

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- PHASE 1: DISCOVERY ---
    print("=" * 60)
    print("PHASE 1: Loading leaf guideline URLs from bundle")
    print("=" * 60)

    if BUNDLE_LEAF_URLS.exists():
        all_leaves = json.loads(BUNDLE_LEAF_URLS.read_text())
        print(f"  Loaded {len(all_leaves)} URLs from {BUNDLE_LEAF_URLS}")
    elif BUNDLE_NAV_JSON.exists():
        all_leaves = extract_leaf_urls_from_bundle()
        print(f"  Extracted {len(all_leaves)} URLs from bundle nav JSON")
    else:
        print("  WARNING: No bundle data found, falling back to Playwright discovery")
        all_leaves = []
        seen_urls = set()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_context().new_page()
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
            time.sleep(1)
            dismiss_modals(page)
            for section_slug, section_info in GUIDELINE_SECTIONS.items():
                leaves = discover_leaf_urls(page, section_slug, section_info)
                for leaf in leaves:
                    if leaf["url"] not in seen_urls:
                        seen_urls.add(leaf["url"])
                        all_leaves.append(leaf)
            browser.close()

    DISCOVERY_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(DISCOVERY_OUT, "w") as f:
        json.dump(all_leaves, f, indent=2, ensure_ascii=False)
    print(f"Discovery: {len(all_leaves)} unique leaf pages")

    # --- PHASE 2: SCRAPE ---
    print("\n" + "=" * 60)
    print("PHASE 2: Scraping leaf guideline pages")
    print("=" * 60)

    results = []
    errors = []
    updated = 0

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

        for i, leaf in enumerate(all_leaves):
            url = leaf["url"]
            raw_slug = url.rstrip("/").split("/")[-1]
            slug = sanitize_slug(raw_slug)
            print(f"  [{i+1}/{len(all_leaves)}] {slug}: {url}")

            scraped = scrape_leaf_page(page, url)
            if scraped is None:
                errors.append({"url": url, "error": "scrape returned None"})
                continue

            scraped["slug"] = slug
            scraped["section"] = leaf.get("section", "")
            scraped["page_type"] = "guideline"

            results.append(scraped)

            out_file = OUTPUT_DIR / f"{slug}.json"
            with open(out_file, "w") as f:
                json.dump(scraped, f, indent=2, ensure_ascii=False)

            sections_count = len(scraped.get("sections", []))
            text_len = len(scraped.get("full_text", ""))
            print(f"    {sections_count} sections, {text_len} chars")

            if update_structured_file(scraped):
                updated += 1

        browser.close()

    # --- SUMMARY ---
    summary = {
        "total_discovered": len(all_leaves),
        "total_scraped": len(results),
        "total_errors": len(errors),
        "structured_updated": updated,
        "with_sections": sum(1 for r in results if r.get("sections")),
        "with_text": sum(1 for r in results if len(r.get("full_text", "")) > 100),
        "errors": errors,
    }

    with open(OUTPUT_DIR / "_scrape_summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Scraping complete!")
    print(f"  Leaf pages discovered: {summary['total_discovered']}")
    print(f"  Pages scraped: {summary['total_scraped']}")
    print(f"  With sections: {summary['with_sections']}")
    print(f"  With text (>100 chars): {summary['with_text']}")
    print(f"  Structured files updated: {summary['structured_updated']}")
    print(f"  Errors: {summary['total_errors']}")
    print(f"  Output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
