# src/api/ebay/ebay_scrape_client.py

import json
import random
import re
import os
import time
import urllib.parse
import requests
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
from loguru import logger
from src.core.models import MarketItem
from src.analysis.strategy.cpu_strategy import BaseCPUStrategy

class EbayScrapeClient:
    def __init__(self, config):
        self.config = config
        self.timeout = getattr(config, "api_timeout_seconds", 30)
        self.last_request_time = time.perf_counter() - 10.0
        self.min_wait = 1.5
        self.max_wait = 6.0

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
                        "url": "https://example.com"
                    }
                    try:
                        logger.debug("Syncing real-time webscraping_ai balance metrics via minimal credit lookup node...")
                        res = requests.get(sync_url, params=sync_payload, timeout=10)
                        remaining = res.headers.get("X-Quota-Remaining") or res.headers.get("x-quota-remaining")

                        if remaining is not None:
                            self._runtime_credits[name] = int(remaining)
                            logger.info(f"📊 Baseline Token Sync Completed -> WEBSCRAPING_AI: {self._runtime_credits[name]}")
                        else:
                            self._runtime_credits[name] = 1973
                    except Exception as ai_err:
                        logger.warning(f"Could not verify live webscraping_ai credit headers: {ai_err}")
                        self._runtime_credits[name] = 0

            except Exception as e:
                logger.warning(f"Could not fetch live credits for {name}: {type(e).__name__} - {e}")
                self._runtime_credits[name] = 0

        self._balances_already_refreshed = True

    def get_credit_summary(self) -> Dict[str, int]:
        """Returns a snapshot of currently known remaining credit allowances."""
        return self._runtime_credits.copy()

    def _build_provider_headers(self, provider_name: str, p_cfg: dict) -> dict:
        """Helper to generate clean, robust request headers dynamically based on backend specifications."""
        headers = {}
        base_url = p_cfg.get("base_url", "")

        if provider_name == "scraperbox" or "rapidapi" in base_url.lower():
            host_clean = base_url.replace("https://", "").replace("http://", "").split("/")[0].strip()
            if not host_clean or host_clean == "api":
                host_clean = "scraperbox1.p.rapidapi.com"
            headers.update({
                "X-RapidAPI-Key": p_cfg.get("api_key", ""),
                "X-RapidAPI-Host": host_clean
            })

        return headers

    def _get_proxied_request_params(self, target_url: str, blacklist: List[str]) -> Tuple[str, dict, dict, str]:
        """Dynamically picks an available provider, sets up routing parameters, and tracks availability pools."""
        proxy_rotation = getattr(self.config, "proxy_rotation", {})
        providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else getattr(proxy_rotation, "providers", {})

        available_providers = [p for p in self._runtime_credits.keys() if p not in blacklist and self._runtime_credits.get(p, 0) > 0]
        if not available_providers:
            available_providers = [p for p in providers_cfg.keys() if p not in blacklist]
        if not available_providers:
            raise RuntimeWarning("All configured proxy providers are blacklisted or unavailable.")

        chosen_name = random.choice(available_providers)
        p_cfg = providers_cfg.get(chosen_name, {})
        base_url = p_cfg.get("base_url", "")
        api_key = p_cfg.get("api_key", "")

        payload = {}
        headers = self._build_provider_headers(chosen_name, p_cfg)

        if chosen_name == "scraperapi":
            payload.update({
                "api_key": api_key,
                "url": target_url,
                "premium": "true",
                "skip_cache": "true"
            })
        elif chosen_name == "scrapeops":
            payload.update({
                "api_key": api_key,
                "url": target_url,
                "bypass": "cloudflare_imperva"
            })
        elif chosen_name == "webscraping_ai":
            payload.update({
                "api_key": api_key,
                "url": target_url,
                "proxy": "datacenter"
            })
        elif chosen_name == "scraperbox":
            if base_url.endswith("/scrape"):
                base_url = base_url[:-7]
            payload.update({
                "url": target_url,
                "proxy_type": "residential",
                "render": "true"
            })
        else:
            payload.update({
                "api_key": api_key,
                "url": target_url
            })

        return base_url, payload, headers, chosen_name

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
            base_url, payload, headers, provider = self._get_proxied_request_params(target_ebay_url, self._active_blacklist)
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

        endpoint_path = p_cfg.get('endpoint_path', '') or 'scrape'
        request_url = f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}".rstrip('/')

        # Keep a dedicated clean copy of headers to prevent cross-contamination
        active_headers = headers.copy() if headers else {}

        # --- PRE-REQUEST ROUTING PARAMETERS ---
        if provider == "scraperbox":
            payload["proxy_type"] = "datacenter"

        elif provider == "webscraping_ai":
            api_key = p_cfg.get("api_key", "")
            raw_encoded_target = requests.utils.quote(target_ebay_url, safe='')
            request_url = f"{request_url}?api_key={api_key}&url={raw_encoded_target}&proxy=datacenter"
            payload = {}
            active_headers = {}  # Wipe downstream proxy headers

        try:
            logger.debug(f"Dispatching to {provider} | URL: {request_url}")
            response = requests.get(request_url, params=payload, headers=active_headers, timeout=self.timeout)

            # --- POST-REQUEST QUANTUM RESPONSE PARSING ---
            if provider == "webscraping_ai":
                remaining_quota = response.headers.get("X-Quota-Remaining") or response.headers.get("x-quota-remaining")
                if remaining_quota is not None:
                    self._runtime_credits[provider] = int(remaining_quota)
                    logger.debug(f"🔄 WebScraping.AI Live Quota Synced: {self._runtime_credits[provider]}")

            if response.status_code in [401, 403]:
                logger.error(f"🔒 Authentication rejection / Quota Exceeded (Status {response.status_code}) on {provider}. Zeroing credits.")
                self._runtime_credits[provider] = 0
                if provider not in self._active_blacklist:
                    self._active_blacklist.append(provider)
                return []

            if response.status_code == 200:
                if not response.text or "captcha" in response.text.lower():
                    logger.warning(f"⚠️ {provider} returned a 200 but text appears to be a CAPTCHA challenge or empty.")
                    return []
                return self._parse_ebay_html(response.text, model_name, category_id, True, strategy)

            logger.warning(f"Bad response from {provider}: Status {response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Provider {provider} failed execution: {e}")
            return []

    def dispatch_scrape(self, target_url: str, max_retries: int = 3) -> Optional[str]:
        """Executes targeted individual page scraping operations across available proxy matrix allocations."""
        for attempt in range(max_retries):
            try:
                base_url, payload, headers, provider = self._get_proxied_request_params(target_url, self._active_blacklist)

                proxy_rotation = getattr(self.config, "proxy_rotation", {})
                providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else getattr(proxy_rotation, "providers", {})
                p_cfg = providers_cfg.get(provider, {})

                endpoint_path = p_cfg.get('endpoint_path', '') or 'scrape'
                request_url = f"{base_url.rstrip('/')}/{endpoint_path.lstrip('/')}".rstrip('/')

                # Keep a dedicated clean copy of headers to prevent cross-contamination
                active_headers = headers.copy() if headers else {}

                # --- PRE-REQUEST ROUTING PARAMETERS ---
                if provider == "scraperbox":
                    payload["proxy_type"] = "datacenter"

                elif provider == "webscraping_ai":
                    api_key = p_cfg.get("api_key", "")
                    raw_encoded_target = requests.utils.quote(target_url, safe='')
                    request_url = f"{request_url}?api_key={api_key}&url={raw_encoded_target}&proxy=datacenter"
                    payload = {}
                    active_headers = {}  # Wipe downstream proxy headers

                logger.debug(f"[{attempt + 1}/{max_retries}] Dispatching sub-page scrape to {provider}")
                response = requests.get(request_url, params=payload, headers=active_headers, timeout=self.timeout)

                # --- POST-REQUEST QUANTUM RESPONSE PARSING ---
                if provider == "webscraping_ai":
                    remaining_quota = response.headers.get("X-Quota-Remaining") or response.headers.get("x-quota-remaining")
                    if remaining_quota is not None:
                        self._runtime_credits[provider] = int(remaining_quota)
                        logger.debug(f"🔄 WebScraping.AI Live Quota Synced: {self._runtime_credits[provider]}")

                if response.status_code == 200:
                    if response.text and "captcha" not in response.text.lower():
                        return response.text
                    logger.warning(f"⚠️ {provider} hit a soft CAPTCHA firewall block. Forcing proxy retry sequence.")

                elif response.status_code in [401, 403]:
                    logger.error(f"🔒 Token pool depleted or blocked on {provider}. Liquidating runtime availability.")
                    self._runtime_credits[provider] = 0
                    if provider not in self._active_blacklist:
                        self._active_blacklist.append(provider)
                    break

                logger.warning(f"Provider {provider} failed with status {response.status_code}. Blacklisting variant loop.")
                if provider not in self._active_blacklist:
                    self._active_blacklist.append(provider)

            except Exception as e:
                logger.error(f"Circuit breaker sweep attempt failed: {e}")
        return None

    def _parse_ebay_html(self, html_text: str, model_name: str, category_id: str, is_sold: bool, strategy: BaseCPUStrategy) -> List[MarketItem]:
        """Parses list layout html data into raw structured baseline data objects."""
        soup = BeautifulSoup(html_text, 'html.parser')
        listings = soup.find_all('li', class_=lambda c: c and 's-item' in c)
        results = []

        for item in listings:
            if 's-item__pl-on-bottom' in item.get('class', []):
                continue

            try:
                title_elem = item.find('div', class_='s-item__title')
                if not title_elem:
                    continue
                title = title_elem.text.strip()

                if "shop on ebay" in title.lower():
                    continue

                link_elem = item.find('a', class_='s-item__link')
                item_url = link_elem['href'].split('?')[0] if link_elem else ""
                item_id_match = re.search(r'/itm/(\d+)', item_url)
                item_id = item_id_match.group(1) if item_id_match else f"raw_{random.randint(100000,999999)}"

                price_elem = item.find('span', class_='s-item__price')
                if not price_elem:
                    continue

                price_text = price_elem.text.strip().replace('$', '').replace(',', '')
                if 'to' in price_text.lower():
                    price_text = price_text.lower().split('to')[0].strip()
                price = float("".join(c for c in price_text if c.isdigit() or c == '.'))

                market_item = MarketItem(
                    item_id=item_id,
                    model_name=model_name,
                    category=category_id,
                    raw_title=title,
                    title=title,
                    price=price,
                    shipping_cost=0.0,
                    total_cost=price,
                    currency="USD",
                    condition_id=3000,
                    is_sold=is_sold,
                    source_platform="ebay",
                    item_url=item_url,
                    process_state="PENDING"
                )
                results.append(market_item)
            except Exception as e:
                logger.trace(f"Skipping individual row processing fault: {e}")
                continue
        return results

    def parse_msku_item_page(self, html_content: str, base_item: MarketItem) -> list:
        """Parses multi-variation schema variants into distinct explicit platform entries."""
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
