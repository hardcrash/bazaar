#!/usr/bin/env python3
# standalone_utils/diagnostic/scan_card_details.py
#
# Purpose: Deeply inspects and enumerates the DOM microstructure of a single listing card.
# Extracts internal tag paths, CSS classes, and selective string mappings (such as pricing currency tokens)
# from all valid raw offline snapshots to pinpoint precise data alignment vectors and identify
# structural dead-weight.

import os
import sys
import glob
from bs4 import BeautifulSoup
from loguru import logger

# --- Hardened Project Root Path Resolution ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = CURRENT_DIR
while PROJECT_ROOT and PROJECT_ROOT != os.path.dirname(PROJECT_ROOT):
    if os.path.exists(os.path.join(PROJECT_ROOT, "request_responses")):
        break
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)

TARGET_DIR = os.path.join(PROJECT_ROOT, "request_responses")
search_pattern = os.path.join(TARGET_DIR, "*_status_200.html")
html_files = glob.glob(search_pattern)

if not html_files:
    logger.critical(f"❌ No valid target snapshots found inside: {TARGET_DIR}/")
    sys.exit(1)

print("\n" + "=" * 80)
print(f"🔬 BAZAAR COMPONENT SCANNER (Found {len(html_files)} Valid Payload Snapshots)")
print("=" * 80)

for file_path in sorted(html_files):
    filename = os.path.basename(file_path)
    
    # Safety Check: Skip auth failure dumps that don't contain markup content
    if os.path.getsize(file_path) < 1000:
        logger.warning(f"⏩ Skipping {filename} (File footprint too small, likely an auth rejection).")
        continue

    logger.info(f"📖 Ingesting layout parameters from file: {filename}")
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # Target stream isolation selectors
    results_container = soup.select_one("ul.srp-results, ol.srp-results, div.srp-river-results")
    listings = results_container.find_all("li", recursive=False) if results_container else []

    if not listings:
        listings = soup.select("li.s-card")

    if not listings:
        logger.error(f"❌ Could not isolate listing wrappers inside {filename}.")
        print("-" * 80)
        continue

    # Isolate sample target row safely
    first_card = listings[0]
    logger.success(f"🎯 Targeted sample node row inside {filename}: <{first_card.name}> class={first_card.get('class')}")

    print("\n" + "-" * 80)
    print(f"--- 1. Testing Text Extractor Classes Inside Card ({filename}) ---")
    print("-" * 80)
    for elem in first_card.find_all(class_=True):
        text = " ".join(elem.get_text(strip=True).split())
        if text:
            display_text = f"'{text}'" if len(text) < 120 else f"'{text[:120]}...' [Truncated Wrapper]"
            print(f"Tag: <{elem.name:<4}> | Class: {str(elem.get('class')):<45} | Text: {display_text}")

    print("\n" + "-" * 80)
    print(f"--- 2. Direct Price Span Search ({filename}) ---")
    print("-" * 80)
    for span in first_card.find_all(['span', 'div', 'p']):
        txt = " ".join(span.get_text(strip=True).split())
        if '$' in txt and len(txt) < 40:
            print(f"🎯 Potential Price Match Tag: <{span.name:<4}> | Class: {str(span.get('class')):<45} | Text: '{txt}'")
    
    print("\n" + "=" * 80 + "\n")