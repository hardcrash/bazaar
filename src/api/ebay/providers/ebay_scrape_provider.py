# src/api/ebay/ebay_scrape_provider.py
#
# Purpose: Infrastructure and telemetry component focused strictly on proxy state management,
# billing/balance check updates, rate-limiting rules, and runtime circuit breakers.

import time
import random
import requests
from typing import Dict, List, Any, Tuple
from loguru import logger

from src.api.ebay.providers.scrapeops_provider import ScrapeOpsProvider
from src.api.ebay.providers.scraperapi_provider import ScraperApiProvider


class EbayScrapeProvider:
    """
    Dedicated infrastructure layer managing network availability, provider key initialization,
    billing/balance telemetry, and circuit breakers for anti-bot bypass.
    """
    def __init__(self, config):
        self.config = config
        self.timeout = getattr(config, "api_timeout_seconds", 30)
        self.last_request_time = time.perf_counter() - 10.0
        self.min_wait = 1.5
        self.max_wait = 6.0
        self._active_blacklist: List[str] = []
        self._balances_already_refreshed = False
        self.current_strategy = getattr(getattr(config, "proxy_rotation", {}), "strategy", "weighted_random")

        # Dynamic runtime attributes to hold active key allocations
        self.scraperapi_key = ""
        self.scrapeops_key = ""
        self._runtime_credits: Dict[str, int] = {}

        # 🛠️ Safe Hydration of Provider Keys from Nested Config Matrix
        proxy_config = getattr(config, "proxy_rotation", {})
        if isinstance(proxy_config, dict) and proxy_config.get("enabled"):
            providers = proxy_config.get("providers", {}) or {}

            # --- Dynamic Substring Scanning Loop ---
            for provider_key, provider_cfg in providers.items():
                api_key = provider_cfg.get("api_key", "")

                if "scraperapi" in provider_key.lower() and api_key:
                    self.scraperapi_key = api_key
                    self._runtime_credits[provider_key] = 0  # To be populated by balance checker
                elif "scrapeops" in provider_key.lower() and api_key:
                    self.scrapeops_key = api_key
                    self._runtime_credits[provider_key] = 1000  # Default layout buffer state
                elif api_key:
                    # Fallback configuration for variations
                    self._runtime_credits[provider_key] = 1000
        else:
            # Fallback to legacy top-level attributes if rotation structure isn't populated
            self.scraperapi_key = getattr(config, "scraperapi_key", "")
            self.scrapeops_key = getattr(config, "scrapeops_key", "")

            if self.scraperapi_key:
                self._runtime_credits["scraperapi"] = 0
            if self.scrapeops_key:
                self._runtime_credits["scrapeops"] = 1000

        # Quick structural audit logging based on unified status flags
        if not self.scraperapi_key:
            logger.warning("⚠️ No active or enabled ScraperAPI key signature found in config.")
        if not self.scrapeops_key:
            logger.warning("⚠️ No active or enabled ScrapeOps key signature found in config.")

        # Trigger dynamic upstream account balance sync
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
        """Queries proxy billing endpoints and safely updates runtime credit states."""
        if self._balances_already_refreshed:
            return

        proxy_rot = getattr(self.config, "proxy_rotation", {})
        providers = proxy_rot.get("providers", {}) if isinstance(proxy_rot, dict) else getattr(proxy_rot, "providers", {})

        for name in list(self._runtime_credits.keys()):
            p_info = providers.get(name, {})
            api_key = p_info.get("api_key") or p_info.get("api_key_str", "")

            if not api_key:
                logger.warning(f"⚠️ No API Key discovered for provider '{name}' in config. Disabling.")
                self._runtime_credits[name] = 0
                continue

            name_lower = name.lower()
            try:
                # --- ScraperAPI Balance Engine ---
                if "scraperapi" in name_lower:
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
                        logger.error(f"❌ ScraperAPI [{name}] Balance API returned status {res.status_code}. Liquidating allowance.")
                        self._runtime_credits[name] = 0

                # --- ScrapeOps Balance Engine ---
                elif "scrapeops" in name_lower:
                    res = requests.get(f"https://backend.scrapeops.io/v1/proxy/account/usage?api_key={api_key}", timeout=5)
                    
                    if res.status_code == 200:
                        data = res.json()
                        inner_data = data.get("data", {}) if isinstance(data, dict) else {}
                        
                        if "api_credits_remaining" in inner_data:
                            self._runtime_credits[name] = int(inner_data.get("api_credits_remaining", 0))
                        elif "remaining_credits" in inner_data:
                            self._runtime_credits[name] = int(inner_data.get("remaining_credits", 0))
                        else:
                            remaining = data.get("api_credits_remaining", data.get("remaining_credits"))
                            if remaining is not None:
                                self._runtime_credits[name] = int(remaining)
                            else:
                                logger.warning(f"⚠️ Unable to locate credit tokens inside ScrapeOps response layout for [{name}]. Defaulting to 0.")
                                self._runtime_credits[name] = 0
                    elif res.status_code in [401, 403]:
                        logger.error(f"🔒 ScrapeOps Auth Rejection ({res.status_code}) for pool [{name}]. Invalid key or unverified email. Setting allowance to 0.")
                        self._runtime_credits[name] = 0
                    else:
                        logger.error(f"❌ ScrapeOps [{name}] Balance API returned unexpected status code {res.status_code}. Setting allowance to 0.")
                        self._runtime_credits[name] = 0

            except Exception as e:
                logger.warning(f"Could not fetch live credits for {name}: {type(e).__name__} - {e}. Liquidating pool buffer state.")
                self._runtime_credits[name] = 0

        self._balances_already_refreshed = True

    def execute_request(self, target_url: str, strategy: str, max_retries: int = 3) -> Tuple[int, str]:
        """
        Orchestrates network failovers across proxy pools based on credit capacity sequence.
        Returns a structured response tuple of (status_code, response_text).
        """
        self.enforce_politeness()

        # Build execution sequence: non-blacklisted pools sorted highest-credits first
        available_providers = [
            p for p in self._runtime_credits.keys() 
            if p not in self._active_blacklist and self._runtime_credits[p] > 0
        ]
        provider_sequence = sorted(available_providers, key=lambda k: self._runtime_credits[k], reverse=True)

        if not provider_sequence:
            logger.critical("🚨 Execution Interrupted: All downstream proxy configuration targets exhausted or blacklisted.")
            return 503, ""

        proxy_rotation = getattr(self.config, "proxy_rotation", {})
        providers_cfg = proxy_rotation.get("providers", {}) if isinstance(proxy_rotation, dict) else {}

        for provider_key in provider_sequence:
            p_cfg = providers_cfg.get(provider_key, {})

            for attempt in range(max_retries):
                try:
                    if "scraperapi" in provider_key.lower():
                        engine = ScraperApiProvider(self.config, p_cfg)
                    elif "scrapeops" in provider_key.lower():
                        engine = ScrapeOpsProvider(self.config, p_cfg)
                    else:
                        logger.error(f"❌ Unknown or unsupported provider key signature: {provider_key}")
                        break

                    request_url, payload, active_headers = engine.build_request_params(target_url)
                    logger.debug(f"🛸 [{provider_key}] Dispatching attempt {attempt + 1}/{max_retries} -> {target_url}")

                    response = requests.get(
                        request_url,   
                        params=payload,
                        headers=active_headers,
                        timeout=self.timeout
                    )

                    self.update_quota_header(provider_key, response)

                    if response.status_code in [401, 403, 429]:
                        logger.warning(f"🔒 Token depletion or firewall block (Status {response.status_code}) on {provider_key}. Liquidating pool access.")
                        self.flag_provider_exhausted(provider_key)
                        break  # Break out of retries for this provider, drop back to next sequence target

                    raw_text = response.text or ""
                    if response.status_code == 200:
                        if "captcha" in raw_text.lower():
                            logger.warning(f"⚠️ Soft CAPTCHA intercepted on {provider_key} leaf hydration stream. Retrying attempt...")
                            continue
                        return response.status_code, raw_text

                    logger.error(f"🚨 Structural anomaly packet received (Status {response.status_code}) on {provider_key}.")

                except Exception as e:
                    logger.error(f"Circuit breaker loop sweep failed on {provider_key}: {e}")
                    continue

        return 500, ""

    def get_credit_summary(self) -> Dict[str, int]:
        """Returns a snapshot of currently known remaining credit allowances."""
        return self._runtime_credits.copy()

    def flag_provider_exhausted(self, provider: str):
        """Liquidates operational availability state for a specific provider block."""
        if provider in self._runtime_credits:
            self._runtime_credits[provider] = 0
        if provider not in self._active_blacklist:
            self._active_blacklist.append(provider)

    def update_quota_header(self, provider: str, response: requests.Response):
        """Parses real-time downstream response headers to align proxy token states."""
        if not response or not hasattr(response, 'headers'):
            return

        provider_lower = provider.lower()
        if "scraperapi" in provider_lower:
            remaining = response.headers.get("X-Amz-Meta-X-Quota-Remaining") or response.headers.get("x-scraperapi-quota-remaining")
            if remaining and str(remaining).isdigit():
                self._runtime_credits[provider] = int(remaining)