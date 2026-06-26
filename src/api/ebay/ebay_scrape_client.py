# src/api/ebay/ebay_scrape_client.py
#
# Purpose: Orchestrates data translation, structural DOM item extraction cascades,
# Multi-SKU variation parsing, and individual listing attribute hydration maps for
# processing downstream records into high-grade database targets.

import json
import random
import re
import datetime
import requests
import os
import sys
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup, Tag
from loguru import logger
from pathlib import Path
from urllib.parse import urlencode

from src.core.models import MarketItem
from src.api.ebay.ebay_scrape_provider import EbayScraperProvider
from src.api.ebay.providers.scrapeops_provider import ScrapeOpsProvider
from src.api.ebay.providers.scraperapi_provider import ScraperApiProvider

class EbayScrapeClient:
    """
    Data translation component focused strictly on HTML payload ingestion, Layout Parsing,
    Multi-SKU Expansion, and Hydrating records into higher data grades.
    """

    # --- Hardened System Selection Matrix ---
    # Unified configuration hooks engineered to seamlessly extract structural values from traditional 
    # desktop grids, minimal mobile lists, and highly nested alternative modular card layouts simultaneously.
    EBAY_SELECTORS_MATRIX = {
        "containers": [
            "li.s-card",                                 # Alternative modular card outer row container
            "div.su-card-container",                     # Alternative inner component structural wrapper
            "li.s-item",                                 # Standard Desktop grid/list row wrapper
            "div.s-item__wrapper",                       # Standard Desktop inner block element wrapper
            "ul.srp-results > li",                       # Baseline structural container catch-all
            "div[class*='item-container']",              # Dynamic wildcard: generic item row fallback
            "div[class*='card-container']"               # Dynamic wildcard: generic layout component fallback
        ],
        "titles": [
            ".s-card__title",                            # Cleanest atomic modular card item text line
            ".s-item__title",                            # Standard Desktop row title text path
            "h3.s-item__title",                          # Explicit sub-header layout variation tag
            "[class*='card__title']",                    # Fluid variant fallback: card style title matchers
            "[class*='item__title']",                    # Fluid variant fallback: row style title matchers
            "span[role='heading']"                       # High-stability accessible reader fallback anchor
        ],
        "prices": [
            "span.s-card__price",                        # Precise atomic match for compound typography lists
            ".s-card__price",                            # Core modular layout layout tier pricing tag
            ".s-item__price.INLINE",                     # Live market tracking standard inline pricing component
            ".s-item__price.POSITIVE",                   # Historic standard green "Sold" pricing designator
            ".s-item__price .POSITIVE",                  # Nested structural historic green price identifier
            ".s-item__price",                            # Unfiltered generic desktop fallback pricing anchor
            "[class*='item__price']",                    # Structural safety net: shifting desktop element paths
            "[class*='card__price']"                     # Structural safety net: shifting alternative element paths
        ],
        "shipping": [
            ".su-card-container__attributes__secondary", # Isolated meta block capturing clean alternative metrics
            ".s-item__shipping",                         # Standard desktop logistic text content wrapper
            ".s-item__logisticsCost",                    # Legacy platform API backend raw logistics element tag
            "[class*='shipping']",                       # Broad fallback: wildcard text string cost parsing
            "[class*='logistics']",                      # Broad fallback: wildcard text string cost parsing
            ".s-card__attribute-row .secondary"          # Low-level semantic markup component safety net
        ],
        "sellers": [
            ".su-card-container__attributes__secondary", # Alternative shared layout vendor detail field mapping
            ".s-item__seller-info",                      # Standard desktop vendor metrics and store rating container
            "[class*='seller-info']",                    # Universal fallback: fluid vendor tag variations
            "[class*='seller__info']"                     # Universal fallback: fluid vendor tag variations
        ]
    }
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
        """
        Executes a targeted historical sales sweep on eBay by compiling criteria, 
        routing requests dynamically via weighted proxy gateways, and parsing results.
        """
        self.provider.enforce_politeness()
        target_ebay_url = self._build_target_url(query, min_price, max_price, category_id, conditions)
        logger.info(f"🔗 Target Upstream eBay URL Generated: {target_ebay_url}")

        proxy_config = getattr(self.provider.config, "proxy_rotation", {})
        configured_providers = proxy_config.get("providers", {})

        raw_sequence = self._resolve_provider_sequence(configured_providers, strategy)

        # CAPACITY-BASED ROUTING INTERCEPTION
        provider_sequence = sorted(
            raw_sequence,
            key=lambda k: self.provider._runtime_credits.get(k, 0),
            reverse=True
        )

        response_html = None

        for provider_key in provider_sequence:
            current_balance = self.provider._runtime_credits.get(provider_key, 0)

            if current_balance <= 0:
                logger.warning(f"Provider {provider_key} exhausted ({current_balance} credits). Skipping configuration block.")
                self.provider.flag_provider_exhausted(provider_key)
                continue

            try:
                provider_cfg = configured_providers.get(provider_key, {})
                provider_engine = self._instantiate_provider_engine(provider_key, provider_cfg)
                if not provider_engine:
                    continue

                request_url, payload, active_headers = provider_engine.build_request_params(target_ebay_url)

                logger.success(
                    f"🚀 ROUTING CHOICE | Active Provider Strategy: [{provider_key.upper()}] "
                    f"(Credits: {current_balance})"
                )
                logger.debug(f"⚙️ Compiled Request URL: {request_url}")
                self._log_sanitized_payload(payload)

                logger.info(f"📡 Dispatching outbound HTTP request via {provider_key}...")
                response = requests.get(
                    request_url,
                    params=payload,
                    headers=active_headers if active_headers else None,
                    timeout=self.provider.timeout
                )

                raw_text = response.text or ""
                logger.info(
                    f"📥 RESPONSE RECEIVED | Provider: [{provider_key.upper()}] | "
                    f"Status Code: {response.status_code} | Payload Size: {len(raw_text)} characters"
                )

                # INLINE DIAGNOSTIC DUMP
                if any(flag in sys.argv for flag in ["--dev", "-dev", "-d"]):
                    self._dump_network_response(raw_text, response.status_code, provider_key, context="search")
                    self._write_network_checkpoint(provider_key, response.status_code, raw_text)

                if hasattr(self.provider, "update_quota_header"):
                    self.provider.update_quota_header(provider_key, response)

                if response.status_code in [401, 403, 429]:
                    logger.error(f"🔒 Authentication rejection / Quota Exceeded (Status {response.status_code}) on {provider_key}.")
                    if hasattr(self.provider, "flag_provider_exhausted"):
                        self.provider.flag_provider_exhausted(provider_key)
                    continue

                if not self._validate_html_integrity(provider_key, response.status_code, raw_text):
                    continue

                response_html = raw_text
                break

            except Exception as loop_err:
                logger.error(f"Provider {provider_key} failed execution loop network transport layer: {loop_err}")
                continue        

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

    def _build_target_url(
        self, 
        query: str, 
        min_price: float, 
        max_price: float, 
        category_id: str, 
        conditions: Optional[List[int]]
    ) -> str:
        cleaned_query = " ".join(query.split())
        query_params = {
            "_nkw": cleaned_query,
            "LH_Complete": "1",
            "LH_Sold": "1",
            "rt": "nc",
            "_ipg": "100",
            "_sop": "13",  
            "_pgn": "1"
        }

        if category_id and str(category_id).lower() != "global root":
            query_params["_sacat"] = str(category_id)

        if conditions:
            query_params["LH_ItemCondition"] = ",".join(map(str, conditions))

        if min_price is not None:
            query_params["_udlo"] = f"{min_price:.2f}"
            
        if max_price is not None:
            query_params["_udhi"] = f"{max_price:.2f}"

        encoded_params = urlencode(query_params)
        return f"https://www.ebay.com/sch/i.html?{encoded_params}"

    def _resolve_provider_sequence(self, configured_providers: dict, strategy: Any) -> List[str]:
        available_keys = list(configured_providers.keys())

        if str(strategy).lower() == "weighted_random":
            runtime_balances = {
                k: self.provider._runtime_credits.get(k, 0) 
                for k in available_keys 
                if self.provider._runtime_credits.get(k, 0) > 0
            }
            
            if not runtime_balances:
                return available_keys 

            weighted_sequence = []
            candidates = list(runtime_balances.keys())
            weights = list(runtime_balances.values())
            
            while candidates:
                chosen = random.choices(candidates, weights=weights, k=1)[0]
                weighted_sequence.append(chosen)
                idx = candidates.index(chosen)
                candidates.pop(idx)
                weights.pop(idx)
                
            return weighted_sequence + [k for k in available_keys if k not in weighted_sequence]

        available_keys.sort(key=lambda k: str(strategy).lower() in k.lower(), reverse=True)
        return available_keys

    def _instantiate_provider_engine(self, provider_key: str, provider_cfg: dict) -> Optional[Any]:
        key_lower = provider_key.lower()
        try:
            if "scraperapi" in key_lower:
                return ScraperApiProvider(self.provider.config, provider_cfg)
            elif "scrapeops" in key_lower:
                return ScrapeOpsProvider(self.provider.config, provider_cfg)
            
            logger.error(f"⚠️ Unrecognized structural provider string configuration: {provider_key}")
            return None
        except TypeError:
            if "scraperapi" in key_lower:
                return ScraperApiProvider(provider_cfg=provider_cfg)
            elif "scrapeops" in key_lower:
                return ScrapeOpsProvider(provider_cfg=provider_cfg)
        return None

    def _log_sanitized_payload(self, payload: dict) -> None:
        sanitized = {
            k: (v if k not in ['api_key', 'api-key'] else '***')
            for k, v in payload.items()
        }
        logger.debug(f"⚙️ Compiled Proxy Parameters: {json.dumps(sanitized)}")

    def _write_network_checkpoint(self, provider_key: str, status_code: int, raw_text: str) -> None:
        try:
            with open("raw_network_checkpoint.txt", "w", encoding="utf-8") as f:
                f.write(f"TIMESTAMP: {datetime.datetime.now()}\nPROVIDER: {provider_key}\nSTATUS CODE: {status_code}\n")
                f.write(f"RESPONSE LENGTH: {len(raw_text)}\n" + "-" * 50 + "\n")
                f.write(raw_text if raw_text else "[EMPTY BODY]")
            logger.info("📡 Dropped full network diagnostic checkpoint to raw_network_checkpoint.txt")
        except Exception as checkpoint_err:
            logger.error(f"⚠️ Failed to write raw network checkpoint: {checkpoint_err}")

    def _validate_html_integrity(self, provider_key: str, status_code: int, raw_text: str) -> bool:
        html_lower = raw_text.lower()
        
        has_items_raw = (
            "s-item__wrapper" in raw_text or
            'li class="s-item' in raw_text or
            "srp-results" in html_lower or
            "srp-river" in html_lower or
            "/itm/" in html_lower
        )

        is_valid = (
            status_code == 200 and 
            bool(raw_text) and 
            "captcha" not in html_lower and 
            "robot check" not in html_lower and 
            "security measure" not in html_lower and 
            "attention required" not in html_lower and 
            has_items_raw
        )

        title_match = re.search(r"<title>(.*?)</title>", raw_text, re.IGNORECASE)
        page_title = title_match.group(1).strip() if title_match else "NO TITLE FOUND"

        if not is_valid:
            logger.warning(
                f"❌ [BOGUS RESPONSE] Headless layout validation failed for {provider_key}. "
                f"Title: '{page_title}' | Has s-item container variant: {has_items_raw}"
            )
            try:
                with open(f"debug_{provider_key.lower()}_response.html", "w", encoding="utf-8") as f:
                    f.write(raw_text)
            except Exception as err:
                logger.error(f"Failed to write bogus response dump: {err}")
            return False

        logger.debug(f"🔍 Content Integrity Audit | Page Title: '{page_title}' | Raw 's-item' Substring Found: True")
        return True
    
    def select_weighted_provider(self, gateway_status: dict) -> str:
        active_pools = {
            provider_id: credits 
            for provider_id, credits in gateway_status.items() 
            if credits > 0
        }

        if not active_pools:
            raise RuntimeError("❌ Severe System Exhaustion: All registered routing gateways show 0 available credits.")

        providers = list(active_pools.keys())
        credit_weights = list(active_pools.values())
        total_available_credits = sum(credit_weights)
        
        chosen_provider = random.choices(providers, weights=credit_weights, k=1)[0]
        selection_probability = (active_pools[chosen_provider] / total_available_credits) * 100
        
        logger.info(
            f"🎯 WEIGHTED ROUTING CHOSEN | Provider: [{chosen_provider.upper()}] "
            f"({active_pools[chosen_provider]} cr remaining | Chance: {selection_probability:.1f}%)"
        )
        return chosen_provider

    def _parse_ebay_html(self, html_content: str, model_name: str, category_id: str, is_sold: bool = True) -> List[Any]:
        soup = BeautifulSoup(html_content, 'html.parser')
        listings, strategy_used = self._isolate_listing_nodes(soup)

        if not listings:
            logger.warning("⚠️ No raw item listing container elements matched the structural DOM query.")
            body_snippet = soup.body.text[:200].strip() if soup.body else "NO BODY TAG"
            logger.debug(f"🩻 Body text snippet: {body_snippet}")
            return []

        logger.info(f"🔍 DOM Ingestion Engine isolated {len(listings)} element nodes via strategy: [{strategy_used}]")

        results = []
        metrics = {"no_title": 0, "shop_on": 0, "no_price": 0, "price_conv": 0, "exceptions": 0}

        for item in listings:
            try:
                title = self._extract_title(item)
                if not title:
                    metrics["no_title"] += 1
                    continue
                if "shop on" in title.lower():
                    metrics["shop_on"] += 1
                    continue

                item_id, item_url = self._extract_identifiers(item)                    
                if not item_id or not item_url:
                    continue

                price_data = self._extract_price(item, title)
                if price_data is None:
                    metrics["no_price"] += 1  
                    continue
                
                price, is_msku_parent = price_data
                if price <= 0.0:
                    metrics["price_conv"] += 1
                    continue

                shipping_cost = self._extract_shipping(item)
                seller_data = self._extract_seller_metrics(item)

                market_item = MarketItem(
                    item_id=item_id,
                    model_name=model_name,
                    category=category_id,
                    raw_title=title,
                    title=title,
                    price=price,
                    shipping_cost=shipping_cost,
                    total_cost=round(price + shipping_cost, 2),
                    currency="USD",
                    condition_id=3000,  
                    is_sold=is_sold,
                    source_platform="ebay",
                    item_url=item_url,
                    process_state="PENDING_DEEP_HARVEST" if is_msku_parent else "PENDING",
                    data_grade="BRONZE"
                )
                
                # Hydrate seller keys safely if columns map down cleanly
                for key, val in seller_data.items():
                    if hasattr(market_item, key):
                        setattr(market_item, key, val)

                results.append(market_item)

            except Exception as parse_err:
                metrics["exceptions"] += 1
                logger.debug(f"🚨 Item parsing iteration failed: {type(parse_err).__name__} - {parse_err}")
                continue

        self._log_pipeline_metrics(len(listings), len(results), strategy_used, metrics)
        return results

    def _isolate_listing_nodes(self, soup: BeautifulSoup) -> Tuple[List[Any], str]:
        river_selectors = [
            "div.srp-river-results",
            "ul.srp-results",
            "#mainContent",
            ".srp-main-content",
            "#srp-river-results"
        ]
        
        river_scope = None
        for r_sel in river_selectors:
            container = soup.select_one(r_sel)
            if container:
                river_scope = container
                break
                
        active_scope = river_scope if river_scope else soup

        try:
            # Gather all candidate target containers from our dynamic configuration ledger
            selectors = self.EBAY_SELECTORS_MATRIX["containers"]
            
            listings = active_scope.select(", ".join(selectors))
            unique_listings = []
            seen_ids = set()
            
            if listings:
                for node in listings:
                    # Bubble up execution reference if selector trapped nested elements
                    if not any(k in node.get('class', []) for k in ['s-item', 's-card']) and node.name != 'li':
                        ancestor = node.find_parent('li', class_=lambda c: c and any(k in c for k in ['s-item', 's-card'])) or \
                                   node.find_parent('div', class_=lambda c: c and any(k in c for k in ['s-item', 's-card', 'su-card']))
                        if ancestor:
                            node = ancestor
                    
                    node_id = id(node)
                    if node_id not in seen_ids:
                        classes = node.get('class', [])
                        node_id_str = str(node.get("id", ""))
                        class_str = "".join(classes)
                        
                        # Filter tracking noise elements and paid placement metrics
                        if node.select_one(".s-item__ad-modifier") or node.select_one(".s-item__sponsored-label"):
                            continue
                            
                        if "s-item__placeholder" not in classes and "s-item--watch-tile" not in class_str and "listing1" not in node_id_str:
                            seen_ids.add(node_id)
                            unique_listings.append(node)
                            
                if unique_listings:
                    return unique_listings, "Hardened Primary Grid Elements"
                    
        except Exception as e:
            logger.debug(f"Stage 1 modern grid selector failed: {e}")

        try:
            item_links = active_scope.find_all('a', href=lambda h: h and '/itm/' in h)
            seen_parents = set()
            listings = []
            
            for link in item_links:
                parent = link.find_parent('li') or \
                         link.find_parent('div', class_=lambda c: c and any(k in c for k in ['s-item', 'result', 'item', 'card']))
                
                if parent and id(parent) not in seen_parents:
                    node_id_str = str(parent.get("id", ""))
                    if "listing1" not in node_id_str and not parent.select_one(".s-item__ad-modifier"):
                        seen_parents.add(id(parent))
                        listings.append(parent)
                    
            if listings:
                return listings, "Rendered JS Link-Driven Parent Extraction Engine (Scoped)"
                
        except Exception as e:
            logger.error(f"💥 Stage 4 link harvesting crashed: {e}")

        return [], "None"

    def _extract_title(self, item: Tag) -> Optional[str]:
        raw_text = None
        for selector in self.EBAY_SELECTORS_MATRIX["titles"]:
            title_node = item.select_one(selector)
            if title_node:
                if title_node.find('span'):
                    inner_spans = title_node.find_all('span')
                    raw_text = inner_spans[-1].get_text(strip=True)
                else:
                    raw_text = title_node.get_text(strip=True)
                break
                
        if not raw_text:
            img_node = item.select_one(".s-item__image-img, img")
            if img_node and img_node.get('alt'):
                raw_text = img_node.get('alt')
     
        if not raw_text:
            return None

        noise_filters = ["New Listing", "Opens in a new window or tab", "SPONSORED"]
        sanitized = raw_text
        for noise in noise_filters:
            sanitized = re.sub(re.escape(noise), "", sanitized, flags=re.IGNORECASE)
            
        return sanitized.strip()

    def _extract_identifiers(self, item: Tag) -> Tuple[Optional[str], Optional[str]]:
        item_id = item.get('data-id') or item.get('data-itemid')
        
        link_elem = (
            item.select_one(".s-item__link") or
            item.select_one("a[href*='/itm/']") or
            item.find('a')
        )
        
        item_url = ""
        if link_elem and link_elem.has_attr('href'):
            item_url = link_elem['href'].split('?')[0]

        if not item_id and item_url:
            item_id_match = re.search(r'/itm/(\d+)', item_url)
            if item_id_match:
                item_id = item_id_match.group(1)

        if not item_id or not item_url or "/itm/" not in item_url:
            return None, None

        return item_id, item_url

    def _extract_price(self, item: Tag, title: str) -> Optional[Tuple[float, bool]]:
        price_elem = None
        for selector in self.EBAY_SELECTORS_MATRIX["prices"]:
            price_elem = item.select_one(selector)
            if price_elem:
                break
                
        if not price_elem:
            # Last-ditch structural layout sweep if elements aren't tagged directly
            price_elem = item.select_one("[class*='item__price']") or item.select_one("[class*='card__price']")
            
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

    def _extract_shipping(self, item: Tag) -> float:
        shipping_elem = None
        for selector in self.EBAY_SELECTORS_MATRIX["shipping"]:
            shipping_elem = item.select_one(selector)
            if shipping_elem:
                break
                
        if not shipping_elem:
            return 0.0

        raw_text = shipping_elem.get_text(" ", strip=True).lower()
        if "free" in raw_text:
            return 0.0

        match = re.search(r'\d+(?:[.,]\d+)?', raw_text)
        if not match:
            return 0.0

        return float(match.group(0).replace(',', '.'))

    def _extract_seller_metrics(self, item: Tag) -> dict:
        metrics = {"seller_username": None, "feedback_score": None, "feedback_percentage": None}
        seller_container = None
        
        for selector in self.EBAY_SELECTORS_MATRIX["sellers"]:
            seller_container = item.select_one(selector)
            if seller_container:
                break
                
        if not seller_container:
            return metrics

        raw_text = seller_container.get_text(" ", strip=True)
        user_match = re.search(r'^([\w\.\-]+)', raw_text)
        if user_match:
            metrics["seller_username"] = user_match.group(1)

        score_match = re.search(r'\((\d+)\)', raw_text)
        if score_match:
            metrics["feedback_score"] = int(score_match.group(1))

        pct_match = re.search(r'(\d+(?:\.\d+)?)%', raw_text)
        if pct_match:
            metrics["feedback_percentage"] = float(pct_match.group(1))

        return metrics

    def dispatch_scrape(self, target_url: str, max_retries: int = 3) -> Optional[str]:
        for attempt in range(max_retries):
            provider = getattr(self.provider, "current_strategy", "weighted_random")
            if provider == "weighted_random":
                provider = "scraperapi_gmail_cmk" # Fallback explicit string hook if unresolved

            try:
                proxy_rotation = getattr(self.config, "proxy_rotation", {})
                providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else getattr(proxy_rotation, "providers", {})
                p_cfg = providers_cfg.get(provider, {})        

                if "scraperapi" in provider.lower():
                    provider_engine = ScraperApiProvider(self.provider.config, p_cfg)
                elif "scrapeops" in provider.lower():
                    provider_engine = ScrapeOpsProvider(self.provider.config, p_cfg)
                else:
                    logger.error(f"❌ Unknown or unsupported provider target engine signature: {provider}")
                    break

                request_url, payload, active_headers = provider_engine.build_request_params(target_url)
                logger.debug(f"[{attempt + 1}/{max_retries}] Dispatching sub-page scrape to {provider}")

                timeout_val = getattr(self.provider, "timeout", 20)
                response = requests.get(
                    request_url,
                    params=payload,
                    headers=active_headers,
                    timeout=timeout_val
                )

                if hasattr(self.provider, "update_quota_header"):
                    self.provider.update_quota_header(provider, response)

                raw_text = response.text or ""

                if response.status_code == 200:
                    logger.info(f"📥 RESPONSE RECEIVED | Provider: [{provider}] | Status Code: 200")
                    
                    if any(flag in sys.argv for flag in ["--dev", "-dev", "-d"]):
                        self._dump_network_response(raw_text, response.status_code, provider, context="leaf")
                        self._write_network_checkpoint(provider, response.status_code, raw_text)

                    if "captcha" not in raw_text.lower():
                        return raw_text
                    logger.warning(f"⚠️ {provider} hit a soft CAPTCHA block during deep leaf hydration.")

                elif response.status_code in [401, 403]:
                    logger.error(f"🔒 Token pool depleted on {provider}. Liquidating availability.")
                    if hasattr(self.provider, "flag_provider_exhausted"):
                        self.provider.flag_provider_exhausted(provider)
                    break
                else:
                    logger.error(f"🚨 Severe structural server anomaly ({response.status_code}) on {provider}.")
                    if hasattr(self.provider, "flag_provider_exhausted"):
                        self.provider.flag_provider_exhausted(provider)

            except Exception as e:
                logger.error(f"Circuit breaker sweep attempt failed: {e}")

        return None
    
    def _log_pipeline_metrics(self, total: int, hydrated: int, strategy: str, metrics: dict):
        logger.info(f"📊 Loop complete. Hydrated {hydrated}/{total} items using strategy [{strategy}].")
        if any(count > 0 for count in metrics.values()):
            logger.warning(
                f"🛑 Dropback Triage Failure Summary | "
                f"Missing Title: {metrics['no_title']} | "
                f"'Shop On' Ad Filters: {metrics['shop_on']} | "
                f"Missing Price DOM: {metrics['no_price']} | "
                f"Conversion Failures: {metrics['price_conv']} | "
                f"Crashes: {metrics['exceptions']}"
            )

    def parse_msku_item_page(self, html_content: str, base_item: MarketItem) -> List[MarketItem]:
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
        logger.debug(f"🕵️‍♂️ Initiating deep harvest for: {item_url}")
        provider = getattr(self.provider, "current_strategy", "")
        if not provider:
            logger.error("❌ Direct leaf harvest aborted: No active proxy strategy initialized.")
            return None

        try:
            html_payload = self.dispatch_scrape(target_url=item_url)
            if html_payload and "captcha" not in html_payload.lower():
                return html_payload

            logger.warning(f"⚠️ Leaf hydration sweep returned empty or blocked string stream for {item_url}")
            return None
        except Exception as e:
            logger.error(f"❌ Critical failure during deep harvest fetch: {e}")
            return None
        
    def _dump_network_response(self, raw_text: str, status_code: int, provider_key: str, context: str = "search"):
        output_dir = "request_responses"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%H%M%S_%f")
        clean_provider = str(provider_key).lower().replace(":", "_")
        filename = f"{timestamp}_{clean_provider}_{context}_status_{status_code}.html"
        full_path = os.path.join(output_dir, filename)

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(raw_text or "")
            logger.info(f"💾 Live network diagnostic snapshot committed -> {full_path}")
        except Exception as e:
            logger.error(f"Failed writing local debug snapshot matrix: {e}")

    def _is_multisku_parent(self, *args, **kwargs) -> bool:
        """Fallback stub filter for multi-sku components."""
        return False