#!/usr/bin/env python3
# standalone_utils/diagnostic/inspect_layout_nodes.py
"""
Bazaar Polymorphic Layout Node Inspector

This diagnostic utility analyzes offline HTML snapshot files inside the project's
request_responses/ directory. It automatically discovers all successful (status 200) 
response pools, verifies layout selector matrix stability, and aggregates parsing efficiency ratios.
"""

import os
import re
import glob
from bs4 import BeautifulSoup, Tag
from typing import Optional, Tuple


class LayoutInspector:
    """
    Evaluates raw document trees using structural cascading selectors to isolate, 
    parse, and classify item rows across variable front-end frameworks.
    """

    def _is_multisku_parent(self, item: Tag, title: str, raw_price_text: str) -> bool:
        """
        Evaluates listing metadata to identify and flag multi-variation items.
        """
        has_range = 'to' in raw_price_text.lower()
        has_variant = item.select_one(
            '.s-item__format-dynamic, .s-item__format-variants, [class*="format-variant"]'
        ) is not None
        
        known_models = ["5600X", "5700X", "5800X", "5900X", "5950X", "7800X3D"]
        matching_models = [m for m in known_models if m.lower() in title.lower()]
        
        return has_range or has_variant or len(matching_models) > 1

    def _extract_price(self, item: Tag, title: str) -> Optional[Tuple[float, bool]]:
        """
        Parses numeric pricing text metrics out of polymorphic card components.
        """
        price_elem = (
            item.select_one("span.s-card__price") or             # 🌟 High-specificity atomic leaf
            item.select_one(".s-card__price") or                 # General card fallback tier
            item.select_one(".s-item__price.POSITIVE") or        # Historic desktop green 'Sold' tag
            item.select_one(".s-item__price .POSITIVE") or       # Historic nested child variant
            item.select_one(".s-item__price") or                 # Base legacy wrapper fallback
            item.select_one("[class*='card__price']") or         # Wildcard structural safety net
            item.select_one("[class*='item__price']")            # Wildcard structural safety net
        )
        if not price_elem:
            return None

        raw_text = price_elem.get_text(" ", strip=True)
        is_msku_parent = self._is_multisku_parent(item, title, raw_text)

        if 'to' in raw_text.lower():
            raw_text = raw_text.lower().split('to')[0].strip()

        match = re.search(r'\d+(?:[.,]\d+)?', raw_text)
        if not match:
            return None

        digits = match.group(0)
        if ',' in digits and '.' not in digits:
            digits = digits.replace(',', '.')
        elif ',' in digits and '.' in digits:
            digits = digits.replace(',', '')

        try:
            val = float(digits)
            return (val, is_msku_parent) if val > 0 else None
        except ValueError:
            return None

    def scan_all_responses(self):
        """
        Discovers and processes all valid 200 status HTML files inside the request_responses payload directory.
        """
        # Determine the project root location relative to this utility script
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        target_dir = os.path.join(base_dir, "request_responses")
        
        # Target only valid HTML responses with a 200 HTTP response marker
        search_pattern = os.path.join(target_dir, "*_status_200.html")
        valid_files = sorted(glob.glob(search_pattern))

        if not valid_files:
            print(f"⚠️ No valid '_status_200.html' files found under tracking path: {target_dir}")
            return

        print(f"🔬 Bazaar Batch Processor: Found {len(valid_files)} valid payload snapshot files to evaluate.\n")
        print("=" * 90)

        global_hydrated = 0
        global_missing = 0
        global_msku = 0

        for file_path in valid_files:
            file_name = os.path.basename(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'html.parser')
            listings = soup.select(".srp-results .s-item, .srp-results .s-card, li.s-card, li.s-item")
            
            if not listings:
                results_container = soup.select_one("ul.srp-results, ol.srp-results")
                if results_container:
                    listings = results_container.find_all("li", recursive=False)

            file_hydrated = 0
            file_missing = 0
            file_msku = 0

            for item in listings:
                title_elem = (
                    item.select_one(".s-card__title") or 
                    item.select_one(".s-item__title") or
                    item.select_one("[class*='card__title']") or
                    item.select_one("[class*='item__title']")
                )
                if not title_elem:
                    continue

                title = title_elem.get_text(" ", strip=True)
                title = title.replace("New Listing", "").replace("Opens in a new window or tab", "").strip()

                price_data = self._extract_price(item, title)
                if price_data is None:
                    file_missing += 1
                    continue

                price, is_msku = price_data
                file_hydrated += 1
                if is_msku:
                    file_msku += 1

            # Print single-file metric output row
            print(f"📄 Snapshot: {file_name}")
            print(f"   ├─ Extracted Clean: {file_hydrated:4d} listings")
            print(f"   ├─ Missing Price:   {file_missing:4d} nodes")
            print(f"   └─ Multi-SKU Items: {file_msku:4d} entries")
            print("-" * 90)

            global_hydrated += file_hydrated
            global_missing += file_missing
            global_msku += file_msku

        print("\n📊 COMBINED GLOBAL PIPELINE REPORT:")
        print(f"   Total Successful Extractions:  {global_hydrated}")
        print(f"   Total Unresolvable Price DOMs: {global_missing}")
        print(f"   Total Multi-SKU Parents Found: {global_msku}")
        print(f"   Extraction Success Ratio:      {(global_hydrated / (global_hydrated + global_missing) * 100):.2f}%")
        print("=" * 90)


if __name__ == "__main__":
    inspector = LayoutInspector()
    inspector.scan_all_responses()