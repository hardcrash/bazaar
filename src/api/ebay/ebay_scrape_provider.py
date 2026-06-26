# src/api/ebay/ebay_scrape_provider.py
#
# Purpose: Infrastructure and telemetry component focused strictly on proxy state management,
# billing/balance check updates, rate-limiting rules, and runtime circuit breakers.

import time
import requests
from typing import Dict, List, Any
from loguru import logger

class EbayScraperProvider:
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
                    # ✅ FIXED: Routed to backend.scrapeops.io analytics endpoint
                    res = requests.get(f"https://backend.scrapeops.io/v1/proxy/account/usage?api_key={api_key}", timeout=5)
                    
                    if res.status_code == 200:
                        data = res.json()
                        # ScrapeOps returns credit balance info wrapped inside a top-level 'data' object wrapper
                        inner_data = data.get("data", {}) if isinstance(data, dict) else {}
                        
                        if "api_credits_remaining" in inner_data:
                            self._runtime_credits[name] = int(inner_data.get("api_credits_remaining", 0))
                        elif "remaining_credits" in inner_data:
                            self._runtime_credits[name] = int(inner_data.get("remaining_credits", 0))
                        else:
                            # Direct check fallback on root structure if schema variations are active
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