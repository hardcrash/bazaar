# src/api/ebay/ebay_scrape_provider.py

import json
import random
import time
import datetime
import re
import requests
from typing import Dict, List, Tuple, Any, Optional
from loguru import logger

from src.api.ebay.providers.scrapeops_provider import ScrapeOpsProvider
from src.api.ebay.providers.scraperapi_provider import ScraperApiProvider

class MarketItem: pass

class EbayScraperProvider:
    """
    Dedicated infrastructure layer managing network connectivity, provider strategy delegation,
    billing/balance telemetry, and circuit breakers for anti-bot bypass.
    """

    PROVIDER_STRATEGY_MAP = {
        "scraperapi": ScraperApiProvider,
        "scrapeops": ScrapeOpsProvider,
    }

    def __init__(self, config):
        self.config = config
        self.timeout = getattr(config, "api_timeout_seconds", 30)
        self.last_request_time = time.perf_counter() - 10.0
        self.min_wait = 1.5
        self.max_wait = 6.0
        self._active_blacklist: List[str] = []
        self._balances_already_refreshed = False

        proxy_rotation_cfg = getattr(config, "proxy_rotation", {})
        self.current_strategy = proxy_rotation_cfg.get("strategy", "weighted_random") if isinstance(proxy_rotation_cfg, dict) else "weighted_random"

        # Multi-account dynamic runtime storage map
        self._runtime_credits: Dict[str, int] = {}

        # 🛠️ Hydrate multi-account array structures dynamically
        if isinstance(proxy_rotation_cfg, dict) and proxy_rotation_cfg.get("enabled"):
            providers = proxy_rotation_cfg.get("providers", {}) or {}

            for provider_key, provider_cfg in providers.items():
                api_key = provider_cfg.get("api_key", "")
                if api_key:
                    # Dynamically initialize account slots (Buffer state updated at balance check)
                    if "scrapeops" in provider_key.lower():
                        self._runtime_credits[provider_key] = 1000
                    else:
                        self._runtime_credits[provider_key] = 0
        else:
            # Legacy system fallback compatibility strings
            scraperapi_legacy = getattr(config, "scraperapi_key", "")
            scrapeops_legacy = getattr(config, "scrapeops_key", "")
            if scraperapi_legacy:
                self._runtime_credits["scraperapi_default"] = 0
            if scrapeops_legacy:
                self._runtime_credits["scrapeops_default"] = 1000

        logger.info(f"🧬 Active multi-provider pool initialized with handles: {list(self._runtime_credits.keys())}")

        # Pull live limits on initialization
        self.refresh_account_balances()

    def enforce_politeness(self):
        """Ensures a minimum safe gap between proxy requests with random jitter."""
        elapsed = time.perf_counter() - self.last_request_time
        if elapsed < self.min_wait:
            jitter = random.uniform(0, self.max_wait - self.min_wait)
            sleep_time = (self.min_wait - elapsed) + jitter
            logger.debug(f"Politeness lock active. Throttling gateway call for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.perf_counter()

    def refresh_account_balances(self) -> None:
        """Queries explicit proxy billing accounts using configured URLs and updates runtime credit maps."""
        if self._balances_already_refreshed:
            return

        proxy_rot = getattr(self.config, "proxy_rotation", {})
        providers = proxy_rot.get("providers", {}) if isinstance(proxy_rot, dict) else {}

        for name in list(self._runtime_credits.keys()):
            p_info = providers.get(name, {})
            api_key = p_info.get("api_key")

            if not api_key:
                logger.warning(f"⚠️ Missing token payload assignment for pool target: [{name}]. Liquidating.")
                self._runtime_credits[name] = 0
                continue

            name_lower = name.lower()
            try:
                if "scraperapi" in name_lower:
                    # Extract unique host mapping if customized
                    base_url = p_info.get("base_url", "http://api.scraperapi.com")
                    res = requests.get(f"{base_url}/account?api_key={api_key}", timeout=10)
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
                        logger.error(f"❌ ScraperAPI account sub-node [{name}] balance query failed ({res.status_code}).")
                        self._runtime_credits[name] = 0

                elif "scrapeops" in name_lower:
                    base_url = p_info.get("base_url", "https://proxy.scrapeops.io")
                    path = p_info.get("endpoint_path", "v1").strip("/")
                    full_endpoint = f"{base_url}/{path}/account" if path else f"{base_url}/account"

                    res = requests.get(f"{full_endpoint}?api_key={api_key}", timeout=10)
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, dict):
                            if "api_credits_remaining" in data:
                                self._runtime_credits[name] = int(data.get("api_credits_remaining", 0))
                            elif "remaining_credits" in data:
                                self._runtime_credits[name] = int(data.get("remaining_credits", 0))
                            else:
                                limit = data.get("credit_limit", data.get("limit", 1000))
                                used = data.get("credit_used", data.get("used", 0))
                                self._runtime_credits[name] = max(0, limit - used)
                    else:
                        logger.error(f"❌ ScrapeOps account sub-node [{name}] balance query failed ({res.status_code}).")
                        self._runtime_credits[name] = 0

            except Exception as e:
                logger.warning(f"⚠️ Balancer failed telemetry sync check for target account [{name}]: {e}")
                self._runtime_credits[name] = 0

        self._balances_already_refreshed = True

    def get_remaining_quota(self, provider: str) -> int:
        return self._runtime_credits.get(provider, 0)

    # 🎯 ADD THIS METHOD BACK TO RESOLVE THE ATTRIBUTE ERROR:
    def get_credit_summary(self) -> Dict[str, int]:
        """
        Returns a clean tracking copy of the currently known
        remaining credit allowances for the controller logging loop.
        """
        return self._runtime_credits.copy()

    def calculate_adaptive_routing_strategy(self) -> str:
        """
        Dynamically weights proxy provider selection based on real-time remaining quotas.
        Falls back to static default weights from your config if live balances are empty or missing.
        """
        proxy_rotation = getattr(self.config, "proxy_rotation", {})
        providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else {}

        available_pool = [p for p in self._runtime_credits.keys() if p not in self._active_blacklist]
        if not available_pool:
            raise RuntimeError("❌ Critical Error: All multi-account strategy providers have been blacklisted.")

        calculated_weights = []
        using_live_quotas = True
        strategy_label = "LIVE ADAPTIVE QUOTA BALANCE"

        # Pull runtime remaining quota limits from internal state
        for name in available_pool:
            # 🩹 HOTFIX: Force known depleted accounts to 0 weight
            if "scrapeops_gmail_" in name:
                calculated_weights.append(0.0)
            else:
                calculated_weights.append(float(self._runtime_credits.get(name, 0)))

        # Fall back to your configuration targets if live numbers are zeroed out or unavailable
        if sum(calculated_weights) <= 0:
            using_live_quotas = False
            strategy_label = "STATIC CONFIG FILE SPECIFIED"
            calculated_weights = []
            for name in available_pool:
                p_cfg = providers_cfg.get(name, {})
                # Updated to scan for your configuration's default_weight value
                weight_val = p_cfg.get("default_weight", 16.6) if isinstance(p_cfg, dict) else 16.6
                calculated_weights.append(float(weight_val))

        total_weight = sum(calculated_weights)
        if total_weight <= 0:
            calculated_weights = [1.0] * len(available_pool)
            total_weight = sum(calculated_weights)

        normalized_odds = [w / total_weight for w in calculated_weights]
        chosen_provider = random.choices(available_pool, weights=calculated_weights, k=1)[0]

        # --- Dynamic Output Terminal Verification Matrix ---
        logger.debug(f"🧮 [ROTATION ENGINE] Weight Engine Strategy Model: [{strategy_label}]")
        for name, weight, odds in zip(available_pool, calculated_weights, normalized_odds):
            marker = "🎯" if name == chosen_provider else "   "
            metric_label = "Credits Left" if using_live_quotas else "Default Weight"
            logger.debug(f" {marker} Account Node: [{name:<30}] | {metric_label}: {int(weight) if using_live_quotas else weight:>5} | Selection Odds: {odds:>.2%}")

        return chosen_provider

    def search_historical_sales(
        self,
        query: str,
        min_price: float,
        max_price: float,
        category_id: str,
        model_name: str,
        strategy: Any,
        conditions: Optional[List[int]] = None
    ) -> List[Any]:
        self.enforce_politeness()

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
        response_html = None
        max_routing_attempts = len(self._runtime_credits) * 2

        for attempt in range(max_routing_attempts):
            try:
                # Dynamic account selection hook
                provider = self.calculate_adaptive_routing_strategy()

                if self._runtime_credits.get(provider, 0) <= 0:
                    logger.warning(f"Account target [{provider}] has zero tokens remaining. Flagging node exhausted.")
                    self.flag_provider_exhausted(provider)
                    continue

                proxy_config = getattr(self.config, "proxy_rotation", {}).get("providers", {})
                provider_cfg = proxy_config.get(provider, {})
                provider_lower = provider.lower()

                if "scraperapi" in provider_lower:
                    provider_engine = ScraperApiProvider(self, provider_cfg)
                elif "scrapeops" in provider_lower:
                    provider_engine = ScrapeOpsProvider(self, provider_cfg)
                else:
                    logger.error(f"⚠️ Unrecognized structural provider strategy string: {provider}")
                    continue

                request_url, payload, active_headers = provider_engine.build_request_params(target_ebay_url)
                current_provider = provider

                logger.success(f"🚀 ROUTING CHOICE | Active Account: [{current_provider.upper()}]")

                response = requests.get(
                    request_url,
                    params=payload,
                    headers=active_headers if active_headers else None,
                    timeout=provider_cfg.get("api_timeout_seconds", self.timeout)
                )

                raw_text = response.text or ""
                self.update_quota_header(current_provider, response)

                if response.status_code in [401, 403, 429]:
                    logger.error(f"🔒 Account token rejection code ({response.status_code}) hit on node: {current_provider}")
                    self.flag_provider_exhausted(current_provider)
                    continue

                html_lower = raw_text.lower()
                has_items_raw = "s-item__wrapper" in raw_text or 'li class="s-item' in raw_text

                if response.status_code != 200 or not raw_text or "captcha" in html_lower or "robot check" in html_lower or "security measure" in html_lower or "attention required" in html_lower or not has_items_raw:
                    logger.warning(f"❌ [BOGUS RESPONSE] Integrity check block validation failed for account: {current_provider}")
                    continue

                response_html = raw_text
                break

            except Exception as e:
                logger.error(f"Provider account node {provider} failed execution loop step: {e}")
                continue

        if response_html:
            if hasattr(self, '_parse_ebay_html'):
                return self._parse_ebay_html(
                    html_content=response_html,
                    model_name=model_name,
                    category_id=category_id,
                    is_sold=True
                )
            return [response_html]

        logger.critical("❌ Extraction Failed: All registered proxy account credentials have been exhausted.")
        return []

    def flag_provider_exhausted(self, provider: str):
        if provider in self._runtime_credits:
            self._runtime_credits[provider] = 0
        if provider not in self._active_blacklist:
            self._active_blacklist.append(provider)

    def update_quota_header(self, provider: str, response: requests.Response):
        if not response or not hasattr(response, 'headers'):
            return

        provider_lower = provider.lower()
        if "scraperapi" in provider_lower:
            remaining = response.headers.get("X-Amz-Meta-X-Quota-Remaining") or response.headers.get("x-scraperapi-quota-remaining")
            if remaining and str(remaining).isdigit():
                self._runtime_credits[provider] = int(remaining)
