import os
import re
import yaml
import time
import random
import urllib.parse
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from loguru import logger

from src.core.models import MarketItem
from src.analysis.strategy.cpu_strategy import BaseCPUStrategy

class EbayScrapeClient:
    def __init__(self, config, min_wait: float = 2.0, max_wait: float = 5.0):
        self.config = config
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.last_request_time = 0.0

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
                logger.warning(f"Could not read alternative credentials config from disk: {e}")

        self.provider = str(global_cfg.get("active_scraper_proxy", "scrapeops")).lower()
        self.scrapeops_key = str(global_cfg.get("scrapeops_api_key", "")).strip()
        self.scraperapi_key = str(global_cfg.get("scraperapi_key", "")).strip()
        self.timeout = int(global_cfg.get("api_timeout_seconds", 20))

        logger.info(f"EbayScrapeClient router mapped successfully to provider edge: {self.provider.upper()}")

    def _enforce_politeness(self):
        """Ensures a minimum gap between requests with random jitter to prevent detection."""
        elapsed = time.perf_counter() - self.last_request_time
        if elapsed < self.min_wait:
            jitter = random.uniform(0, self.max_wait - self.min_wait)
            sleep_time = (self.min_wait - elapsed) + jitter
            logger.debug(f"Politeness lock active. Throttling gateway call for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.perf_counter()

    def search_historical_sales(self, query: str, min_price: float, max_price: float, category_id: str, model_name: str, strategy: BaseCPUStrategy) -> List[MarketItem]:
        self._enforce_politeness()

        cleaned_query = " ".join(query.split())
        encoded_query = requests.utils.quote(cleaned_query)

        target_ebay_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1&_ipg=100&_sop=13"
        if category_id and str(category_id).lower() != "global root":
            target_ebay_url += f"&_sacat={category_id}"
        target_ebay_url += f"&_udlo={min_price}&_udhi={max_price}"

        if self.provider == "scraperapi":
            gateway_url = "http://api.scraperapi.com"
            payload = {
                "api_key": self.scraperapi_key,
                "url": f"{target_ebay_url}&cb={int(time.time() * 1000)}",
                "keep_headers": "false",
                "render": "true",
                "skip_cache": "true",
                "wait_for_selector": ".srp-results, .s-card--horizontal"
            }
        else:
            gateway_url = "https://proxy.scrapeops.io/v1/"
            payload = {
                "api_key": self.scrapeops_key,
                "url": urllib.parse.quote_plus(target_ebay_url),
                "bypass": "cloudflare_imperva",
                "render_js": "true",
                "residential": "true",
                "wait_for_selector": ".s-card--horizontal"
            }

        try:
            logger.debug(f"Dispatching API remote gateway call payload to {gateway_url}")
            response = requests.get(gateway_url, params=payload, timeout=self.timeout)
            if response.status_code == 200:
                return self._parse_ebay_html(response.text, model_name, category_id, True, strategy)

            logger.error(f"Gateway proxy rejection status code returned: {response.status_code}")
            return []
        except Exception as e:
            logger.exception("Catastrophic connection breakout during remote scraping request")
            return []

    def _parse_ebay_html(self, html_content: str, model_name: str, category: str, is_sold: bool, strategy: BaseCPUStrategy) -> List[MarketItem]:
        soup = BeautifulSoup(html_content, "html.parser")
        item_summaries = []

        listings = soup.find_all(lambda tag: tag.name in ['li', 'div'] and tag.has_attr('class') and any(
            cls in tag.get('class', []) for cls in ['s-item', 's-card--horizontal']
        ))

        for listing in listings:
            title_ele = listing.find(class_=lambda c: c and any(x in c for x in ["s-item__title", "card__title"]))
            if not title_ele:
                continue

            raw_title = title_ele.text.strip()
            title_clean = strategy.clean_title(raw_title)

            status = strategy.is_valid(title_clean, target_model=model_name)
            if status == "INVALID":
                continue

            price_ele = listing.find(class_=lambda c: c and any(x in c for x in ["s-item__price", "card__price"]))
            if not price_ele:
                continue

            price_str = "".join(c for c in price_ele.text.strip() if c.isdigit() or c == ".")
            try:
                price_val = float(price_str)
            except ValueError:
                continue

            item_url = listing.find("a", href=True)["href"] if listing.find("a", href=True) else None
            item_id = item_url.split("/itm/")[-1].split("?")[0] if item_url and "/itm/" in item_url else "0"

            item_summaries.append(MarketItem(
                item_id=item_id,
                model_name=model_name,
                category=category,
                raw_title=raw_title,
                title=title_clean,
                price=price_val,
                shipping_cost=0.0,
                total_cost=price_val,
                currency="USD",
                condition_id=3000,
                is_sold=is_sold,
                source_platform="ebay",
                item_url=item_url,
                process_state="PENDING_DEEP_HARVEST" if status == "MSKU" else "PENDING"
            ))

            logger.debug(f"    [Parser Accept] Strategy Verified MarketItem: '{title_clean}' | ${price_val}")

        logger.info(f"Parser validation round closed. Extracted {len(item_summaries)} raw records for pattern: {model_name}")
        return item_summaries

    def fetch_raw_item_page(self, item_url: str, max_retries: int = 3) -> str:
        self._enforce_politeness()
        payload = {"api_key": self.scraperapi_key, "url": item_url}

        for attempt in range(max_retries):
            try:
                response = requests.get("https://api.scraperapi.com/", params=payload, timeout=30)
                if response.status_code == 200:
                    return response.text
                else:
                    logger.warning(f"Deep Harvest deep connection attempt [{attempt+1}/{max_retries}] failed with status: {response.status_code}")
            except Exception as e:
                logger.error(f"Deep Harvest connection error exception on step [{attempt+1}/{max_retries}]: {e}")

            time.sleep(1)

        logger.error(f"Deep Harvest extraction pool failure exhaustion for endpoint target: {item_url}")
        return ""

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
        start_match = re.search(r'"MSKU"\s*:\s*\{', html_content)

        if not start_match:
            logger.warning(f"  [⚠️] Multi-SKU Schema Exception: Missing block anchor on listing element ID: {base_item.item_id}")
            return []

        start_idx = start_match.end() - 1
        bracket_count = 0
        json_str = ""

        # Complete the bracket-matching scan loop to safely isolate the JSON block
        for i in range(start_idx, len(html_content)):
            char = html_content[i]
            json_str += char
            if char == "{":
                bracket_count += 1
            elif char == "}":
                bracket_count -= 1
                if bracket_count == 0:
                    break

        return extracted_variants
