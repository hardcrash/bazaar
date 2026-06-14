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
        self.config = config
        self.timeout = getattr(config, "api_timeout_seconds", 30)
        self.last_request_time = time.perf_counter() - 10.0
        self.min_wait = 1.0
        self.max_wait = 3.0

        self._active_blacklist: List[str] = []

        # Updated Provider Pool
        self._runtime_credits: Dict[str, int] = {
            "scraperapi": 5000,
            "scrapeops": 1000,
            "scraperbox": 1000,
            "webscraping_ai": 1000
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

    def search_historical_sales(
        self,
        query: str,
        min_price: float,
        max_price: float,
        category_id: str,
        model_name: str,
        strategy: BaseCPUStrategy,
        conditions: Optional[List[int]] = None
    ) -> List[MarketItem]:
        self._enforce_politeness()

        # 1. Construct Target URL
        cleaned_query = " ".join(query.split())
        encoded_query = requests.utils.quote(cleaned_query)
        target_ebay_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1&_ipg=100&_sop=13"

        if category_id and str(category_id).lower() != "global root":
            target_ebay_url += f"&_sacat={category_id}"

        target_ebay_url += f"&_udlo={min_price}&_udhi={max_price}"
        if conditions:
            condition_str = ",".join(map(str, conditions))
            target_ebay_url += f"&LH_ItemCondition={condition_str}"

        # 2. Select provider via rotation engine
        base_url, _, provider = self._get_proxied_request_params(target_ebay_url, self._active_blacklist)

        # 2.5 Safety Guard: Check credits
        if self._runtime_credits.get(provider, 0) <= 0:
            logger.warning(f"Provider {provider} exhausted. Blacklisting.")
            self._active_blacklist.append(provider)
            return []

        # 3. Resolve API Tokens, Timeouts, and Gateway Headers
        proxy_rotation = getattr(self.config, "proxy_rotation", {})
        providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else getattr(proxy_rotation, "providers", {})

        p_cfg = providers_cfg.get(provider, {})
        api_key = p_cfg.get("api_key")
        timeout = p_cfg.get("api_timeout_seconds", 30)

        # Initialize variables before conditional assignments
        headers = {}
        payload_key = None

        # Determine if we are using a RapidAPI gateway
        if "rapidapi" in p_cfg.get("base_url", "").lower():
            headers = {
                "x-rapidapi-key": api_key,
                "x-rapidapi-host": p_cfg.get("base_url", "").replace("https://", "").split("/")[0]
            }
        else:
            payload_key = api_key

        # 4. Payload Generation
        payload = {"url": target_ebay_url}
        if payload_key:
            payload["api_key"] = payload_key

        # Map provider-specific primitives
        config = p_cfg.copy()
        if provider == "scraperapi":
            payload.update({"render": "true", "skip_cache": "true", "wait_for_selector": ".srp-results, .s-card--horizontal", "url": f"{target_ebay_url}&cb={int(time.time() * 1000)}"})
        elif provider == "scrapeops":
            payload.update({"bypass": "cloudflare_imperva", "render_js": "true", "residential": "true", "wait_for_selector": ".s-card--horizontal"})
        elif provider == "scraperbox":
            payload.update({"render": "true"})
        elif provider == "webscraping_ai":
            payload.update({"proxy": "residential"})

        # 5. Execute Request
        request_url = f"{p_cfg.get('base_url', '').rstrip('/')}{p_cfg.get('endpoint_path', '')}"
        try:
            logger.debug(f"Dispatching to {provider} | URL: {request_url}")
            response = requests.get(request_url, params=payload, headers=headers, timeout=timeout)

            if response.status_code in [401, 403]:
                self._runtime_credits[provider] = 0
                return []

            if response.status_code == 200:
                return self._parse_ebay_html(response.text, model_name, category_id, True, strategy)

            return []
        except Exception as e:
            logger.error(f"Provider {provider} failed: {e}")
            return []

    def get_credit_summary(self) -> str:
        """Returns a formatted string of remaining credits for all providers."""
        summaries = [f"{name.upper()}: {count}" for name, count in self._runtime_credits.items()]
        return " | ".join(summaries)

    def _get_proxied_request_params(self, target_url: str, blacklisted_providers: List[str]) -> Tuple[str, Dict[str, Any], str]:
        rotation_cfg = getattr(self.config, "proxy_rotation", {})
        providers = rotation_cfg.get("providers", {})

        # Filter by blacklist AND credit balance
        active_providers = {
            k: v for k, v in providers.items()
            if k not in blacklisted_providers and self._runtime_credits.get(k, 0) > 0
        }

        if not active_providers:
            raise Exception("Critical: All proxy providers exhausted or blacklisted!")

        # Perform weighted random selection
        names = list(active_providers.keys())
        weights = [int(p.get("default_weight", 25)) for p in active_providers.values()]
        chosen_name = random.choices(names, weights=weights, k=1)[0]
        p_info = active_providers[chosen_name]

        # 5. Prepare provider-specific payloads
        payload = {"api_key": p_info.get("api_key")}

        if chosen_name == "scraperapi":
            payload.update({"url": target_url, "render": "false", "skip_cache": "true"})
        elif chosen_name == "scrapeops":
            payload.update({"url": target_url})
        elif chosen_name == "webscraping_ai":
            payload.update({"url": target_url, "proxy": "residential"})
        elif chosen_name == "scraperbox":
            payload.update({"url": target_url, "premium_proxy": "true"})

        return p_info.get("base_url").rstrip("/"), payload, chosen_name

    def dispatch_scrape(self, target_url: str, max_retries: int = 3) -> Optional[str]:
        """Circuit-breaker wrapper for proxy-rotated requests."""
        # Use the class attribute instead of a local variable
        for attempt in range(max_retries):
            # Pass self._active_blacklist to your helper
            base_url, payload, provider = self._get_proxied_request_params(target_url, self._active_blacklist)
            try:
                response = requests.get(base_url, params=payload, timeout=self.timeout)
                if response.status_code == 200:
                    return response.text

                logger.warning(f"Provider {provider} failed with {response.status_code}. Blacklisting.")

                # Append to the persistent class attribute
                if provider not in self._active_blacklist:
                    self._active_blacklist.append(provider)

            except Exception as e:
                logger.error(f"Request failed: {e}")
        return None


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
    def parse_standalone_item_hydration(self, html_content: str, item: MarketItem, strategy: Optional[Any] = None) -> MarketItem:
        """
        Executes Stage 2 structural data mutation by routing raw HTML payload
        through the explicit domain strategy parser.
        """
        if not html_content:
            logger.warning(f"⚠️ Blank HTML response packet passed to hydrator for item {item.item_id}")
            return item

        # Resolve explicit parameter first, then fallbacks
        active_strategy = strategy or getattr(item, "strategy", None) or getattr(self, "strategy", None)

        if active_strategy:
            # Invoke your CPUStrategy text evaluation patterns!
            item = active_strategy.extract_specific_attributes(html_content, item)
        else:
            logger.error(f"❌ Missing strategy context layer for item {item.item_id}. Executing fallback state.")
            item.is_for_parts_or_not_working = (item.condition_id == 7000)
            item.process_state = "HYDRATED"

        item.is_parsed_by_agent = True
        return item
