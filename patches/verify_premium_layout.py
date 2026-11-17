#!/usr/bin/env python3
"""Run the exact embedded Premium Cinema script against the live RuFilmTV DOM."""
import base64
import re
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

java_path = Path(sys.argv[1])
source = java_path.read_text(encoding="utf-8")
match = re.search(r'final String encoded = "([A-Za-z0-9+/=]+)";', source)
if not match:
    raise SystemExit("Could not find embedded Premium layout payload in generated MainActivity.java")
payload = base64.b64decode(match.group(1)).decode("utf-8")

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(options=options)
try:
    driver.set_page_load_timeout(45)
    driver.get("https://rufilmtv.tv/serials")
    time.sleep(6)
    driver.execute_script(payload)
    time.sleep(2)
    report = driver.execute_script("return window.__rfPremiumReport || null")
    if not report:
        raise SystemExit("Premium script ran but did not publish a DOM report")
    print("LIVE DOM REPORT:", report)
    if not report.get("style"):
        raise SystemExit("Premium stylesheet was not attached to the live document")
    cards = report.get("cards") or {}
    if not cards.get("grid") or cards.get("cards", 0) < 3:
        raise SystemExit("Live catalog was not converted into a 3+ card grid: " + str(cards))
    computed = driver.execute_script("""
      const el=document.querySelector('.rf-premium-grid');
      if(!el) return null;
      return {display:getComputedStyle(el).display,
              columns:getComputedStyle(el).gridTemplateColumns.split(' ').length,
              directItems:el.querySelectorAll(':scope > .rf-premium-grid-item').length};
    """)
    print("LIVE GRID COMPUTED STYLE:", computed)
    if not computed or computed["display"] != "grid" or computed["columns"] != 3:
        raise SystemExit("Live CSS grid is not exactly three columns: " + str(computed))
    print("LIVE DOM/CSS CHECK PASSED")
finally:
    driver.quit()
