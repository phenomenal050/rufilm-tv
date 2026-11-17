#!/usr/bin/env python3
"""Verify the exact injected Premium Cinema JS against the live catalog DOM."""
import base64, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

java = Path(sys.argv[1]).read_text(encoding="utf-8")
m = re.search(r'final String encoded\s*=\s*"([A-Za-z0-9+/=]+)"', java)
if not m:
    raise SystemExit("Premium JS payload not found in generated MainActivity.java")
payload = base64.b64decode(m.group(1)).decode("utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    # Third-party ad/media resources often stall page load; retain first-party scripts and images.
    page.route("**/*", lambda route: route.abort() if (
        route.request.resource_type in ("media", "font") or
        any(x in route.request.url.lower() for x in (
            "doubleclick.net", "googlesyndication.com", "google-analytics.com",
            "adservice.", " kaspi", "facebook.net", "hotjar.com"
        ))
    ) else route.continue_())
    try:
        page.goto("https://rufilmtv.tv/serials", wait_until="domcontentloaded", timeout=90000)
    except Exception as e:
        # DOMContentLoaded can be delayed by third-party scripts; still inspect a usable document.
        print("Navigation note:", str(e)[:300])
    page.wait_for_timeout(12000)
    if not page.locator("body").count():
        raise SystemExit("Site document did not become available")
    page.evaluate(payload)
    page.wait_for_timeout(2500)
    report = page.evaluate("window.__rfPremiumReport || null")
    print("LIVE DOM REPORT:", report)
    if not report or not report.get("style"):
        raise SystemExit("Premium stylesheet did not attach to live page")
    cards = report.get("cards") or {}
    if not cards.get("grid") or cards.get("cards", 0) < 3:
        raise SystemExit("Live DOM did not produce a 3-card grid: " + str(cards))
    computed = page.evaluate("""() => {
      const el=document.querySelector('.rf-premium-grid');
      if(!el) return null;
      const cs=getComputedStyle(el);
      return {display:cs.display,columns:cs.gridTemplateColumns.split(' ').length,
              items:el.querySelectorAll(':scope > .rf-premium-grid-item').length};
    }""")
    print("LIVE COMPUTED GRID:", computed)
    if not computed or computed["display"] != "grid" or computed["columns"] != 3 or computed["items"] < 3:
        raise SystemExit("Computed grid is not exactly 3 columns: " + str(computed))
    print("LIVE DOM/CSS CHECK PASSED")
    browser.close()
