import requests
import logging
from bs4 import BeautifulSoup
from typing import List, Optional
import urllib.parse
import time
import random
import re
import json
from copy import deepcopy
from src.core.models import MarketItem
from src.analysis.strategy.cpu_strategy import CPUStrategy

logger = logging.getLogger("BazaarPipeline")

class EbayScrapeClient:
    def __init__(self, config):
        self.config = config
        import os
        import yaml

        global_cfg = {}
        if hasattr(config, 'params') and isinstance(config.params, dict):
            global_cfg = config.params.get("global_params", {})

        if not global_cfg or not global_cfg.get("scrapeops_api_key"):
            try:
                possible_paths = ['config.yaml', 'config/config.yaml', '../config.yaml']
                for path in possible_paths:
                    if os.path.exists(path):
                        with open(path, 'r') as f:
                            raw_yaml = yaml.safe_load(f)
                            if raw_yaml and "global_params" in raw_yaml:
                                global_cfg = raw_yaml["global_params"]
                                break
                            elif raw_yaml:
                                global_cfg = raw_yaml
            except Exception as e:
                print(f"[⚠️] Could not read config.yaml from disk: {e}")

        self.provider = str(global_cfg.get("active_scraper_proxy", "scrapeops")).lower()
        self.scrapeops_key = str(global_cfg.get("scrapeops_api_key", "")).strip()
        self.scraperapi_key = str(global_cfg.get("scraperapi_key", "")).strip()
        self.timeout = int(global_cfg.get("api_timeout_seconds", 20))

        print("\n=== 🛠️ PIPELINE PROXY CONFIG DEBUG ===")
        print(f" Detected Provider : {self.provider.upper()}")
        print(f" ScrapeOps Key     : {self.scrapeops_key[:5] + '...' if len(self.scrapeops_key) > 5 else '❌ MISSING'}")
        print(f" ScraperAPI Key    : {self.scraperapi_key[:5] + '...' if len(self.scraperapi_key) > 5 else '❌ MISSING'}")
        print("=======================================\n")

    def search_historical_sales(self, query: str, min_price: float, max_price: float, category_id: str, model_name: str, strategy: CPUStrategy) -> List[MarketItem]:
        cleaned_query = " ".join(query.split())
        encoded_query = requests.utils.quote(cleaned_query)

        target_ebay_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1&_ipg=100&_sop=13"
        if category_id and str(category_id).lower() != "global root":
            target_ebay_url += f"&_sacat={category_id}"

        target_ebay_url += f"&_udlo={min_price}&_udhi={max_price}"

        if self.provider == "scraperapi":
            gateway_url = "http://api.scraperapi.com"
            cache_buster_url = f"{target_ebay_url}&cb={int(time.time() * 1000)}{random.randint(100,999)}"

            payload = {
                "api_key": self.scraperapi_key,
                "url": cache_buster_url,
                "keep_headers": "false",
                "render": "true",
                "skip_cache": "true",
                "wait_for_selector": ".srp-results, .s-card--horizontal"
            }
        else:
            gateway_url = "https://proxy.scrapeops.io/v1/"
            safe_target_url = urllib.parse.quote_plus(target_ebay_url)

            payload = {
                "api_key": self.scrapeops_key,
                "url": safe_target_url,
                "bypass": "cloudflare_imperva",
                "render_js": "true",
                "residential": "true",
                "wait_for_selector": ".s-card--horizontal"
            }
        try:
            token_preview = self.scraperapi_key[:6] if self.provider == "scraperapi" else self.scrapeops_key[:6]
            print(f"[🕷️] Dispatching sweep via [{self.provider.upper()}] | Token: {token_preview}...")

            if self.provider == "scraperapi":
                payload["keep_headers"] = "false"

            response = requests.get(gateway_url, params=payload, timeout=self.timeout)

            if response.status_code == 200:
                return self._parse_ebay_html(
                    html_content=response.text,
                    model_name=model_name,
                    category=category_id,
                    is_sold=True,
                    strategy=strategy
                )
            else:
                print(f"  ❌ Proxy failure token block. Status code: {response.status_code}")
                return []

        except Exception as e:
            print(f"[❌] Exception triggered during execution pipeline loop: {e}")
            return []

    def _parse_ebay_html(self, html_content: str, model_name: str, category: str, is_sold: bool, strategy: CPUStrategy) -> List[MarketItem]:
        soup = BeautifulSoup(html_content, "html.parser")
        item_summaries = []

        page_text = soup.get_text()
        if any(x in page_text.lower() for x in ["please verify you are a human", "security check", "robot"]):
            print("  ⚠️  [BLOCK] Warning: Proxy exit node hit an eBay verification wall page.")
            return []

        listings = soup.find_all(lambda tag: tag.name in ['li', 'div'] and tag.has_attr('class') and any(
            cls in tag.get('class', []) for cls in ['s-item', 's-card--horizontal', 'srp-results__item', 's-item__wrapper']
        ))

        for idx, listing in enumerate(listings):
            if any(cls in listing.get("class", []) for cls in ["s-item__pl-on-bottom", "s-item-placeholder"]):
                continue

            title_ele = listing.find(class_=lambda c: c and any(x in c for x in ["s-item__title", "card__title", "item__title"])) or \
                        listing.find("h3") or \
                        listing.find("span", role="heading")

            if not title_ele:
                continue

            raw_title = title_ele.text.strip()
            title_clean = strategy.clean_title(raw_title)

            if "Shop on eBay" in title_clean or not title_clean:
                continue

            status = strategy.is_valid(title_clean, target_model=model_name)

            if status == "INVALID":
                print(f"     [Parser Drop #{idx}] Strategy Rejected -> '{title_clean}'")
                continue

            price_ele = listing.find(class_=lambda c: c and any(x in c for x in ["s-item__price", "card__price", "item__price"])) or \
                        listing.find("span", class_="s-item__price")

            if not price_ele:
                continue

            raw_price_text = price_ele.text.strip()
            price_str = "".join(c for c in raw_price_text if c.isdigit() or c == ".")
            if "to" in price_str.lower():
                price_str = price_str.lower().split("to")[0].strip()

            try:
                price_val = float(price_str) if price_str else 0.0
            except ValueError:
                continue

            if price_val == 0.0:
                continue

            id_ele = listing.find("a", class_=lambda c: c and any(x in c for x in ["s-item__link", "card__link"])) or \
                     listing.find("a", href=True)
            item_url = id_ele["href"] if (id_ele and id_ele.has_attr("href")) else None

            item_id = "0"
            if item_url and "/itm/" in item_url:
                item_id = item_url.split("/itm/")[-1].split("?")[0]

            if status == "MSKU":
                current_state = "PENDING_DEEP_HARVEST"
                print(f"     [Parser Flag] Found Multi-Variation Menu -> '{title_clean}' | Tagged: {current_state}")
            else:
                current_state = "PENDING"
                print(f"     [Parser Accept] Strategy Verified MarketItem: '{title_clean}' | ${price_val}")

            market_item = MarketItem(
                item_id=item_id, model_name=model_name, category=category,
                raw_title=raw_title, title=title_clean, price=price_val,
                shipping_cost=0.0, total_cost=price_val, currency="USD",
                condition_id=3000, is_sold=is_sold, source_platform="ebay",
                item_url=item_url, process_state=current_state
            )
            item_summaries.append(market_item)

        return item_summaries

    def parse_msku_item_page(self, html_content: str, base_item) -> list:
        extracted_variants = []
        html_upper = html_content.upper()

        feedback_score = None
        fb_match = re.search(r'feedbackScore"\s*:\s*(\d+)', html_content)
        if fb_match:
            feedback_score = int(fb_match.group(1))

        feedback_pct = None
        fbp_match = re.search(r'positiveFeedbackPercent"\s*:\s*([\d\.]+)', html_content)
        if fbp_match:
            feedback_pct = float(fbp_match.group(1))

        is_top_rated = "TOP-RATED SELLER" in html_upper or "TOP_RATED_SELLER" in html_upper
        has_bent_pins = any(x in html_upper for x in ["BENT PIN", "BROKEN PIN", "DAMAGED PIN", "MISSING PIN"])

        start_match = re.search(r'"MSKU"\s*:\s*\{', html_content)
        if not start_match:
            print(f"      [⚠️] Error: Could not locate 'MSKU' schema block anchor on item {base_item.item_id}.")
            return []

        start_idx = start_match.end() - 1
        bracket_count = 0
        json_str = ""

    def fetch_raw_item_page(self, item_url: str) -> str:
        payload = {
            "api_key": self.scraperapi_key,
            "url": item_url
        }

        print(f"      [🕷] Fetching deep landing page via ScraperAPI...")
        try:
            response = requests.get("https://api.scraperapi.com/", params=payload, timeout=30)
            if response.status_code == 200:
                return response.text
            else:
                print(f"      ❌ ScraperAPI returned status code: {response.status_code}")
                return ""
        except Exception as e:
            print(f"      ❌ Exception occurred during page proxy request: {e}")
            return ""
