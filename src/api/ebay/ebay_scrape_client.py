# src/api/ebay/ebay_scrape_client.py

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

        # Start with 0 credits safely. Live refresh will populate actual values.
        self._runtime_credits: Dict[str, int] = {
            "scraperapi": 0,
            "scrapeops": 0,
            "scraperbox": 0,
            "webscraping_ai": 0
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
        # Internal execution guard to stop double-firing during pre-flight boot phases
        if getattr(self, "_balances_already_refreshed", False):
            return

        proxy_rot = getattr(self.config, "proxy_rotation", {})
        providers = proxy_rot.get("providers", {}) if isinstance(proxy_rot, dict) else getattr(proxy_rot, "providers", {})

        for name, p_info in providers.items():
            api_key = p_info.get("api_key")
            if not api_key:
                self._runtime_credits[name] = 0
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
                                    limit = data.get("requestLimit", 5000)
                                    used = data.get("requestCount", 0)
                                    self._runtime_credits[name] = max(0, limit - used)
                            except ValueError:
                                self._runtime_credits[name] = 0
                    else:
                        self._runtime_credits[name] = 0

                elif name == "scrapeops":
                    res = requests.get(f"https://proxy.scrapeops.io/v1/account?api_key={api_key}", timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, dict):
                            if "remaining_credits" in data:
                                self._runtime_credits[name] = data.get("remaining_credits", 0)
                            else:
                                limit = data.get("credit_limit", data.get("limit", 0))
                                used = data.get("credit_used", data.get("used", 0))
                                self._runtime_credits[name] = max(0, limit - used)
                    else:
                        self._runtime_credits[name] = 0

                elif name == "scraperbox":
                    self._runtime_credits[name] = 1000 if api_key else 0

                elif name == "webscraping_ai":
                    base_url = p_info.get("base_url", "https://api.webscraping.ai").rstrip("/")
                    sync_url = f"{base_url}/html"
                    sync_payload = {
                        "api_key": api_key,
                        "url": "https://example.com",
                        "js": "false",
                        "proxy": "datacenter"
                    }
                    try:
                        logger.debug("Syncing real-time webscraping_ai balance metrics via minimal credit lookup node...")
                        res = requests.get(sync_url, params=sync_payload, timeout=10)

                        # Added case-insensitive fallback mapping to ensure the header isn't dropped by different clients
                        remaining = res.headers.get("X-Quota-Remaining") or res.headers.get("x-quota-remaining")

                        if remaining is not None:
                            self._runtime_credits[name] = int(remaining)
                            logger.info(f"📊 Baseline Token Sync Completed -> WEBSCRAPING_AI: {self._runtime_credits[name]}")
                        else:
                            # Hardcoded real target update from your dashboard to bypass the initial 1000 threshold drop
                            self._runtime_credits[name] = 1973
                    except Exception as ai_err:
                        logger.warning(f"Could not verify live webscraping_ai credit headers: {ai_err}")
                        self._runtime_credits[name] = 0

            except Exception as e:
                logger.warning(f"Could not fetch live credits for {name}: {type(e).__name__} - {e}")
                self._runtime_credits[name] = 0

        # Mark balance checking complete for this execution lifecycle
        self._balances_already_refreshed = True
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

        cleaned_query = " ".join(query.split())
        encoded_query = requests.utils.quote(cleaned_query)
        target_ebay_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1&_ipg=100&_sop=13"

        if category_id and str(category_id).lower() != "global root":
            target_ebay_url += f"&_sacat={category_id}"

        target_ebay_url += f"&_udlo={min_price}&_udhi={max_price}"
        if conditions:
            condition_str = ",".join(map(str, conditions))
            target_ebay_url += f"&LH_ItemCondition={condition_str}"

        try:
            base_url, payload, provider = self._get_proxied_request_params(target_ebay_url, self._active_blacklist)
        except Exception as e:
            logger.critical(f"Rotation Error: {e}")
            return []

        if self._runtime_credits.get(provider, 0) <= 0:
            logger.warning(f"Provider {provider} exhausted. Blacklisting.")
            if provider not in self._active_blacklist:
                self._active_blacklist.append(provider)
            return []

        proxy_rotation = getattr(self.config, "proxy_rotation", {})
        providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else getattr(proxy_rotation, "providers", {})
        p_cfg = providers_cfg.get(provider, {})
        headers = {}

        if "rapidapi" in p_cfg.get("base_url", "").lower():
            headers = {
                "x-rapidapi-key": p_cfg.get("api_key"),
                "x-rapidapi-host": p_cfg.get("base_url", "").replace("https://", "").split("/")[0]
            }

        # Build dynamic full-path clean request path endpoint definition
        endpoint_path = p_cfg.get('endpoint_path', '')
        request_url = f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}".rstrip('/')

        try:
            logger.debug(f"Dispatching to {provider} | URL: {request_url}")
            response = requests.get(request_url, params=payload, headers=headers, timeout=self.timeout)

            # Live synchronization hook for running webscraping_ai metadata
            if provider == "webscraping_ai":
                remaining_quota = response.headers.get("X-Quota-Remaining")
                if remaining_quota is not None:
                    self._runtime_credits[provider] = int(remaining_quota)

            if response.status_code in [401, 403]:
                logger.error(f"🔒 Authentication rejection (Status {response.status_code}) on {provider}. Zeroing credits.")
                self._runtime_credits[provider] = 0
                if provider not in self._active_blacklist:
                    self._active_blacklist.append(provider)
                return []

            if response.status_code == 200:
                return self._parse_ebay_html(response.text, model_name, category_id, True, strategy)

            logger.warning(f"Bad response from {provider}: Status {response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Provider {provider} failed execution: {e}")
            return []

    def get_credit_summary(self) -> str:
        summaries = [f"{name.upper()}: {count}" for name, count in self._runtime_credits.items()]
        return " | ".join(summaries)

    def _get_proxied_request_params(self, target_url: str, blacklisted_providers: List[str]) -> Tuple[str, Dict[str, Any], str]:
        rotation_cfg = getattr(self.config, "proxy_rotation", {})
        providers = rotation_cfg.get("providers", {}) if isinstance(rotation_cfg, dict) else getattr(rotation_cfg, "providers", {})

        # Retain full pool isolation constraints across all known providers
        active_providers = {
            k: v for k, v in providers.items()
            if k not in blacklisted_providers and self._runtime_credits.get(k, 0) > 0
        }

        if not active_providers:
            raise Exception("Critical: All proxy providers exhausted or blacklisted!")

        names = list(active_providers.keys())
        weights = [int(p.get("default_weight", 25)) for p in active_providers.values()]
        chosen_name = random.choices(names, weights=weights, k=1)[0]
        p_info = active_providers[chosen_name]

        payload = {}
        api_key = p_info.get("api_key")

        # Route matching parameters dynamically by specific vendor signatures
        if chosen_name == "scraperapi":
            payload.update({"api_key": api_key, "url": target_url, "render": "true", "skip_cache": "true", "wait_for_selector": ".srp-results, .s-card--horizontal"})
        elif chosen_name == "scrapeops":
            payload.update({"api_key": api_key, "url": target_url, "bypass": "cloudflare_imperva", "render_js": "true", "residential": "true"})
        elif chosen_name == "webscraping_ai":
            # Testing mode active: Utilizing anti-bot bypass profiles (50 credits/call)
            payload.update({"api_key": api_key, "url": target_url, "proxy": "stealth"})
        elif chosen_name == "scraperbox":
            # Scraperbox API matches 'token' payload parameter identifier mapping
            payload.update({"token": api_key, "url": target_url, "render": "true"})

        return p_info.get("base_url").rstrip("/"), payload, chosen_name

    def dispatch_scrape(self, target_url: str, max_retries: int = 3) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                base_url, payload, provider = self._get_proxied_request_params(target_url, self._active_blacklist)

                proxy_rotation = getattr(self.config, "proxy_rotation", {})
                providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else getattr(proxy_rotation, "providers", {})
                p_cfg = providers_cfg.get(provider, {})
                endpoint_path = p_cfg.get('endpoint_path', '')

                request_url = f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}".rstrip('/')

                response = requests.get(request_url, params=payload, timeout=self.timeout)

                # Live synchronization hook for running webscraping_ai metadata inside the secondary dispatch route
                if provider == "webscraping_ai":
                    remaining_quota = response.headers.get("X-Quota-Remaining")
                    if remaining_quota is not None:
                        self._runtime_credits[provider] = int(remaining_quota)

                if response.status_code == 200:
                    return response.text

                logger.warning(f"Provider {provider} failed with status {response.status_code}. Blacklisting variant loop.")
                if provider not in self._active_blacklist:
                    self._active_blacklist.append(provider)

            except Exception as e:
                logger.error(f"Circuit breaker sweep attempt failed: {e}")
        return None

    def fetch_raw_item_page(self, item_url: str, max_retries: int = 3) -> str:
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

            try:
                price_val = float("".join(c for c in price_ele.text.strip() if c.isdigit() or c == "."))
            except ValueError:
                continue

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
        if not html_content or len(html_content.strip()) == 0:
            logger.error(f"  [❌] Deep Harvest Aborted: Received empty HTML payload for Item ID: {base_item.item_id}")
            return []

        extracted_variants = []
        soup = BeautifulSoup(html_content, "html.parser")
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

        sku_options = soup.find_all(class_="listbox__option", attrs={"data-sku-value-name": True})

        if sku_options:
            for index, option in enumerate(sku_options):
                variant_text = option["data-sku-value-name"].strip()
                if not variant_text or variant_text.upper() == "SELECT":
                    continue
                if option.has_attr("aria-disabled") and option["aria-disabled"].lower() == "true":
                    continue

                extracted_variants.append({
                    "text": variant_text,
                    "index": index,
                    "price_mod": base_item.price
                })
        else:
            var_model_match = re.search(r'"itmVarModel"\s*:\s*(\{.*?\})(?:,\s*"|\s*\})', html_content)
            if not var_model_match:
                var_model_match = re.search(r'ItemJson["\']\s*:\s*(\{.*?\})(?:,\s*"|\s*\})', html_content)
            if not var_model_match:
                var_model_match = re.search(r'window\.__context__\s*=\s*(\{.*?\})(?:;\s*</script>|;\s*window)', html_content)

            if var_model_match:
                try:
                    model_data = json.loads(var_model_match.group(1))
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
                    logger.error(f"Error decoding legacy variation payload JSON: {json_err}")

        if not extracted_variants:
            logger.warning(f"  [⚠️] Multi-SKU Schema Exception: Missing block anchor on listing element ID: {base_item.item_id}")
            return []

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

        logger.debug(f"  │  └─ Captured {len(final_records)} items from variation pool.")
        return final_records

    def parse_standalone_item_hydration(self, html_content: str, item: MarketItem, strategy: Optional[Any] = None) -> MarketItem:
        if not html_content:
            logger.warning(f"⚠️ Blank HTML response packet passed to hydrator for item {item.item_id}")
            return item

        active_strategy = strategy or getattr(item, "strategy", None) or getattr(self, "strategy", None)

        if active_strategy:
            item = active_strategy.extract_specific_attributes(html_content, item)
        else:
            logger.error(f"❌ Missing strategy context layer for item {item.item_id}.")
            item.is_for_parts_or_not_working = (item.condition_id == 7000)
            item.process_state = "HYDRATED"

        item.is_parsed_by_agent = True
        return item
