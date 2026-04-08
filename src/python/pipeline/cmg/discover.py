"""
Stage 1: Playwright SPA crawler for ACTAS CMGs
Because the CMGs are compiled Angular components, we actively crawl the DOM.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
try:
    from playwright.sync_api import sync_playwright, TimeoutError
except ImportError:  # pragma: no cover — playwright is an optional scraping dependency
    sync_playwright = None  # type: ignore[assignment]
    TimeoutError = Exception  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

def discover(url: str = "https://cmg.ambulance.act.gov.au/tabs/guidelines", output_dir: str = "data/cmgs/raw") -> str:
    """Run Playwright to crawl the SPA and save raw guideline HTML outputs."""
    if sync_playwright is None:
        raise ImportError("playwright is required for CMG scraping. Install with: pip install studybot-backend[scraping]")
    os.makedirs(output_dir, exist_ok=True)
    
    crawled_cmgs = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        logger.info(f"Navigating to {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Dismiss disclaimer
            logger.info("Waiting for disclaimer modal...")
            try:
                page.wait_for_selector("app-disclaimer ion-button", state="visible", timeout=10000)
                page.locator("app-disclaimer ion-button").filter(has_text="OK").click()
                logger.info("Disclaimer dismissed.")
            except TimeoutError:
                logger.warning("No disclaimer found or timed out.")

            # Select Level (Modal 2)
            logger.info("Waiting for Level Selection modal...")
            try:
                page.wait_for_selector("ion-modal ion-item", state="visible", timeout=5000)
                page.locator("ion-modal ion-item").filter(has_text="Intensive Care Paramedic").click()
                logger.info("Level Selected: Intensive Care Paramedic.")
            except TimeoutError:
                logger.warning("No level selection modal found.")
                
            logger.info("Waiting for all modals to be hidden...")
            page.wait_for_selector("ion-modal", state="hidden", timeout=10000)
            time.sleep(2) # Give ionic extra time to clear overlay

            # Wait for list to load
            page.wait_for_selector("ion-router-outlet > .ion-page:last-child ion-item", state="visible", timeout=10000)
            
            # Extract category text so we can loop and click by text
            # Ignore purely navigational or disabled ones
            time.sleep(1) # wait for ionic animation
            
            categories_locators = page.locator("ion-router-outlet > .ion-page:last-child ion-item")
            num_categories = categories_locators.count()
            cat_names = []
            for i in range(num_categories):
                cat_names.append(categories_locators.nth(i).inner_text().replace('\\n', ' ').strip())
                
            logger.info(f"Found {len(cat_names)} categories: {cat_names}")
            
            for cat_name in cat_names:
                # Some items might be empty or dividers
                if not cat_name or "level" in cat_name.lower() or "recent" in cat_name.lower():
                    continue
                    
                logger.info(f"Loading category: {cat_name}")
                # We do a fresh click on the category
                page.locator("ion-router-outlet > .ion-page:last-child ion-item").filter(has_text=cat_name).first.click(force=True)
                time.sleep(1) # transition
                
                # Wait for CMG list inside category
                try:
                    page.wait_for_selector("ion-router-outlet > .ion-page:last-child ion-item", state="visible", timeout=5000)
                    cmg_locators = page.locator("ion-router-outlet > .ion-page:last-child ion-item")
                    num_cmgs = cmg_locators.count()
                    
                    # Store exact texts so we can click by text inside this category
                    cmg_texts = []
                    for i in range(num_cmgs):
                        t = cmg_locators.nth(i).inner_text().strip()
                        if t:
                            cmg_texts.append(t)
                    
                    logger.info(f"  Found {len(cmg_texts)} CMGs in '{cat_name}'")
                    
                    for cmg_name in cmg_texts:
                        logger.info(f"    Extracting CMG: {cmg_name.replace('\\n', ' ')}")
                        
                        # Click the specific CMG
                        page.locator("ion-router-outlet > .ion-page:last-child ion-item").filter(has_text=cmg_name).first.click(force=True)
                        time.sleep(1)
                        
                        # Wait for the content to render
                        try:
                            page.wait_for_selector("ion-content.guideline-content", state="visible", timeout=5000)
                            content_html = page.locator("ion-content.guideline-content").inner_html()
                            content_text = page.locator("ion-content.guideline-content").inner_text()
                            
                            title_safe = cmg_name.replace('/', '_').replace(' ', '_').replace('\\n', '_')[:50]
                            filepath = os.path.join(output_dir, f"{title_safe}.json")
                            with open(filepath, "w", encoding="utf-8") as f:
                                json.dump({
                                    "cmg_title": cmg_name.replace('\\n', ' '),
                                    "category": cat_name,
                                    "html": content_html,
                                    "text": content_text,
                                    "extracted_at": datetime.now(timezone.utc).isoformat()
                                }, f, indent=2)
                            
                            crawled_cmgs.append(cmg_name)
                            logger.info(f"    Saved: {filepath}")
                            
                        except TimeoutError:
                            logger.warning(f"    Timeout waiting for content of {cmg_name}")
                            
                        # Navigate back to CMG list
                        # Ionic has an ion-back-button
                        try:
                            # wait for ripple to finish so it's clickable
                            time.sleep(0.5) 
                            page.locator("ion-back-button").first.click(force=True)
                            time.sleep(1)
                        except Exception as e:
                            logger.warning(f"    Back button failed: {e}. Trying page.go_back()")
                            page.go_back()
                            time.sleep(1)
                            
                except TimeoutError:
                    logger.warning(f"No CMGs found in category {cat_name}")
                    
                # Back to root category list
                try:
                    time.sleep(0.5)
                    page.locator("ion-back-button").first.click()
                    time.sleep(1)
                except Exception as e:
                    page.go_back()
                    time.sleep(1)
                
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            
        finally:
            browser.close()
            
    # Write summary
    summary_file = os.path.join(output_dir, "discovery_summary.json")
    with open(summary_file, "w") as f:
        json.dump({
            "status": "success",
            "extracted_count": len(crawled_cmgs),
            "cmgs": crawled_cmgs
        }, f, indent=2)
        
    return summary_file

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    discover()
