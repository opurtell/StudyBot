# AT CPG Leaf Guideline Scraper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the AT CPG scraper to navigate into leaf guideline pages and extract actual clinical content, then update the 155 stub structured files.

**Architecture:** Two-phase Playwright scraper. Phase 1 discovers all leaf guideline URLs by navigating each category and collecting clickable leaf items. Phase 2 scrapes each discovered URL. A final mapping step writes content into the existing `CPG_*.json` structured files.

**Tech Stack:** Python 3, Playwright (sync API), existing JSON structured files.

---

### Task 1: Rewrite the scraper — discovery phase

**Files:**
- Modify: `scripts/at_scrape_all.py` (full rewrite)

- [ ] **Step 1: Write the discovery function**

Replace the entire contents of `scripts/at_scrape_all.py` with a new scraper. The key change: the guideline section no longer scrapes category pages — it discovers leaf URLs by clicking into each category and collecting the `href` attributes or click targets of leaf-level items.

```python
"""Scrape all AT CPG guidelines and medicines via Playwright.

Renders each leaf guideline page, extracts structured text content, and saves as JSON.

Usage:
    python3 scripts/at_scrape_all.py
"""

import json
import re
import time
from pathlib import Path

BASE_URL = "https://cpg.ambulance.tas.gov.au"
OUTPUT_DIR = Path("data/at/raw")
STRUCTURED_DIR = Path("data/services/at/structured")
DISCOVERY_OUT = Path("data/at/investigation/leaf_urls.json")

# Category slugs mapped to their top-level URL path segments
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

# Qualification levels to iterate (ordered broadest first for dedup)
QUAL_LEVELS = ["Paramedic", "ICP", "CP/ECP", "PACER"]

# Medicine page slugs (already scraped successfully — skip in guideline pass)
MEDICINE_SLUGS = {
    "adrenaline", "amiodarone", "aspirin", "atropine", "ceftriaxone",
    "dexamethasone", "diazepam", "droperidol", "enoxaparin", "ergometrine",
    "fentanyl", "frusemide", "glucagon", "glucosefive", "glucoseten",
    "glucose-paste", "gtn", "heparin", "ibuprofen", "ipratropium-bromide",
    "ketamine", "lignocaine", "magnesium-sulphate", "methoxyflurane",
    "metoclopramide", "midazolam", "morphine", "naloxone", "normal-saline",
    "olanzapint-odt", "ondansetron", "oxygen", "oxytocin", "paracetamol",
    "prochlorperazine", "quetiapine", "salbutamol", "sodium-bicarbonate",
    "sumatriptan", "tenecteplase", "tranexamic-acid", "water-for-injection",
    "clopidogrel", "drug-presentation", "cetirizine-dtp", "cophenylcaine-forte-dtp",
    "loperamide-dtp", "oral-rehydration-salts-dtp", "ural-dtp",
    "diazepam-pacer", "adrenaline-cfp", "aspirin-cfp", "glucagon-cfp",
    "glucose-paste-cfp", "gtn-cfp", "ibuprofen-cfp", "ipratropium-bromide-cfp",
    "methoxyflurane-cfp", "oxygen-cfp", "paracetamol-cfp", "salbutamol-cfp",
}


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


def select_qualification_level(page, level: str) -> None:
    """Select a qualification level on the site."""
    # Try clicking the user-info / level selector
    try:
        # Look for the level selector button or dropdown
        level_btn = page.locator(
            f"ion-item:has-text('{level}'), ion-button:has-text('{level}')"
        ).first
        level_btn.click(force=True, timeout=5000)
        time.sleep(1)
        dismiss_modals(page)
    except Exception:
        # If no selector found, the level may already be set or not required
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


def discover_leaf_urls(page, section_slug: str, section_info: dict) -> list[dict]:
    """Navigate a guideline section and discover all leaf-level page URLs.

    Clicks into each category within a section, collects clickable leaf items
    (those with angle-double-right icon or direct href links), and records
    the leaf URL and metadata.
    """
    leaves = []
    cat_url = f"{BASE_URL}/{section_info['path']}"

    try:
        page.goto(cat_url, wait_until="networkidle", timeout=20000)
        time.sleep(2)
        dismiss_modals(page)
        time.sleep(0.5)
    except Exception as e:
        print(f"  FAILED to load {cat_url}: {e}")
        return leaves

    # Get all ion-item elements on the category page
    items = page.query_selector_all("ion-item")
    print(f"  Found {len(items)} items on {section_slug}")

    for i, item in enumerate(items):
        text = (item.inner_text() or "").strip()
        if not text or len(text) > 200:
            continue

        # Get the first line as display text
        display_text = text.split("\n")[0].strip()

        # Check if this item has a link/href we can extract
        href = None
        try:
            link = item.query_selector("a[href]")
            if link:
                href = link.get_attribute("href")
        except Exception:
            pass

        try:
            # Click into the item to navigate to the leaf page
            item.click(force=True, timeout=5000)
            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1)
            dismiss_modals(page)

            current_url = page.url
            # Check if we actually navigated to a new page
            # (leaf pages have different URLs from category pages)
            is_new_page = current_url != cat_url

            if is_new_page:
                # Check if this new page has sub-items (it's another category)
                # or if it's a leaf page with actual content
                sub_items = page.query_selector_all("ion-item")
                has_content = False

                # Check if the page has substantial text content beyond just nav items
                main_content = page.query_selector("ion-content")
                if main_content:
                    full_text = (main_content.inner_text() or "").strip()
                    # Leaf pages have headings and paragraphs, not just a list of items
                    has_headings = bool(page.query_selector(
                        "ion-content h1, ion-content h2, ion-content h3, ion-content h4"
                    ))
                    has_content = has_headings or len(full_text) > 500

                if has_content:
                    # This is a leaf page
                    leaf_entry = {
                        "url": current_url,
                        "display_text": display_text,
                        "section": section_info["label"],
                        "section_slug": section_slug,
                    }
                    leaves.append(leaf_entry)
                    print(f"    LEAF: {display_text} -> {current_url}")
                else:
                    # This is a sub-category — recurse into its items
                    print(f"    SUB-CATEGORY: {display_text}")
                    sub_leaves = _discover_subcategory_leaves(page, display_text)
                    leaves.extend(sub_leaves)

                # Go back
                page.go_back(wait_until="networkidle", timeout=10000)
                time.sleep(1.5)
                dismiss_modals(page)
            else:
                # Didn't navigate — might need to try clicking differently
                print(f"    SKIP (no navigation): {display_text}")

        except Exception as e:
            print(f"    ERROR on '{display_text}': {e}")
            try:
                page.go_back(wait_until="networkidle", timeout=10000)
                time.sleep(0.5)
                dismiss_modals(page)
            except Exception:
                pass

    return leaves


def _discover_subcategory_leaves(page, parent_name: str) -> list[dict]:
    """Discover leaf pages within a sub-category page (already navigated to it)."""
    leaves = []
    items = page.query_selector_all("ion-item")
    print(f"      {len(items)} sub-items in '{parent_name}'")

    for item in items:
        text = (item.inner_text() or "").strip()
        if not text or len(text) > 200:
            continue
        display_text = text.split("\n")[0].strip()

        try:
            item.click(force=True, timeout=5000)
            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1)
            dismiss_modals(page)

            current_url = page.url
            main_content = page.query_selector("ion-content")

            if main_content:
                full_text = (main_content.inner_text() or "").strip()
                has_headings = bool(page.query_selector(
                    "ion-content h1, ion-content h2, ion-content h3, ion-content h4"
                ))
                has_content = has_headings or len(full_text) > 500

                if has_content:
                    leaves.append({
                        "url": current_url,
                        "display_text": display_text,
                        "section": parent_name,
                        "section_slug": "",
                    })
                    print(f"        LEAF: {display_text}")
                else:
                    # Deeper nesting — recurse
                    deeper = _discover_subcategory_leaves(page, display_text)
                    leaves.extend(deeper)

            page.go_back(wait_until="networkidle", timeout=10000)
            time.sleep(1)
            dismiss_modals(page)

        except Exception as e:
            print(f"        ERROR on '{display_text}': {e}")
            try:
                page.go_back(wait_until="networkidle", timeout=10000)
                time.sleep(0.5)
                dismiss_modals(page)
            except Exception:
                pass

    return leaves


def scrape_leaf_page(page, url: str) -> dict | None:
    """Navigate to a leaf page URL and extract its content."""
    try:
        page.goto(url, wait_until="networkidle", timeout=20000)
        time.sleep(2)
        dismiss_modals(page)
        time.sleep(0.5)
        return extract_page_content(page)
    except Exception as e:
        print(f"  FAILED to scrape {url}: {e}")
        return None


def cpg_code_to_filename(code: str) -> str:
    """Convert a CPG code like 'A0201-1' to a filename like 'CPG_A0201_1.json'."""
    normalized = code.replace("-", "_")
    return f"CPG_{normalized}.json"


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


def update_structured_file(slug: str, scraped: dict) -> bool:
    """Find and update the matching CPG_*.json structured file with scraped content."""
    # Extract CPG code from the scraped title (e.g. "Medical Cardiac Arrest\nCPG A0201-1")
    title_text = scraped.get("title", "")
    cpg_code = None

    # Try to extract CPG code from title
    match = re.search(r'CPG\s+([A-Z]\d+(?:-\d+)?)', title_text)
    if match:
        cpg_code = match.group(1)

    if not cpg_code:
        # Try matching by slug name against structured file titles
        slug_words = slug.replace("-", " ").lower()
        for f in STRUCTURED_DIR.glob("CPG_*.json"):
            data = json.loads(f.read_text())
            file_title = data.get("title", "").lower()
            if slug_words in file_title or file_title in slug_words:
                cpg_code = data.get("cpg_code")
                break

    if not cpg_code:
        return False

    filename = cpg_code_to_filename(cpg_code)
    filepath = STRUCTURED_DIR / filename

    if not filepath.exists():
        return False

    # Read, update, write
    data = json.loads(filepath.read_text())
    content_md = build_markdown_from_sections(
        scraped.get("sections", []),
        scraped.get("full_text", "")
    )

    data["content_markdown"] = content_md
    data["extraction_metadata"] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
        "source_type": "scraped",
        "agent_version": "at-pipeline-2.0",
        "source_url": scraped.get("url", ""),
        "content_flag": "scraped",
    }

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return True


def main():
    from playwright.sync_api import sync_playwright

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_leaves = []  # type: list[dict]
    seen_urls = set()

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

        # --- PHASE 1: DISCOVERY ---
        print("=" * 60)
        print("PHASE 1: Discovering leaf guideline pages")
        print("=" * 60)

        for level in QUAL_LEVELS:
            print(f"\n--- Qualification Level: {level} ---")

            # Load base page and select level
            page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            dismiss_modals(page)
            select_qualification_level(page, level)
            time.sleep(1)

            for section_slug, section_info in GUIDELINE_SECTIONS.items():
                print(f"\n  Section: {section_info['label']}")
                leaves = discover_leaf_urls(page, section_slug, section_info)

                new_count = 0
                for leaf in leaves:
                    if leaf["url"] not in seen_urls:
                        seen_urls.add(leaf["url"])
                        all_leaves.append(leaf)
                        leaf["qual_level"] = level
                        new_count += 1

                print(f"    Discovered {len(leaves)} pages, {new_count} new")

        # Save discovery manifest
        DISCOVERY_OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(DISCOVERY_OUT, "w") as f:
            json.dump(all_leaves, f, indent=2, ensure_ascii=False)
        print(f"\nDiscovery: {len(all_leaves)} unique leaf pages found")

        # --- PHASE 2: SCRAPE ---
        print("\n" + "=" * 60)
        print("PHASE 2: Scraping leaf guideline pages")
        print("=" * 60)

        results = []
        errors = []
        updated = 0

        for i, leaf in enumerate(all_leaves):
            url = leaf["url"]
            slug = url.rstrip("/").split("/")[-1]
            print(f"  [{i+1}/{len(all_leaves)}] {slug}: {url}")

            scraped = scrape_leaf_page(page, url)
            if scraped is None:
                errors.append({"url": url, "error": "scrape returned None"})
                continue

            scraped["slug"] = slug
            scraped["section"] = leaf.get("section", "")
            scraped["qual_level"] = leaf.get("qual_level", "")
            scraped["page_type"] = "guideline"

            results.append(scraped)

            # Save raw JSON
            out_file = OUTPUT_DIR / f"{slug}.json"
            with open(out_file, "w") as f:
                json.dump(scraped, f, indent=2, ensure_ascii=False)

            sections_count = len(scraped.get("sections", []))
            text_len = len(scraped.get("full_text", ""))
            print(f"    {sections_count} sections, {text_len} chars")

            # Update structured file
            if update_structured_file(slug, scraped):
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
```

- [ ] **Step 2: Run the scraper**

Run: `cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot && python3 scripts/at_scrape_all.py`

Expected: The scraper will iterate through qualification levels, discover leaf guideline URLs by clicking through category pages, and scrape each one. Watch the console output for:
- Discovery phase showing leaf pages found per section
- Scrape phase showing section counts and text lengths
- Structured file update counts

The scraper will take several minutes to run (~91 pages × ~4s each = ~6 minutes).

- [ ] **Step 3: Verify the output**

Run:
```bash
# Check discovery manifest
python3 -c "import json; d=json.load(open('data/at/investigation/leaf_urls.json')); print(f'Discovered: {len(d)} leaf pages')"

# Check structured files for content
python3 -c "
import json
from pathlib import Path
full = 0
stubs = 0
for f in Path('data/services/at/structured').glob('CPG_*.json'):
    d = json.loads(f.read_text())
    if len(d.get('content_markdown', '').strip()) > 100:
        full += 1
    else:
        stubs += 1
print(f'Structured files with content: {full}')
print(f'Remaining stubs: {stubs}')
"
```

Expected: Most of the 155 stub files should now have content. Some may remain as stubs if they represent CPG codes that don't have discoverable leaf pages on the site.

- [ ] **Step 4: Commit**

```bash
git add scripts/at_scrape_all.py data/at/investigation/leaf_urls.json data/services/at/structured/
git commit -m "feat: rewrite AT CPG scraper to navigate leaf guideline pages

Replace category-level scraping with Playwright navigation that clicks
into individual guideline pages. Supports multi-level qualification
discovery (Paramedic, ICP, CP/ECP, PACER) with deduplication.

Updates structured CPG_*.json files with scraped content."
```

---

### Task 2: Handle edge cases and missed pages

**Files:**
- Modify: `scripts/at_scrape_all.py` (if needed)

- [ ] **Step 1: Check for remaining stubs and investigate**

After the first run, check which structured files are still stubs:

```bash
python3 -c "
import json
from pathlib import Path
for f in sorted(Path('data/services/at/structured').glob('CPG_*.json')):
    d = json.loads(f.read_text())
    if len(d.get('content_markdown', '').strip()) < 100:
        print(f'{f.name}: {d[\"title\"]} ({d[\"section\"]})')
"
```

Investigate any remaining stubs:
- They may be pages only visible at a different qualification level
- They may have URL patterns not discovered by the category navigation
- They may correspond to medicine or checklist pages (already scraped separately)

- [ ] **Step 2: Fix any issues found**

If specific pages were missed, add targeted URL construction for them based on the component selectors found in `common.js`. The 172 component selectors extracted from the JS bundle can be used as fallback URLs.

```python
# Fallback: try component selector URLs for remaining stubs
# These follow patterns like:
# /tabs/guidelines/adult-patient-guidelines/{category-slug}/{leaf-slug}
# /tabs/guidelines/paediatric-patient-guidelines/{category-slug}/{leaf-slug}
```

- [ ] **Step 3: Re-run and verify**

```bash
python3 scripts/at_scrape_all.py
# Then re-check stubs
```

- [ ] **Step 4: Commit fixes**

```bash
git add scripts/at_scrape_all.py data/services/at/structured/
git commit -m "fix: handle edge cases in AT CPG leaf scraper"
```
