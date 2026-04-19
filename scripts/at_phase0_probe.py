"""Phase 0 probe for Ambulance Tasmania CPG website.

Discovers content structure, auth requirements, and data format
for the AT Clinical Practice Guidelines site at cpg.ambulance.tas.gov.au.

Usage:
    python3 scripts/at_phase0_probe.py [output_dir]

Output:
    Writes phase0_findings.json and screenshots to output_dir
    (default: tmp/at-phase0).
"""

import json
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone


BASE_URL = "https://cpg.ambulance.tas.gov.au"


def run_probe(output_dir: Path) -> dict:
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)

    findings: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "probe_version": "3.0.0",
        "requests": [],
        "guidelines_sampled": [],
        "site_structure": {},
        "js_bundles": [],
        "data_endpoints": [],
    }

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

        def on_request(request):
            if request.url.endswith(".js") or ".js?" in request.url:
                findings["js_bundles"].append(
                    {"url": request.url, "resource_type": request.resource_type}
                )

        def on_response(response):
            rt = response.request.resource_type
            if rt in ("xhr", "fetch", "document"):
                try:
                    ct = response.headers.get("content-type", "")
                    findings["requests"].append({
                        "url": response.url,
                        "status": response.status,
                        "content_type": ct,
                        "resource_type": rt,
                    })
                    if "json" in ct or "api" in response.url.lower():
                        findings["data_endpoints"].append({
                            "url": response.url,
                            "status": response.status,
                            "content_type": ct,
                        })
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # ── 1. Load base page and dismiss all modals ────────────────
        print("[1/8] Loading base page ...")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        findings["site_structure"]["title"] = page.title()
        findings["site_structure"]["url_after_load"] = page.url
        html = page.content()
        findings["site_structure"]["html_size_bytes"] = len(html)
        findings["site_structure"]["framework_hints"] = {
            "has_angular": bool(page.query_selector("[ng-version]") or "ng-version" in html),
            "has_ionic": bool(page.query_selector("ion-app, ion-tabs, ion-tab-bar, ion-content")),
            "has_react": bool("__NEXT_DATA__" in html),
            "has_vue": bool("vue" in html.lower()),
        }
        meta_app_name = page.query_selector('meta[name="application-name"]')
        if meta_app_name:
            findings["site_structure"]["app_meta"] = meta_app_name.get_attribute("content")

        page.screenshot(path=str(output_dir / "01_home_raw.png"))

        # ── 2. Dismiss disclaimer modal ──────────────────────────────
        print("[2/8] Dismissing modals ...")
        _dismiss_all_modals(page)
        time.sleep(1)
        page.screenshot(path=str(output_dir / "02_after_dismiss.png"))

        findings["site_structure"]["home_content_after_dismiss"] = _extract_text(page)

        # ── 3. Select "Paramedic" level ──────────────────────────────
        print("[3/8] Selecting Paramedic level ...")
        _dismiss_all_modals(page)
        time.sleep(0.5)

        # Force-click "Paramedic" in the level selector
        try:
            paramedic_item = page.locator("ion-item:has-text('Paramedic')").last
            paramedic_item.click(force=True, timeout=5000)
            time.sleep(2)
            _dismiss_all_modals(page)
            time.sleep(1)
        except Exception as e:
            print(f"  -> Paramedic selection attempt: {e}")

        page.screenshot(path=str(output_dir / "03_paramedic_selected.png"))

        # ── 4. Navigate to Adult Patient Guidelines ──────────────────
        print("[4/8] Navigating to Adult Patient Guidelines ...")
        _dismiss_all_modals(page)
        try:
            adult_btn = page.locator("text=Adult Patient Guidelines").first
            adult_btn.click(force=True, timeout=5000)
            time.sleep(3)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.screenshot(path=str(output_dir / "04_adult_guidelines.png"))
            findings["site_structure"]["adult_guidelines"] = {
                "url": page.url,
                "title": page.title(),
                "content": _extract_text(page),
            }
            print(f"  -> URL: {page.url}")
        except Exception as e:
            # Try navigating directly
            print(f"  -> Click failed: {e}")
            print("  -> Trying direct navigation ...")
            try:
                page.evaluate("document.querySelectorAll('ion-modal').forEach(m => m.remove())")
                page.goto(f"{BASE_URL}/tabs/guidelines", wait_until="networkidle", timeout=30000)
                time.sleep(2)
                _dismiss_all_modals(page)
                adult_btn = page.locator("text=Adult Patient Guidelines").first
                adult_btn.click(force=True, timeout=5000)
                time.sleep(3)
                page.screenshot(path=str(output_dir / "04_adult_guidelines.png"))
                findings["site_structure"]["adult_guidelines"] = {
                    "url": page.url,
                    "title": page.title(),
                    "content": _extract_text(page),
                }
                print(f"  -> URL (retry): {page.url}")
            except Exception as e2:
                findings["site_structure"]["adult_guidelines_error"] = str(e2)
                print(f"  -> Retry also failed: {e2}")

        # ── 5. Click into specific guidelines ────────────────────────
        print("[5/8] Exploring individual guidelines ...")
        _dismiss_all_modals(page)
        guideline_items = _get_clickable_items(page)
        findings["site_structure"]["guideline_list_items"] = guideline_items
        print(f"  -> Found {len(guideline_items)} guideline items")

        # Try to click the first real-looking guideline
        for item in guideline_items:
            text = item["text"].lower()
            if any(kw in text for kw in ["cardiac", "anaphylaxis", "respiratory", "chest", "arrest"]):
                try:
                    loc = page.locator(f"ion-item:has-text('{item['text'].split(chr(10))[0]}')").first
                    loc.click(force=True, timeout=5000)
                    time.sleep(3)
                    page.wait_for_load_state("networkidle", timeout=15000)
                    page.screenshot(path=str(output_dir / "05_specific_guideline.png"))
                    content = _extract_text(page)
                    findings["site_structure"]["specific_guideline"] = {
                        "name": item["text"],
                        "url": page.url,
                        "title": page.title(),
                        "content": content,
                    }
                    print(f"  -> Opened: {item['text'][:60]}")
                    print(f"  -> URL: {page.url}")
                    break
                except Exception as e:
                    print(f"  -> Could not open {item['text'][:40]}: {e}")

        # ── 6. Check Medicines tab and click a medicine ──────────────
        print("[6/8] Checking Medicines tab ...")
        try:
            page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            time.sleep(1)
            _dismiss_all_modals(page)
            time.sleep(0.5)

            # Navigate via URL to medicines tab
            page.goto(f"{BASE_URL}/tabs/medicines", wait_until="networkidle", timeout=30000)
            time.sleep(2)
            _dismiss_all_modals(page)
            page.screenshot(path=str(output_dir / "06_medicines.png"))

            medicines_content = _extract_text(page)
            findings["site_structure"]["medicines_tab"] = {
                "url": page.url,
                "title": page.title(),
                "content": medicines_content,
            }

            # Click on Adrenaline
            try:
                adr = page.locator("ion-item:has-text('Adrenaline')").first
                adr.click(force=True, timeout=5000)
                time.sleep(3)
                page.wait_for_load_state("networkidle", timeout=15000)
                page.screenshot(path=str(output_dir / "06b_adrenaline.png"))
                findings["site_structure"]["adrenaline_medicine"] = {
                    "url": page.url,
                    "title": page.title(),
                    "content": _extract_text(page),
                }
                print(f"  -> Adrenaline URL: {page.url}")
            except Exception as e:
                print(f"  -> Could not click Adrenaline: {e}")
        except Exception as e:
            findings["site_structure"]["medicines_error"] = str(e)
            print(f"  -> ERROR: {e}")

        # ── 7. Check Calculators tab ─────────────────────────────────
        print("[7/8] Checking Calculators tab ...")
        try:
            page.goto(f"{BASE_URL}/tabs/calculators", wait_until="networkidle", timeout=30000)
            time.sleep(2)
            _dismiss_all_modals(page)
            page.screenshot(path=str(output_dir / "07_calculators.png"))
            findings["site_structure"]["calculators_tab"] = {
                "url": page.url,
                "title": page.title(),
                "content": _extract_text(page),
            }
        except Exception as e:
            findings["site_structure"]["calculators_error"] = str(e)

        # ── 8. Analyse JS bundles for data patterns ──────────────────
        print("[8/8] Analysing JS bundles ...")
        findings["js_bundles"] = _deduplicate_bundles(findings["js_bundles"])
        print(f"  -> Found {len(findings['js_bundles'])} unique JS bundles")

        # Analyse common bundle for data patterns
        _analyse_bundle(findings, "common", output_dir)
        _analyse_bundle(findings, "main", output_dir)

        browser.close()

    _save(findings, output_dir)
    return findings


def _dismiss_all_modals(page) -> None:
    """Force-dismiss all Ionic modals via DOM removal + OK clicks."""
    # Try clicking OK on disclaimer first
    try:
        ok_btn = page.locator("button:has-text('OK')").first
        if ok_btn.is_visible(timeout=1000):
            ok_btn.click(force=True, timeout=2000)
            time.sleep(0.5)
    except Exception:
        pass

    # Force-remove all ion-modal overlays from the DOM
    try:
        page.evaluate("""
            document.querySelectorAll('ion-modal').forEach(m => {
                m.style.display = 'none';
                m.remove();
            });
            // Also remove any backdrop overlays
            document.querySelectorAll('.ion-overlay-hidden, ion-backdrop').forEach(b => {
                b.style.display = 'none';
                b.remove();
            });
        """)
    except Exception:
        pass


def _extract_text(page) -> str:
    """Extract visible text content."""
    try:
        return (page.inner_text("body") or "")[:5000]
    except Exception:
        return ""


def _get_clickable_items(page) -> list[dict]:
    """Get all ion-item elements with their text."""
    items = []
    try:
        elements = page.query_selector_all("ion-item")
        for el in elements[:50]:
            text = (el.inner_text() or "").strip()
            if text and len(text) < 200:
                items.append({"text": text})
    except Exception:
        pass
    return items


def _analyse_bundle(findings: dict, bundle_name: str, output_dir: Path) -> None:
    """Download and analyse a named JS bundle for data patterns."""
    import urllib.request

    target_url = None
    for b in findings.get("js_bundles", []):
        url = b["url"]
        if bundle_name in url and not any(
            x in url for x in ["common"] if bundle_name == "main"
        ):
            target_url = url
            break
        if bundle_name == "common" and "common" in url:
            target_url = url
            break

    if not target_url:
        print(f"  -> No {bundle_name} bundle found")
        return

    try:
        resp = urllib.request.urlopen(target_url, timeout=60)
        data = resp.read()
        text = data.decode("utf-8", errors="replace")

        analysis = {
            "url": target_url,
            "size_bytes": len(data),
            "size_mb": round(len(data) / 1024 / 1024, 2),
        }

        # Data pattern checks
        patterns = {
            "has_guideline_text": "guideline",
            "has_dose_tables": "dose",
            "has_medication_names": "adrenaline",
            "has_flowchart_refs": "flowchart",
            "has_cognito": "Cognito",
            "has_firebase": "firebase",
            "has_firestore": "firestore",
            "has_auth_guard": "canActivate",
            "has_scope_of_practice": "scope of practice",
            "has_qualification_levels": "Volunteer Ambulance Officer",
        }

        for key, pattern in patterns.items():
            analysis[key] = pattern.lower() in text.lower()

        # Look for CPG number patterns (e.g. CPG D002, CPG 1.1)
        cpg_refs = re.findall(r"CPG\s+[A-Z]?\d{1,4}", text)
        analysis["cpg_number_count"] = len(set(cpg_refs))
        analysis["cpg_number_samples"] = sorted(set(cpg_refs))[:20]

        # Look for medicine/ingredient patterns
        med_names = re.findall(
            r"(?:Adrenaline|Amiodarone|Morphine|Fentanyl|Midazolam|Ketamine|"
            r"Salbutamol|Glucose|Aspirin|Clopidogrel|Tranexamic Acid|"
            r"Diazepam|Droperidol|Enoxaparin|Heparin|Ibuprofen|"
            r"Methoxyflurane|Ondansetron|Paracetamol|Tenecteplase|"
            r"Naloxone|Atropine|Adenosine|Oxytocin|Ceftriaxone|"
            r"Dexamethasone|Prochlorperazine|Lignocaine|Frusemide|"
            r"Magnesium Sulphate|Ergometrine|Glucagon|Normal saline|"
            r"Sodium Bicarbonate|Ipratropium|Glyceryl Trinitrate|Oxygen)",
            text, re.IGNORECASE
        )
        analysis["medicine_name_count"] = len(med_names)
        analysis["medicine_names_unique"] = sorted(set(med_names))[:40]

        # Look for URL routing patterns
        routes = re.findall(r"path:\s*['\"]([^'\"]+)['\"]", text)
        analysis["route_count"] = len(routes)
        analysis["route_samples"] = routes[:30]

        findings["site_structure"][f"{bundle_name}_bundle_analysis"] = analysis

        print(f"  -> {bundle_name}: {analysis['size_mb']}MB")
        print(f"     CPG numbers found: {analysis['cpg_number_count']}")
        print(f"     Medicine names: {analysis['medicine_name_count']}")
        print(f"     Routes found: {analysis['route_count']}")
        if analysis["cpg_number_samples"]:
            print(f"     CPG samples: {analysis['cpg_number_samples']}")
        if analysis["route_samples"]:
            print(f"     Route samples: {analysis['route_samples']}")

    except Exception as e:
        print(f"  -> Error analysing {bundle_name}: {e}")


def _deduplicate_bundles(bundles: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for b in bundles:
        url = b.get("url", "")
        if url not in seen:
            seen.add(url)
            result.append(b)
    return result


def _save(findings: dict, output_dir: Path) -> None:
    output_file = output_dir / "phase0_findings.json"
    output_file.write_text(json.dumps(findings, indent=2, ensure_ascii=False))
    print(f"\nFindings saved to {output_file}")


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tmp/at-phase0")
    run_probe(output)
