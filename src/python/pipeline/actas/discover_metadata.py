"""Lightweight Playwright crawl of the CMG guideline list page to extract
titles, version dates, and compare against existing structured data."""

import json
import logging
import os
import re
from typing import Any

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover — playwright not installed in test env
    sync_playwright = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s+Version\s+([\d.]+)")
_URL = "https://cmg.ambulance.act.gov.au/tabs/guidelines"


def _dismiss_modals(page) -> None:
    from playwright.sync_api import TimeoutError
    try:
        page.wait_for_selector("app-disclaimer ion-button", state="visible", timeout=10000)
        page.locator("app-disclaimer ion-button").filter(has_text="OK").click()
    except TimeoutError:
        pass
    try:
        page.wait_for_selector("ion-modal ion-item", state="visible", timeout=5000)
        page.locator("ion-modal ion-item").filter(has_text="Intensive Care Paramedic").click()
    except TimeoutError:
        pass
    try:
        page.wait_for_selector("ion-modal", state="hidden", timeout=10000)
    except TimeoutError:
        pass


def _parse_version_text(text: str) -> dict[str, str]:
    match = _VERSION_RE.search(text)
    if match:
        return {"date": match.group(1), "version": match.group(2)}
    return {"date": "", "version": ""}


def _load_existing_versions(structured_dir: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    if not os.path.isdir(structured_dir):
        return versions
    for fname in os.listdir(structured_dir):
        if not fname.endswith(".json") or fname.startswith(".") or "index" in fname:
            continue
        fpath = os.path.join(structured_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            title = data.get("title", "")
            version_str = data.get("version_date", "")
            if title and version_str:
                versions[title.lower().strip()] = version_str
        except (json.JSONDecodeError, OSError):
            continue
    return versions


def discover_metadata(
    url: str = _URL,
    output_dir: str = "data/cmgs/raw",
    structured_dir: str = "data/cmgs/structured",
) -> dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    guidelines: list[dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        _dismiss_modals(page)

        page.wait_for_selector(
            "ion-router-outlet > .ion-page:last-child ion-item",
            state="visible",
            timeout=10000,
        )

        import time
        time.sleep(1)

        items = page.locator("ion-router-outlet > .ion-page:last-child ion-item")
        count = items.count()

        for i in range(count):
            text = items.nth(i).inner_text().strip()
            if not text or "level" in text.lower() or "recent" in text.lower():
                continue
            lines = text.replace("\n", " ")
            parsed = _parse_version_text(lines)
            title = text.split("\n")[0].strip()
            guidelines.append({
                "title": title,
                "date": parsed.get("date", ""),
                "version": parsed.get("version", ""),
                "raw_text": lines,
            })

        browser.close()

    existing = _load_existing_versions(structured_dir)
    changed_ids: list[str] = []
    unchanged_count = 0

    for g in guidelines:
        key = g["title"].lower().strip()
        existing_version = existing.get(key, "")
        current_version_str = f"{g['date']} Version {g['version']}" if g.get("date") else ""
        if current_version_str and current_version_str != existing_version:
            safe_id = g["title"].replace("/", "_").replace(" ", "_").replace("\n", "_")[:50]
            changed_ids.append(safe_id)
        elif existing.get(key):
            unchanged_count += 1

    result = {
        "guidelines": guidelines,
        "changed_ids": changed_ids,
        "unchanged_count": unchanged_count,
        "total_count": len(guidelines),
    }

    output_path = os.path.join(output_dir, "discovery_metadata.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result
