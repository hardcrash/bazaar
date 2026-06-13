import json
import random
import re
import os
import time
from typing import List, Optional, Dict, Any, Tuple
import requests
from bs4 import BeautifulSoup
from loguru import logger

from src.core.models import MarketItem
from src.analysis.strategy.cpu_strategy import BaseCPUStrategy

class EbayScrapeClient:
    def __init__(self, config):
        """Initializes the eBay Scraping Client with credit-aware runtime weighting properties."""
        self.config = config
        if isinstance(config, dict):
            self.timeout = config.get("api_timeout_seconds", 30)
        else:
            self.timeout = getattr(config, "api_timeout_seconds", 30)

        self.last_request_time = time.perf_counter() - 10.0
        self.min_wait = 1.0
        self.max_wait = 3.0

        self._runtime_credits: Dict[str, int] = {
            "scraperapi": 5000,
            "scrapeops": 1000,
            "zenrows": 1000
        }
        self.refresh_account_balances()

    def _enforce_politeness(self):
        """Ensures a minimum gap between requests with random jitter."""
        elapsed = time.perf_counter() - self.last_request_time
        if elapsed < self.min_wait:
            jitter = random.uniform(0, self.max_wait - self.min_wait)
            sleep_time = (self.min_wait - elapsed) + jitter
            logger.debug(f"Politeness lock active. Throttling gateway call for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.perf_counter()

    def refresh_account_balances(self):
        """Queries proxy billing endpoints and safely updates runtime credit states."""
        providers = getattr(self.config, "proxy_rotation", {}).get("providers", {})

        for name, p_info in providers.items():
            api_key = p_info.get("api_key")
            if not api_key:
                continue
            try:
                if name == "scraperapi":
                    res = requests.get(f"http://api.scraperapi.com/account?api_key={api_key}", timeout=5)
                    if res.status_code == 200:
                        cleaned_text = res.text.strip()
                        if cleaned_text.isdigit():
                            self._runtime_credits[name] = int(cleaned_text)
                        else:
                            try:
                                data = res.json()
                                if isinstance(data, dict):
                                    # ScraperAPI JSON endpoint schema
                                    limit = data.get("requestLimit", 5000)
                                    used = data.get("requestCount", 0)
                                    self._runtime_credits[name] = max(0, limit - used)
                            except ValueError:
                                self._runtime_credits[name] = 5000

                elif name == "scrapeops":
                    # Corrected ScrapeOps Aggregator usage path
                    res = requests.get(f"https://proxy.scrapeops.io/v1/account?api_key={api_key}", timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, dict):
                            # Handle both standard individual keys and aggregate endpoint formats
                            if "remaining_credits" in data:
                                self._runtime_credits[name] = data.get("remaining_credits", 0)
                            else:
                                # Fallback math using dashboard properties: limit - used
                                limit = data.get("credit_limit", data.get("limit", 1000))
                                used = data.get("credit_used", data.get("used", 497))
                                self._runtime_credits[name] = max(0, limit - used)

                elif name == "zenrows":
                    res = requests.get(f"https://api.zenrows.com/v1/usage?apikey={api_key}", timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, dict):
                            limit = data.get("limit", 5000)
                            cost = data.get("cost", 0)
                            self._runtime_credits[name] = max(0, limit - cost)
            except Exception as e:
                logger.warning(f"Could not fetch live credits for {name}: {type(e).__name__} - {e}")

    def search_historical_sales(self, query: str, min_price: float, max_price: float, category_id: str, model_name: str, strategy: BaseCPUStrategy) -> List[MarketItem]:
        """Harvests historical sales using explicit typed parameter payloads to prevent gateway 400 rejections."""
        self._enforce_politeness()

        # 1. Construct Target URL
        cleaned_query = " ".join(query.split())
        encoded_query = requests.utils.quote(cleaned_query)
        target_ebay_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1&_ipg=100&_sop=13"
        if category_id and str(category_id).lower() != "global root":
            target_ebay_url += f"&_sacat={category_id}"
        target_ebay_url += f"&_udlo={min_price}&_udhi={max_price}"

        # 2. Select provider via rotation engine
        base_url, _, provider = self._get_proxied_request_params(target_ebay_url, [])

        # 3. Resolve API Tokens cleanly from config object attributes
        proxy_rotation = getattr(self.config, "proxy_rotation", {})
        providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else getattr(proxy_rotation, "providers", {})
        api_key = providers_cfg.get(provider, {}).get("api_key")

        # 4. Payload Generation mapping direct parameters using explicit primitive booleans
        if provider == "scraperapi":
            payload = {
                "api_key": api_key,
                "url": f"{target_ebay_url}&cb={int(time.time() * 1000)}",
                "render": "true",
                "skip_cache": "true",
                "wait_for_selector": ".srp-results, .s-card--horizontal"
            }
        elif provider == "scrapeops":
            payload = {
                "api_key": api_key,
                "url": target_ebay_url,
                "bypass": "cloudflare_imperva",
                "render_js": "true",
                "residential": "true",
                "wait_for_selector": ".s-card--horizontal"
            }
        elif provider == "zenrows":
            # Pass options exactly per ZenRows spec using native request serialization behavior
            payload = {
                "apikey": api_key,
                "url": target_ebay_url,
                "render_js": "true",
                "proxy_country": "us",
                "premium_proxy": "true"
            }
        else:
            payload = {"api_key": api_key, "url": target_ebay_url}

        # 5. Execute Request
        try:
            logger.debug(f"Dispatching gateway call to {provider} | URL: {base_url}")
            response = requests.get(base_url, params=payload, timeout=self.timeout)

            if response.status_code == 200:
                return self._parse_ebay_html(response.text, model_name, category_id, True, strategy)

            logger.error(f"Gateway {provider} rejected request. Status: {response.status_code} | Body Summary: {response.text[:200]}")
            return []
        except Exception as e:
            logger.exception(f"Request failed for {provider}: {str(e)}")
            return []

    def get_credit_summary(self) -> str:
        """Returns a formatted string of remaining credits for all providers."""
        summaries = [f"{name.upper()}: {count}" for name, count in self._runtime_credits.items()]
        return " | ".join(summaries)

    def _get_proxied_request_params(self, target_url: str, blacklisted_providers: List[str]) -> Tuple[str, Dict[str, Any], str]:
        """Evaluates the proxy rotation matrix and applies weighted random selection."""
        # 1. Extract rotation config
        rotation_cfg = self.config.get("proxy_rotation", {}) if isinstance(self.config, dict) else getattr(self.config, "proxy_rotation", {})
        providers = rotation_cfg.get("providers", {}) if isinstance(rotation_cfg, dict) else {}

        # 2. Filter out blacklisted providers
        active_providers = {k: v for k, v in providers.items() if k not in blacklisted_providers}

        # 3. If all providers are blacklisted, reset the list (self-healing)
        if not active_providers:
            logger.warning("All providers blacklisted. Resetting proxy rotation cycle.")
            blacklisted_providers.clear()
            active_providers = providers

        # 4. Extract weights and perform weighted choice
        names = list(active_providers.keys())
        # Use .get("weight", 1) as a default to prevent math errors
        weights = [int(active_providers[name].get("weight", 1)) for name in names]
        chosen_name = random.choices(names, weights=weights, k=1)[0]

        p_info = active_providers[chosen_name]

        # 5. Prepare payload
        # Note: Some APIs require 'url' as a parameter, others might have different requirements
        payload = {"api_key": p_info.get("api_key"), "url": target_url}

        if chosen_name == "scraperapi":
            payload.update({"render": "false", "skip_cache": "true"})
        elif chosen_name == "zenrows":
            payload.update({"proxy_country": "us"})

        # Clean base_url to ensure consistency
        base_url = p_info.get("base_url", "https://api.scraperapi.com").rstrip("/")

        return base_url, payload, chosen_name

        return p_info.get("base_url", "https://api.scraperapi.com").rstrip("/"), payload, chosen_name

    def dispatch_scrape(self, target_url: str, max_retries: int = 3) -> Optional[str]:
        """Circuit-breaker wrapper for proxy-rotated requests."""
        blacklisted = []
        for attempt in range(max_retries):
            base_url, payload, provider = self._get_proxied_request_params(target_url, blacklisted)
            try:
                response = requests.get(base_url, params=payload, timeout=self.timeout)
                if response.status_code == 200:
                    return response.text
                logger.warning(f"Provider {provider} failed with {response.status_code}. Blacklisting.")
                blacklisted.append(provider)
            except Exception as e:
                logger.error(f"Request failed: {e}")
        return None

    def search_historical_sales(self, query: str, min_price: float, max_price: float, category_id: str, model_name: str, strategy: BaseCPUStrategy) -> List[MarketItem]:
        """Harvests historical sales using weighted proxy rotation, using safe URL assignment schemas."""
        self._enforce_politeness()

        # 1. Construct Target eBay URL (Do not double-encode things requests will encode automatically)
        cleaned_query = " ".join(query.split())
        encoded_query = requests.utils.quote(cleaned_query)
        target_ebay_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1&_ipg=100&_sop=13"
        if category_id and str(category_id).lower() != "global root":
            target_ebay_url += f"&_sacat={category_id}"
        target_ebay_url += f"&_udlo={min_price}&_udhi={max_price}"

        # 2. Select proxy rotation target via engine matrix
        base_url, _, provider = self._get_proxied_request_params(target_ebay_url, [])

        # 3. Resolve API Tokens cleanly from config object attributes
        proxy_rotation = getattr(self.config, "proxy_rotation", {})
        if isinstance(proxy_rotation, dict):
            providers_cfg = proxy_rotation.get("providers", {})
        else:
            providers_cfg = getattr(proxy_rotation, "providers", {})

        api_key = providers_cfg.get(provider, {}).get("api_key") if isinstance(providers_cfg, dict) else {}

        # 4. Precise Payload Mapping per Gateway Spec
        if provider == "scraperapi":
            payload = {
                "api_key": api_key,
                "url": f"{target_ebay_url}&cb={int(time.time() * 1000)}",
                "render": "true",
                "skip_cache": "true",
                "wait_for_selector": ".srp-results, .s-card--horizontal"
            }
        elif provider == "scrapeops":
            payload = {
                "api_key": api_key,
                "url": target_ebay_url,
                "bypass": "cloudflare_imperva",
                "render_js": "true",
                "residential": "true",
                "wait_for_selector": ".s-card--horizontal"
            }
        elif provider == "zenrows":
            # Zenrows uses 'apikey' without an underscore.
            # If a 400 persists, ZenRows prefers headers or raw string queries for the target URL.
            payload = {
                "apikey": str(api_key),
                "url": target_ebay_url,
                "render_js": "true",
                "proxy_country": "us",
                "premium_proxy": "true"
            }
        else:
            payload = {"api_key": api_key, "url": target_ebay_url}

        # 5. Execute Pipeline Request Matrix
        try:
            logger.debug(f"Dispatching gateway call to {provider} | URL: {base_url}")
            response = requests.get(base_url, params=payload, timeout=self.timeout)

            if response.status_code == 200:
                return self._parse_ebay_html(response.text, model_name, category_id, True, strategy)

            logger.error(f"Gateway {provider} rejected request. Status: {response.status_code} | Body Summary: {response.text[:200]}")
            return []
        except Exception as e:
            logger.exception(f"Request execution breakout failed for {provider}: {str(e)}")
            return []
    def fetch_raw_item_page(self, item_url: str, max_retries: int = 3) -> str:
        """Fetches a raw item page using the existing dispatch_scrape circuit-breaker logic."""
        self._enforce_politeness()
        html = self.dispatch_scrape(item_url, max_retries=max_retries)
        return html if html else ""

    def _parse_ebay_html(self, html_content: str, model_name: str, category: str, is_sold: bool, strategy: BaseCPUStrategy) -> List[MarketItem]:
        soup = BeautifulSoup(html_content, "html.parser")
        item_summaries = []
        listings = soup.find_all(lambda tag: tag.name in ['li', 'div'] and tag.has_attr('class') and any(
            cls in tag.get('class', []) for cls in ['s-item', 's-card--horizontal']
        ))

        for listing in listings:
            title_ele = listing.find(class_=lambda c: c and any(x in c for x in ["s-item__title", "card__title"]))
            if not title_ele: continue

            raw_title = title_ele.text.strip()
            title_clean = strategy.clean_title(raw_title)
            if strategy.is_valid(title_clean, target_model=model_name) == "INVALID": continue

            price_ele = listing.find(class_=lambda c: c and any(x in c for x in ["s-item__price", "card__price"]))
            if not price_ele: continue

            price_val = float("".join(c for c in price_ele.text.strip() if c.isdigit() or c == "."))
            item_url = listing.find("a", href=True)["href"] if listing.find("a", href=True) else None
            item_id = item_url.split("/itm/")[-1].split("?")[0] if item_url and "/itm/" in item_url else "0"

            item_summaries.append(MarketItem(
                item_id=item_id, model_name=model_name, category=category, raw_title=raw_title,
                title=title_clean, price=price_val, shipping_cost=0.0, total_cost=price_val,
                currency="USD", condition_id=3000, is_sold=is_sold, source_platform="ebay",
                item_url=item_url, process_state="PENDING"
            ))
        return item_summaries

    def parse_msku_item_page(self, html_content: str, base_item) -> list:

        # Guard against connection timeouts returning empty payloads
        if not html_content or len(html_content.strip()) == 0:
            logger.error(f"  [❌] Deep Harvest Aborted: Received empty HTML payload for Item ID: {base_item.item_id} due to upstream gateway timeout.")
            return []

        extracted_variants = []
        soup = BeautifulSoup(html_content, "html.parser")
        html_upper = html_content.upper()

        # 1. Capture Seller Metadata Parameters
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

        # 2. ENGINE ALPHA: Check for Modern 'x-msku-evo' DOM Elements
        sku_options = soup.find_all(class_="listbox__option", attrs={"data-sku-value-name": True})

        if sku_options:
            for index, option in enumerate(sku_options):
                variant_text = option["data-sku-value-name"].strip()
                if not variant_text or variant_text.upper() == "SELECT":
                    continue
                if option.has_attr("aria-disabled") and option["aria-disabled"].lower() == "true":
                    continue  # Skip out of stock options

                extracted_variants.append({
                    "text": variant_text,
                    "index": index,
                    "price_mod": base_item.price
                })

        # 3. ENGINE BETA: Legacy & Universal Fallback if Modern DOM Engine found nothing
        else:
            # Pattern 1: Classic itmVarModel Script Tag
            var_model_match = re.search(r'"itmVarModel"\s*:\s*(\{.*?\})(?:,\s*"|\s*\})', html_content)

            # Pattern 2: ItemJson State Variable Object
            if not var_model_match:
                var_model_match = re.search(r'ItemJson["\']\s*:\s*(\{.*?\})(?:,\s*"|\s*\})', html_content)

            # Pattern 3: 🌟 NEW Universal view-model context block injection
            if not var_model_match:
                var_model_match = re.search(r'window\.__context__\s*=\s*(\{.*?\})(?:;\s*</script>|;\s*window)', html_content)

            if var_model_match:
                try:
                    model_data = json.loads(var_model_match.group(1))

                    # Dig down into deep parameters tree layout patterns
                    menu_items = None
                    if "menuItemMap" in model_data:
                        menu_items = model_data["menuItemMap"]
                    elif "menuViewModel" in model_data:
                        menu_items = model_data["menuViewModel"].get("menuItemMap")
                    elif "model" in model_data and "itmVarModel" in model_data["model"]:
                        menu_items = model_data["model"]["itmVarModel"].get("menuItemMap")

                    if menu_items:
                        for idx, (menu_id, details) in enumerate(menu_items.items()):
                            variant_text = details.get("text")
                            if not variant_text or variant_text.upper() == "SELECT":
                                continue

                            variant_price = base_item.price
                            if "price" in details:
                                try:
                                    variant_price = float("".join(c for c in str(details["price"]) if c.isdigit() or c == "."))
                                except ValueError:
                                    pass

                            extracted_variants.append({
                                "text": variant_text,
                                "index": idx,
                                "price_mod": variant_price
                            })
                except Exception as json_err:
                    logger.error(f"Error decoding legacy/universal variation payload JSON: {json_err}")

        # 4. Final Verification Guard Clause
        if not extracted_variants:
            logger.warning(f"  [⚠️] Multi-SKU Schema Exception: Missing block anchor on listing element ID: {base_item.item_id}")
            return []

        # 5. Build and Pack MarketItem Objects
        final_records = []
        for item in extracted_variants:
            variant_title = f"{base_item.title} ({item['text']})".strip()

            cloned_variant = MarketItem(
                item_id=f"{base_item.item_id}-v{item['index']}",
                model_name=base_item.model_name,
                category=base_item.category,
                raw_title=f"{base_item.raw_title} [{item['text']}]",
                title=variant_title,
                price=item['price_mod'],
                shipping_cost=base_item.shipping_cost,
                total_cost=item['price_mod'] + base_item.shipping_cost,
                currency=base_item.currency,
                condition_id=base_item.condition_id,
                is_sold=base_item.is_sold,
                source_platform="ebay",
                item_url=base_item.item_url,
                process_state="PENDING"
            )

            cloned_variant.seller_feedback_score = feedback_score
            cloned_variant.seller_feedback_percent = feedback_pct
            cloned_variant.is_top_rated_seller = is_top_rated
            cloned_variant.has_bent_pins = has_bent_pins

            final_records.append(cloned_variant)

        logger.debug(f"  │  └─ Captured {len(final_records)} items from variation bracket pool.")
        return final_records
