#!/usr/bin/env python3
# standalone_utils/diagnostic/selector_test_runner.py

import os
import sys
import glob
from bs4 import BeautifulSoup
from loguru import logger

# --- Hardened Path Resolution ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = CURRENT_DIR
while PROJECT_ROOT and PROJECT_ROOT != os.path.dirname(PROJECT_ROOT):
    if os.path.exists(os.path.join(PROJECT_ROOT, "src")) and os.path.exists(os.path.join(PROJECT_ROOT, "config.yaml")):
        break
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.api.ebay.ebay_scrape_client import EbayScrapeClient

class DummyConfig:
    pass

try:
    client_instance = EbayScrapeClient(config=DummyConfig())
    EBAY_SELECTORS_MATRIX = client_instance.EBAY_SELECTORS_MATRIX
except AttributeError:
    logger.critical("❌ Could not pull EBAY_SELECTORS_MATRIX out of EbayScrapeClient. Verify it's defined!")
    sys.exit(1)

def run_selector_audit():
    target_dir = os.path.join(PROJECT_ROOT, "request_responses")
    search_pattern = os.path.join(target_dir, "*_status_200.html")
    html_files = glob.glob(search_pattern)

    if not html_files:
        logger.error(f"❌ No snapshots found inside: {target_dir}/")
        return

    print("\n" + "=" * 80)
    print("🔍 BAZAAR DECOUPLED SELECTOR MATRIX DEEP AUDIT")
    print("=" * 80 + "\n")

    for file_path in sorted(html_files):
        filename = os.path.basename(file_path)
        logger.info(f"📄 Snapshot: {filename}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        
        # --- 1. Container Audit ---
        print("\n  📦 CONTAINER DETECTION RUN:")
        print("  " + "-" * 40)
        active_containers = []
        for selector in EBAY_SELECTORS_MATRIX["containers"]:
            match_count = len(soup.select(selector))
            if match_count > 0:
                print(f"   ✅ [{selector:<30}] -> Found {match_count} element nodes.")
                active_containers.append((selector, match_count))
            else:
                print(f"   ❌ [{selector:<30}] -> 0 matches.")

        # --- 2. Independent Field Isolation Audit ---
        # Instead of nesting inside one container, we audit fields globally on the document
        # to see if the new structural components physically exist anywhere in the snapshot!
        print("\n  🔬 ELEMENT ALIGNMENT MATRIX (GLOBAL SNAPSHOT CHECK):")
        print("  " + "-" * 55)

        print("   -- Titles --")
        for t_sel in EBAY_SELECTORS_MATRIX["titles"]:
            hits = len(soup.select(t_sel))
            status = "✨ MATCH" if hits > 0 else "❌ MISS "
            print(f"    [{status}] Selector: [{t_sel:<35}] -> Total Hits: {hits}")

        print("\n   -- Prices --")
        for p_sel in EBAY_SELECTORS_MATRIX["prices"]:
            hits = len(soup.select(p_sel))
            status = "✨ MATCH" if hits > 0 else "❌ MISS "
            print(f"    [{status}] Selector: [{p_sel:<35}] -> Total Hits: {hits}")

        print("\n   -- Shipping --")
        for s_sel in EBAY_SELECTORS_MATRIX["shipping"]:
            hits = len(soup.select(s_sel))
            status = "✨ MATCH" if hits > 0 else "❌ MISS "
            print(f"    [{status}] Selector: [{s_sel:<35}] -> Total Hits: {hits}")

        print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    run_selector_audit()