import json
import random
import re
import datetime
import requests
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger

from src.core.models import MarketItem
from src.api.ebay.ebay_scrape_provider import EbayScraperProvider

class EbayScrapeClient:
    """
    Data translation component focused strictly on HTML payload ingestion, Layout Parsing,
    Multi-SKU Expansion, and Hydrating records into higher data grades.
    """
    def __init__(self, config):
        self.config = config
        self.provider = EbayScraperProvider(config=config)

    def refresh_account_balances(self):
        """Proxy binding method mapping down onto the Infrastructure provider."""
        self.provider.refresh_account_balances()

    def get_credit_summary(self) -> Dict[str, int]:
        """Proxy binding method mapping down onto the Infrastructure provider."""
        return self.provider.get_credit_summary()

    def search_historical_sales(
        self,
        query: str,
        min_price: float,
        max_price: float,
        category_id: str,
        model_name: str,
        strategy: Any,
        conditions: Optional[List[int]] = None
    ) -> List[MarketItem]:

        response_html = ""
        self.provider.enforce_politeness()

        cleaned_query = " ".join(query.split())
        encoded_query = requests.utils.quote(cleaned_query)

        target_ebay_url = (
            f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}"
            f"&LH_Complete=1&LH_Sold=1&rt=nc&_ipg=100&_sop=13&_pgn=1"
        )

        if category_id and str(category_id).lower() != "global root":
            target_ebay_url += f"&_sacat={category_id}"

        if conditions:
            condition_str = ",".join(map(str, conditions))
            target_ebay_url += f"&LH_ItemCondition={condition_str}"

        if min_price is not None:
            target_ebay_url += f"&_udlo={min_price:.2f}"
        if max_price is not None:
            target_ebay_url += f"&_udhi={max_price:.2f}"

        logger.info(f"🔗 Target Upstream eBay URL Generated: {target_ebay_url}")

        # =======================================================
        # --- Dynamic Strategy Order Resolution & Extraction ---
        # =======================================================
        # Extract the exact active provider blocks directly from your config layout
        proxy_config = getattr(self.provider.config, "proxy_rotation", {})
        configured_providers = proxy_config.get("providers", {})

        # Build the iteration list dynamically from whatever keys are present in your YAML
        # e.g., ["scrapeops_hmr"] or ["scraperapi_cmk", "scrapeops_hmr"]
        providers = list(configured_providers.keys())

        # If a specific strategy overrides the order, push that service name to the front
        if str(strategy).lower() != "weighted_random":
            providers.sort(key=lambda k: str(strategy).lower() in k.lower(), reverse=True)

        response_html = None

        # --- Core Provider Failover Pipeline Loop ---
        for provider_key in providers:
            try:
                # 1. Quota Pre-Flight Check (Safely using dynamic config key name)
                if self.provider._runtime_credits.get(provider_key, 0) <= 0:
                    logger.warning(f"Provider {provider_key} exhausted. Skipping configuration block.")
                    self.provider.flag_provider_exhausted(provider_key)
                    continue

                # 2. Extract configuration payload cleanly using the dynamic key string
                provider_cfg = configured_providers.get(provider_key, {})

                # 3. Dynamic Engine Type Identification via substring matching
                if "scraperapi" in provider_key.lower():
                    from src.api.ebay.providers.scraperapi_provider import ScraperApiProvider
                    try:
                        provider_engine = ScraperApiProvider(provider_cfg=provider_cfg)
                    except TypeError:
                        provider_engine = ScraperApiProvider(provider_cfg)

                elif "scrapeops" in provider_key.lower():
                    from src.api.ebay.providers.scrapeops_provider import ScrapeOpsProvider
                    try:
                        provider_engine = ScrapeOpsProvider(provider_cfg=provider_cfg)
                    except TypeError:
                        provider_engine = ScrapeOpsProvider(provider_cfg)
                else:
                    logger.error(f"⚠️ Unrecognized structural provider string configuration: {provider_key}")
                    continue

                # Build fully rendered parameters using the dynamically resolved engine
                request_url, payload, active_headers = provider_engine.build_request_params(target_ebay_url)
                current_provider = provider_key

                logger.success(f"🚀 ROUTING CHOICE | Active Provider Strategy: [{current_provider.upper()}]")
                logger.debug(f"⚙️ Compiled Request URL: {request_url}")

                # Dynamic masking that covers both hyphenated ('api-key') and underscored ('api_key') variations
                sanitized_payload = {
                    k: (v if k not in ['api_key', 'api-key'] else '***')
                    for k, v in payload.items()
                }
                logger.debug(f"⚙️ Compiled Proxy Parameters: {json.dumps(sanitized_payload)}")

                # 4. Network Transport Execution
                logger.info(f"📡 Dispatching outbound HTTP request via {current_provider}...")
                response = requests.get(
                    request_url,
                    params=payload,
                    headers=active_headers if active_headers else None,
                    timeout=self.provider.timeout
                )

                # 5. Telemetry Extraction
                raw_text = response.text or ""
                logger.info(f"📥 RESPONSE RECEIVED | Provider: [{current_provider.upper()}] | Status Code: {response.status_code} | Payload Size: {len(raw_text)} characters")

                # 6. Continuous Network Diagnostic Drop
                try:
                    with open("raw_network_checkpoint.txt", "w", encoding="utf-8") as f:
                        f.write(f"TIMESTAMP: {datetime.datetime.now()}\nPROVIDER: {current_provider}\nSTATUS CODE: {response.status_code}\n")
                        f.write(f"RESPONSE LENGTH: {len(raw_text)}\n" + "-" * 50 + "\n")
                        f.write(raw_text if raw_text else "[EMPTY BODY]")
                    logger.info("📡 Dropped full network diagnostic checkpoint to raw_network_checkpoint.txt")
                except Exception as checkpoint_err:
                    logger.error(f"⚠️ Failed to write raw network checkpoint: {checkpoint_err}")

                self.provider.update_quota_header(current_provider, response)

                # 7. Hard Rejection Checking (Auth / Rate limits using dynamic log values)
                if response.status_code in [401, 403, 429]:
                    logger.error(f"🔒 Authentication rejection / Quota Exceeded (Status {response.status_code}) on {current_provider}.")
                    self.provider.flag_provider_exhausted(current_provider)
                    continue

                # 8. Soft Content Rejection Check (CAPTCHAs or missing layout anchors)
                html_lower = raw_text.lower()

                # Hardened Layout Guard: Look for structural anchors across both raw desktop and rendered JS states
                has_items_raw = (
                    "s-item__wrapper" in raw_text or
                    'li class="s-item' in raw_text or
                    "srp-results" in html_lower or
                    "srp-river" in html_lower or
                    "/itm/" in html_lower
                )

                if response.status_code != 200 or not raw_text or "captcha" in html_lower or "robot check" in html_lower or "security measure" in html_lower or "attention required" in html_lower or not has_items_raw:

                    title_match = re.search(r"<title>(.*?)</title>", raw_text, re.IGNORECASE)
                    page_title = title_match.group(1).strip() if title_match else "NO TITLE FOUND"
                    logger.warning(f"❌ [BOGUS RESPONSE] Headless layout validation failed for {current_provider}. Title: '{page_title}' | Has s-item container variant: {has_items_raw}")

                    with open(f"debug_{current_provider.lower()}_response.html", "w", encoding="utf-8") as f:
                        f.write(raw_text)
                    continue

                # 9. Integrity Audit Passed
                title_match = re.search(r"<title>(.*?)</title>", raw_text, re.IGNORECASE)
                page_title = title_match.group(1).strip() if title_match else "NO TITLE FOUND"
                logger.debug(f"🔍 Content Integrity Audit | Page Title: '{page_title}' | Raw 's-item' Substring Found: True")

                # Assign securely to outer scope
                response_html = raw_text
                break

            except Exception as e:
                logger.error(f"Provider {provider_key} failed execution loop network transport layer: {e}")
                continue
        # --- Extrapolate Sourcing Content Out-of-Bounds ---
        if response_html:
            logger.info("🚀 Payload confirmed. Handing off raw markup stream to _parse_ebay_html().")
            return self._parse_ebay_html(
                html_content=response_html,
                model_name=model_name,
                category_id=category_id,
                is_sold=True
            )

        logger.critical("❌ All configured proxy networks exhausted, unauthorized, or failing layout validation.")
        return []

    def _parse_ebay_html(self, html_content: str, model_name: str, category_id: str, is_sold: bool = True) -> List[MarketItem]:
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []

        # 📊 Stage 1: Expanded Primary Tabular & River Layout Selectors
        try:
            listings = soup.select(".srp-river-results .s-item__wrapper, .srp-results .s-item__wrapper, #srchResultsList .s-item__wrapper")
            strategy_used = "Standard Wrapper (Grid/River CSS Selectors)"
        except Exception as e:
            logger.debug(f"Stage 1 selector failed: {e}")
            listings = []

        # Stage 2: Fallback to global list matching sets if river containers are obfuscated
        if not listings:
            try:
                listings = soup.find_all('li', class_=lambda c: c and 's-item' in c)
                strategy_used = "li.s-item (Fallback Class Matching)"
            except Exception as e:
                logger.debug(f"Stage 2 selector failed: {e}")

        # Stage 3: Flexible Fallback for Rendered JS/Mobile Layout Engines
        if not listings:
            try:
                listings = soup.select("[class*='s-item'][class*='wrapper'], [class*='sitem']")
                if listings:
                    strategy_used = "Partial Substring Class Wildcard Matching"
            except Exception as e:
                logger.debug(f"Stage 3 selector failed: {e}")

        # Stage 4: Extreme fallback via relative item link lookup (Heuristic Link Harvesting)
        if not listings:
            try:
                item_links = soup.find_all('a', href=lambda h: h and ('/itm/' in h or 'itm/' in h))
                logger.debug(f"🕵️‍♂️ Diagnostic: Found {len(item_links)} total /itm/ hyperlinks inside raw DOM stack.")

                seen_parents = set()
                listings = []
                for link in item_links:
                    parent = link.find_parent('li') or link.find_parent('div', class_=lambda c: c and ('item' in c or 'card' in c))
                    if parent:
                        if id(parent) not in seen_parents:
                            seen_parents.add(id(parent))
                            listings.append(parent)
                    else:
                        # Ultra-fallback: if no structured parent card exists, take the direct parent container
                        p_direct = link.parent
                        if p_direct and id(p_direct) not in seen_parents:
                            seen_parents.add(id(p_direct))
                            listings.append(p_direct)

                if listings:
                    strategy_used = "Rendered JS Link-Driven Parent Extraction Engine"
            except Exception as e:
                logger.error(f"💥 Stage 4 link harvesting crashed: {e}", exc_info=True)

        # 📊 Stage 5: Critical Structural Failure Logging
        if not listings:
            logger.warning("⚠️ No raw item listing container elements matched the structural DOM query.")
            try:
                body_snippet = soup.body.text[:200].strip() if soup.body else "NO BODY TAG"
                logger.debug(f"🩻 Body text snippet: {body_snippet}")
            except Exception as e:
                logger.debug(f"Failed to extract body text snippet: {e}")
            return []

        logger.info(f"🔍 DOM Ingestion Engine isolated {len(listings)} element nodes via strategy: [{strategy_used}]")

        # Track precise filter dropouts throughout processing loop
        skipped_no_title = 0
        skipped_shop_on = 0
        skipped_no_price = 0
        skipped_price_conv = 0
        unhandled_exceptions = 0

        for item in listings:
            # 🚨 RELAX THE GUARD: Trace log auxiliary placement templates
            if item.get('class') and any('s-item__pl-on-bottom' in cls for cls in item.get('class')):
                logger.trace("Encountered auxiliary placement block layout template. Processing row regardless.")

            try:
                # 🌟 STEP 0: Pre-initialize loop variables to guarantee scope safety
                title = ""
                item_url = ""
                item_id = None
                price = 0.0
                shipping_cost = 0.0

                # =======================================================
                # 1. Title Extraction Verification (Hardened JS Variant)
                # =======================================================
                title_elem = (
                    item.select_one(".s-item__title") or
                    item.select_one("[class*='item__title']") or
                    item.select_one(".s-item__info a h3") or
                    item.find('div', class_=lambda c: c and 'title' in c) or
                    item.select_one("h3")
                )

                if not title_elem:
                    skipped_no_title += 1
                    continue

                inner_span = title_elem.find('span', role='text') or title_elem.select_one(".s-item__title--tag")
                if inner_span:
                    title = inner_span.text.strip()
                else:
                    title = title_elem.get_text(" ", strip=True)

                if not title or "shop on ebay" in title.lower() or "shop on" in title.lower():
                    skipped_shop_on += 1
                    continue

                # =======================================================
                # 2. URL and Entity Key Identification (Hardened JS Variant)
                # =======================================================
                # Priority 1: Snatch native platform IDs directly off DOM container tags
                item_id = item.get('data-id') or item.get('data-itemid')

                # Priority 2: Extract link element using comprehensive fallback matrix
                link_elem = (
                    item.select_one(".s-item__link") or
                    item.find('a', class_=lambda c: c and 'item__link' in c) or
                    item.select_one("a[href*='/itm/']") or  # Snaps any direct single item link
                    item.find('a')  # Last resort structural fallback anchor
                )

                item_url = ""
                if link_elem and link_elem.has_attr('href'):
                    item_url = link_elem['href'].split('?')[0]

                # Fallback Regex ID Check: If data attributes failed, parse ID out of valid URL string
                if not item_id and item_url:
                    item_id_match = re.search(r'/itm/(\d+)', item_url)
                    if item_id_match:
                        item_id = item_id_match.group(1)

                # CRITICAL GUARD: Drop node early if we can't capture a real eBay ID or valid tracking URL.
                # This guarantees that fake random IDs never corrupt your database deduplication layers.
                if not item_id or not item_url or "/itm/" not in item_url:
                    logger.trace("Skipping unidentifiable node: Missing absolute platform identifier metrics.")
                    continue

                # =======================================================
                # 3. Price Block Parsing Heuristics (Resilient JS Variant)
                # =======================================================
                price_elem = (
                    item.select_one(".s-item__price") or
                    item.select_one("[class*='item__price']") or
                    item.select_one(".s-item__bids") or
                    item.select_one("[class*='item__bids']") or
                    item.find('span', class_=lambda c: c and 'price' in c) or
                    item.select_one(".s-item__detail--primary .POSITIVE")
                )
                if not price_elem:
                    skipped_no_price += 1
                    continue

                price_raw_text = price_elem.get_text(" ", strip=True)

                # Check for explicit range indicators or structural layout formats
                has_range_indicator = 'to' in price_raw_text.lower()
                has_variant_format = (
                    item.select_one('.s-item__format-dynamic') is not None or
                    item.select_one('.s-item__format-variants') is not None
                )

                # Density Check: Flag listing if seller crams multiple monitored models into a single title
                known_models_pool = ["5600X", "5700X", "5800X", "5900X", "5950X"]
                matching_models_in_title = [
                    m for m in known_models_pool
                    if m.lower() in title.lower()
                ]

                # Composite MSKU Strategy Rule
                is_msku_parent = (
                    has_range_indicator or
                    has_variant_format or
                    len(matching_models_in_title) > 1
                )

                if 'to' in price_raw_text.lower():
                    price_raw_text = price_raw_text.lower().split('to')[0].strip()

                price_digits = "".join(c for c in price_raw_text if c.isdigit() or c == '.' or c == ',')
                if not price_digits:
                    skipped_price_conv += 1
                    continue

                if ',' in price_digits and '.' not in price_digits:
                    price_digits = price_digits.replace(',', '.')
                elif ',' in price_digits and '.' in price_digits:
                    price_digits = price_digits.replace(',', '')

                # Safely assign back to our pre-defined local scope variable
                price = float(price_digits)

                # =======================================================
                # 4. Record Hydration
                # =======================================================
                market_item = MarketItem(
                    item_id=item_id,
                    model_name=model_name,
                    category=category_id,
                    raw_title=title,
                    title=title,
                    price=price,
                    shipping_cost=shipping_cost,
                    total_cost=price + shipping_cost,  # Safe scalar arithmetic math base
                    currency="USD",
                    condition_id=3000,
                    is_sold=is_sold,
                    source_platform="ebay",
                    item_url=item_url,
                    process_state="PENDING_DEEP_HARVEST" if is_msku_parent else "PENDING",
                    data_grade="BRONZE"
                )
                results.append(market_item)

            except Exception as parse_err:
                unhandled_exceptions += 1
                logger.debug(f"🚨 Item parsing iteration failed: {type(parse_err).__name__} - {parse_err}")
                continue

        # 📊 Pipeline Triage Diagnostic Reporting
        logger.info(
            f"🔍 DOM Ingestion Engine isolated {len(listings)} nodes via strategy: [{strategy_used}]. "
            f"Successfully hydrated {len(results)} items."
        )

        if len(results) == 0 and len(listings) > 0:
            logger.warning(
                f"🛑 Dropback Triage Summary | Total Nodes: {len(listings)} | "
                f"Missing Title: {skipped_no_title} | "
                f"'Shop On' Filtered: {skipped_shop_on} | "
                f"Missing Price Elem: {skipped_no_price} | "
                f"Price Conversion Failures: {skipped_price_conv} | "
                f"Caught Code Crashes: {unhandled_exceptions}"
            )

        # 📢 FINAL METRIC RECONCILIATION SNAPSHOT
        logger.info(
            f"📊 Parse Statistics Loop Yielded: {len(results)} Hydrated MarketItems | "
            f"Filtered States -> [No Title Elements: {skipped_no_title}, 'Shop On' Ad Blocks: {skipped_shop_on}, "
            f"Missing Price DOM: {skipped_no_price}, Digital Conversion Drops: {skipped_price_conv}]"
        )

        return results


    def dispatch_scrape(self, target_url: str, max_retries: int = 3) -> Optional[str]:
        """Executes targeted individual page scraping operations across available proxy matrix allocations."""
        for attempt in range(max_retries):
            try:
                base_url, payload, headers, provider = self.provider.get_proxied_request_params(target_url)
                proxy_rotation = getattr(self.config, "proxy_rotation", {})
                providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else getattr(proxy_rotation, "providers", {})
                p_cfg = providers_cfg.get(provider, {})

                clean_base = base_url.rstrip('/')
                endpoint_path = p_cfg.get('endpoint_path', '').strip('/')
                request_url = f"{clean_base}/{endpoint_path}" if endpoint_path else clean_base

                active_headers = headers.copy() if headers else {}

                # 🌟 AD-HOC DEVIATIONS STRIPPED OUT:
                # Let the infrastructure provider do its job generating the params cleanly.
                logger.debug(f"[{attempt + 1}/{max_retries}] Dispatching sub-page scrape to {provider}")
                response = requests.get(request_url, params=payload, headers=active_headers, timeout=self.provider.timeout)

                self.provider.update_quota_header(provider, response)

                if response.status_code == 200:
                    if response.text and "captcha" not in response.text.lower():
                        return response.text
                    logger.warning(f"⚠️ {provider} hit a soft CAPTCHA block during deep leaf hydration.")

                elif response.status_code in [401, 403]:
                    logger.error(f"🔒 Token pool depleted on {provider}. Liquidating availability.")
                    self.provider.flag_provider_exhausted(provider)
                    break

                self.provider.flag_provider_exhausted(provider)

            except Exception as e:
                logger.error(f"Circuit breaker sweep attempt failed: {e}")

        return None

    def parse_msku_item_page(self, html_content: str, base_item: MarketItem) -> List[MarketItem]:
        """
        Parses multi-variation split configurations across every style served by eBay.
        Extracts metadata tokens and splits them up into separate SILVER grade child records.
        """
        if not html_content or len(html_content.strip()) == 0:
            logger.error(f"[❌] Deep Harvest Aborted: Empty HTML payload for Parent Item ID: {base_item.item_id}")
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        html_upper = html_content.upper()
        final_records = []

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

        msku_match = re.search(r'"MSKU"\s*:\s*({.+?}),\s*"QUANTITY"', html_content)
        if not msku_match:
            msku_match = re.search(r'"MSKU"\s*:\s*({.+?}),\s*"[A-Za-z_]+"', html_content)

        if msku_match:
            try:
                msku_data = json.loads(msku_match.group(1))
                variations_map = msku_data.get("variationsMap", {})
                menu_items_map = msku_data.get("menuItemMap", {})
                variation_combos = msku_data.get("variationCombinations", {})

                if variation_combos and variations_map:
                    for combo_key, variant_id in variation_combos.items():
                        variant_details = variations_map.get(variant_id, {})
                        if not variant_details:
                            continue

                        labels = []
                        for index_str in combo_key.split("_"):
                            menu_item = menu_items_map.get(index_str, {})
                            label_value = menu_item.get("valueValue") or menu_item.get("displayValue") or ""
                            if label_value:
                                labels.append(label_value.strip())

                        combo_suffix = f" ({' - '.join(labels)})" if labels else f" (Variant {variant_id})"

                        price_val = base_item.price
                        price_info = variant_details.get("priceValue", {}) or variant_details.get("price", {})
                        if isinstance(price_info, dict) and "value" in price_info:
                            price_val = float(price_info["value"])
                        elif isinstance(price_info, (int, float)):
                            price_val = float(price_info)

                        out_of_stock = variant_details.get("isOutOfStock", False)
                        qty = 0 if out_of_stock else variant_details.get("quantityAvailable", 1)

                        child_item = MarketItem(
                            item_id=f"{base_item.item_id}-{variant_id}",
                            model_name=base_item.model_name,
                            category=base_item.category,
                            raw_title=f"{base_item.raw_title} [{', '.join(labels)}]",
                            title=f"{base_item.title}{combo_suffix}",
                            price=price_val,
                            shipping_cost=base_item.shipping_cost,
                            total_cost=price_val + base_item.shipping_cost,
                            currency=base_item.currency,
                            condition_id=base_item.condition_id,
                            is_sold=base_item.is_sold,
                            source_platform="ebay",
                            item_url=base_item.item_url,
                            quantity_sold=qty,
                            process_state="COMPLETED",
                            data_grade="SILVER"
                        )
                        final_records.append(child_item)
            except Exception as msku_err:
                logger.error(f"Failed parsing raw core MSKU engine block: {msku_err}")

        if not final_records:
            var_model_match = re.search(r'"itmVarModel"\s*:\s*(\{.*?\})(?:,\s*"|\s*\})', html_content)
            if not var_model_match:
                var_model_match = re.search(r'ItemJson["\']\s*:\s*(\{.*?\})(?:,\s*"|\s*\})', html_content)

            if var_model_match:
                try:
                    model_data = json.loads(var_model_match.group(1))
                    menu_items = model_data.get("menuItemMap") or model_data.get("menuViewModel", {}).get("menuItemMap")

                    if menu_items:
                        for idx, (menu_id, details) in enumerate(menu_items.items()):
                            variant_text = details.get("text") or details.get("valueValue")
                            if not variant_text or variant_text.upper() == "SELECT":
                                continue

                            variant_price = base_item.price
                            if "price" in details:
                                try:
                                    variant_price = float("".join(c for c in str(details["price"]) if c.isdigit() or c == "."))
                                except ValueError:
                                    pass

                            child_item = MarketItem(
                                item_id=f"{base_item.item_id}-v{idx}",
                                model_name=base_item.model_name,
                                category=base_item.category,
                                raw_title=f"{base_item.raw_title} [{variant_text}]",
                                title=f"{base_item.title} ({variant_text})",
                                price=variant_price,
                                shipping_cost=base_item.shipping_cost,
                                total_cost=variant_price + base_item.shipping_cost,
                                currency=base_item.currency,
                                condition_id=base_item.condition_id,
                                is_sold=base_item.is_sold,
                                source_platform="ebay",
                                item_url=base_item.item_url,
                                process_state="COMPLETED",
                                data_grade="SILVER"
                            )
                            final_records.append(child_item)
                except Exception as json_err:
                    logger.error(f"Error decoding alternative variant context model: {json_err}")

        if not final_records:
            sku_options = soup.find_all(class_="listbox__option", attrs={"data-sku-value-name": True})
            for index, option in enumerate(sku_options):
                variant_text = option["data-sku-value-name"].strip()
                if not variant_text or variant_text.upper() == "SELECT":
                    continue
                if option.has_attr("aria-disabled") and option["aria-disabled"].lower() == "true":
                    continue

                child_item = MarketItem(
                    item_id=f"{base_item.item_id}-dom{index}",
                    model_name=base_item.model_name,
                    category=base_item.category,
                    raw_title=f"{base_item.raw_title} [{variant_text}]",
                    title=f"{base_item.title} ({variant_text})",
                    price=base_item.price,
                    shipping_cost=base_item.shipping_cost,
                    total_cost=base_item.price + base_item.shipping_cost,
                    currency=base_item.currency,
                    condition_id=base_item.condition_id,
                    is_sold=base_item.is_sold,
                    source_platform="ebay",
                    item_url=base_item.item_url,
                    process_state="COMPLETED",
                    data_grade="SILVER"
                )
                final_records.append(child_item)

        if final_records:
            for record in final_records:
                record.feedback_score = feedback_score
                record.feedback_percentage = feedback_pct
                record.is_top_rated = is_top_rated
                record.has_bent_pins = has_bent_pins
            return final_records

        logger.warning(f" [⚠️] Multi-SKU Schema Exception: All fallback matrices missed for parent listing ID: {base_item.item_id}")
        return []

    def parse_standalone_item_hydration(self, html_content: str, item: MarketItem, strategy: Optional[Any] = None) -> MarketItem:
        if not html_content:
            logger.warning(f"⚠️ Blank HTML response packet passed to hydrator for item {item.item_id}")
            return item

        active_strategy = strategy or getattr(item, "strategy", None) or getattr(self, "strategy", None)

        if active_strategy:
            item = active_strategy.extract_specific_attributes(html_content, item)
            item.data_grade = "SILVER"
        else:
            logger.error(f"❌ Missing strategy context layer for item {item.item_id}.")
            item.is_for_parts_or_not_working = (item.condition_id == 7000)
            item.process_state = "HYDRATED"
            item.data_grade = "SILVER"

        item.is_parsed_by_agent = True
        return item

    def fetch_raw_item_page(self, item_url: str) -> Optional[str]:
        """
        Retrieves the raw HTML of an individual item page to facilitate
        deep hydration of SILVER/GOLD grade records.
        """
        logger.debug(f"🕵️‍♂️ Initiating deep harvest for: {item_url}")

        # Reuse your existing robust provider routing logic
        # This ensures you respect quota and proxy rotation even for leaf pages
        proxy_params = {
            "url": item_url,
            "render": "true",
            "premium": "true"
        }

        try:
            # Assuming you use a dispatch pattern similar to search_historical_sales
            response = self.dispatch_scrape(proxy_params)
            if response and response.status_code == 200:
                return response.text

            logger.warning(f"⚠️ Leaf fetch failed for {item_url} with status: {getattr(response, 'status_code', 'N/A')}")
            return None

        except Exception as e:
            logger.error(f"❌ Critical failure during deep harvest fetch: {e}")
            return None
