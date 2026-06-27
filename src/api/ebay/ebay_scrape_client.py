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
import yaml
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup, Tag
from loguru import logger
from pathlib import Path
from urllib.parse import urlencode

from src.core.models import MarketItem
from src.api.ebay.ebay_scrape_provider import EbayScraperProvider
from src.api.ebay.providers.scrapeops_provider import ScrapeOpsProvider
from src.api.ebay.providers.scraperapi_provider import ScraperApiProvider
from src.api.ebay.scrape_parsers.dom import (
    should_skip_title,
    find_first_match,
    bubble_to_container_root,
    is_valid_listing,
    harvest_fallback_links,
    harvest_raw_title_text,
    harvest_item_identifiers,
    extract_by_selector 
)
from src.api.ebay.scrape_parsers.metrics import sanitize_title_noise
from src.api.ebay.scrape_parsers.msku import (
    extract_msku_metadata,
    parse_msku_json,
    parse_var_model_json,
    parse_dom_sku_options
)

class EbayScrapeClient:
    """
    Data translation component focused strictly on HTML payload ingestion, Layout Parsing,
    Multi-SKU Expansion, and Hydrating records into higher data grades.
    """

    def __init__(self, config, config_path: Optional[str] = None):
        self.config = config
        self.provider = EbayScraperProvider(config=config)
        
        # 📄 Hardened Selectors Matrix Orchestration
        # Looks for settings/selectors.yaml in the project directory
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path("settings/selectors.yaml")
            
        self.EBAY_SELECTORS_MATRIX: Dict[str, List[str]] = {}
        self.load_selectors_matrix()

    def refresh_account_balances(self):
        """Proxy binding method mapping down onto the Infrastructure provider."""
        self.provider.refresh_account_balances()

    def get_credit_summary(self) -> Dict[str, int]:
        """Proxy binding method mapping down onto the Infrastructure provider."""
        return self.provider.get_credit_summary()
    
    def load_selectors_matrix(self) -> None:
        """Loads or reloads the extraction selectors directly from the local YAML configuration."""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Selectors configuration file not found at {self.config_path}")
                
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
                if not config_data or "ebay" not in config_data:
                    raise KeyError("Malformed configuration: Missing root 'ebay' selector block.")
                
                # Dig straight into the platform namespace layer
                self.EBAY_SELECTORS_MATRIX = config_data["ebay"]
                logger.info(f"Successfully loaded eBay selector matrix from {self.config_path}")
                
        except Exception as e:
            logger.error(f"⚠️ Failed to load selectors matrix: {e}. Falling back to internal defaults.")
            # Safety net configuration fallback if file reads fail
            self.EBAY_SELECTORS_MATRIX = {
                "rivers": ["div.srp-river-results", "ul.srp-results"],
                "containers": ["li.s-item", "div.s-item__wrapper"],
                "titles": [".s-item__title", "h3.s-item__title"],
                "prices": [".s-item__price"],
                "shipping": [".s-item__shipping"],
                "sellers": [".s-item__seller-info"]
            }

    def get_selectors_for(self, tier: str) -> List[str]:
        """Helper to safely retrieve a specific selector array tier with fallback protection."""
        return self.EBAY_SELECTORS_MATRIX.get(tier, [])

    def search_historical_sales(
        self,
        query: str,
        min_price: float,
        max_price: float,
        category_id: str,
        model_name: str,
        strategy: str,
        conditions: Optional[List[int]] = None
    ) -> List[MarketItem]:
        """Executes a historical sales sweep by relying on the provider engine for transport."""
        target_ebay_url = self._build_target_url(query, min_price, max_price, category_id, conditions)
        logger.info(f"🔗 Target Upstream eBay URL Generated: {target_ebay_url}")

        # Let the provider handle the massive trial-and-error routing network
        status_code, response_html = self.provider.execute_request(
            target_url=target_ebay_url, 
            strategy=strategy
        )

        # Drop a real-time network transaction snapshot to disk for diagnostics
        self._write_network_checkpoint(strategy, status_code, response_html)

        # Run content validation checks using internal layout audit mechanisms
        if not self._validate_html_integrity(strategy, status_code, response_html):
            logger.error("❌ High-grade scraping execution chain returned empty or invalid HTML payload structures.")
            return []

        return self._parse_ebay_html(response_html, model_name, category_id, is_sold=True)

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
        # eBay's legacy search endpoint is typically 'sch/i.html'
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
                skip, metric_key = should_skip_title(title)
                if skip:
                    if metric_key:
                        metrics[metric_key] += 1
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
        """Isolates the listing elements out of the DOM, pulling layout parameters directly from the selector matrix."""
        river_scope = find_first_match(soup, self.get_selectors_for("rivers"))
        active_scope = river_scope if river_scope else soup

        try:
            selectors = self.get_selectors_for("containers")
            listings = active_scope.select(", ".join(selectors))
            unique_listings = []
            seen_ids = set()
            
            if listings:
                for node in listings:
                    node = bubble_to_container_root(node)
                    node_id = id(node)
                    
                    if node_id not in seen_ids and is_valid_listing(node):
                        seen_ids.add(node_id)
                        unique_listings.append(node)
                            
                if unique_listings:
                    return unique_listings, "Hardened Primary Grid Elements"
                    
        except Exception as e:
            logger.debug(f"Stage 1 modern grid selector failed: {e}")

        try:
            listings = harvest_fallback_links(active_scope)
            if listings:
                return listings, "Rendered JS Link-Driven Parent Extraction Engine (Scoped)"
        except Exception as e:
            logger.error(f"💥 Stage 4 link harvesting crashed: {e}")

        return [], "None"

    def _extract_title(self, item: Tag) -> Optional[str]:
        """Extracts and purges titles using platform rules and categorical strategy context."""
        raw_text = harvest_raw_title_text(item, self.get_selectors_for("titles"))
        if not raw_text:
            return None
            
        # Safely extract strategy config from instance if it exists, otherwise default gracefully
        strategy_config = getattr(self, "current_strategy_config", None) or {}
        strategy_blacklist = strategy_config.get("local_noise_blacklist", [])
        
        return sanitize_title_noise(raw_text, custom_blacklist=strategy_blacklist)

    def _extract_identifiers(self, item: Tag) -> Tuple[Optional[str], Optional[str]]:   
        """Isolates unique platform identifiers and absolute listings urls without tracking parameters."""
        link_selectors = self.get_selectors_for("links")
        return harvest_item_identifiers(item, link_selectors)

    def _extract_price(self, item: Tag, title: str) -> Optional[Tuple[float, bool]]:    

        price_elem = extract_by_selector(item, self.EBAY_SELECTORS_MATRIX["prices"])
        
        if not price_elem:
            return None

        raw_text = price_elem.get_text(" ", strip=True)
        is_msku_parent = self._is_multisku_parent(item, title, raw_text)

        # 3. Parsing Logic (to be moved to metrics.py in the next step)
        if 'to' in raw_text.lower():
            raw_text = raw_text.lower().split('to')[0].strip()

        match = re.search(r'\d+(?:[.,]\d+)?', raw_text)
        if not match:
            return None

        digits = match.group(0).replace(',', '.') # Simplified for now
        try:
            val = float(digits)
            return (val, is_msku_parent) if val > 0 else None
        except ValueError:
            return None

    def _extract_shipping(self, item: Tag) -> float:
        # Use the helper to fetch the element
        shipping_elem = extract_by_selector(item, self.EBAY_SELECTORS_MATRIX["shipping"])
            
        if not shipping_elem:
            return 0.0

        raw_text = shipping_elem.get_text(" ", strip=True).lower()
        if "free" in raw_text:
            return 0.0

        match = re.search(r'\d+(?:[.,]\d+)?', raw_text)
        return float(match.group(0).replace(',', '.')) if match else 0.0

    def _extract_seller_metrics(self, item: Tag) -> dict:
        metrics = {"seller_username": None, "feedback_score": None, "feedback_percentage": None}
        seller_container = extract_by_selector(item, self.EBAY_SELECTORS_MATRIX["sellers"])
            
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
        """Streamlined legacy deep-leaf scraper target hook."""
        strategy = getattr(self.provider, "current_strategy", "weighted_random")
        status_code, response_html = self.provider.execute_request(target_url, strategy, max_retries)
        
        if status_code == 200 and "captcha" not in response_html.lower():
            return response_html
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
        if not html_content or not html_content.strip():
            logger.error(f"[❌] Deep Harvest Aborted: Empty payload for ID: {base_item.item_id}")
            return []

        # 1. Extract Shared Metadata
        metadata = extract_msku_metadata(html_content)
        
        # 2. Strategy-based Parsing
        # Try strategies in order of reliability
        final_records = parse_msku_json(html_content, base_item) or \
                        parse_var_model_json(html_content, base_item) or \
                        parse_dom_sku_options(BeautifulSoup(html_content, "html.parser"), base_item)

        # 3. Final Hydration
        if final_records:
            for record in final_records:
                for key, val in metadata.items():
                    setattr(record, key, val)
            return final_records

        logger.warning(f" [⚠️] Multi-SKU Schema Exception: All fallback matrices missed for ID: {base_item.item_id}")
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