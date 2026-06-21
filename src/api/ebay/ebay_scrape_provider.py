# src/api/ebay/ebay_scrape_provider.py

import random
import time
import requests
from typing import Dict, List, Tuple
from loguru import logger

# 🌟 Strategies mapping cleanly to production nodes
from src.api.ebay.providers.scrapeops_provider import ScrapeOpsProvider
from src.api.ebay.providers.scraperapi_provider import ScraperApiProvider

class EbayScraperProvider:
    """
    Dedicated infrastructure layer managing network connectivity, provider strategy delegation,
    billing/balance telemetry, and circuit breakers for anti-bot bypass.
    """

    # 🌟 Registry mapping matching production-ready provider module files
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
        self.current_strategy = "scraperapi"

        # 🛠️ Safe Hydration of Provider Keys from Nested Config Matrix
        proxy_config = getattr(config, "proxy_rotation", {})
        if isinstance(proxy_config, dict) and proxy_config.get("enabled"):
            providers = proxy_config.get("providers", {})
            self.scraperapi_key = providers.get("scraperapi", {}).get("api_key", "")
            self.scrapeops_key = providers.get("scrapeops", {}).get("api_key", "")
        else:
            # Fallback to legacy top-level attributes if rotation structure isn't populated
            self.scraperapi_key = getattr(config, "scraperapi_key", "")
            self.scrapeops_key = getattr(config, "scrapeops_key", "")

        # Quick structural audit logging
        if not self.scraperapi_key:
            logger.warning("⚠️ ScraperAPI key missing or empty in configuration layout.")
        if not self.scrapeops_key:
            logger.warning("⚠️ ScrapeOps key missing or empty in configuration layout.")

        self._runtime_credits: Dict[str, int] = {
            "scraperapi": 0,
            "scrapeops": 0
        }
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
            # Read either standard api_key or nested mapping configurations
            api_key = p_info.get("api_key") or p_info.get("api_key_str", "")

            if not api_key:
                logger.warning(f"⚠️ No API Key discovered for provider '{name}' in config. Disabling.")
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
                        logger.error(f"❌ ScraperAPI Account Balance API returned status {res.status_code}. Setting allowance to 0.")
                        self._runtime_credits[name] = 0

                elif name == "scrapeops":
                    res = requests.get(f"https://proxy.scrapeops.io/v1/account?api_key={api_key}", timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, dict):
                            # Handle all common ScrapeOps API payload structures safely
                            if "api_credits_remaining" in data:
                                self._runtime_credits[name] = int(data.get("api_credits_remaining", 0))
                            elif "remaining_credits" in data:
                                self._runtime_credits[name] = int(data.get("remaining_credits", 0))
                            else:
                                limit = data.get("credit_limit", data.get("limit", 1000))
                                used = data.get("credit_used", data.get("used", 0))
                                self._runtime_credits[name] = max(0, limit - used)
                    else:
                        # Fixed: Explicitly drop credit matrix to zero on network or key rejection
                        logger.error(f"❌ ScrapeOps Account Balance API returned status code {res.status_code}. Setting allowance to 0.")
                        self._runtime_credits[name] = 0

            except Exception as e:
                logger.warning(f"Could not fetch live credits for {name}: {type(e).__name__} - {e}")
                self._runtime_credits[name] = 0

        self._balances_already_refreshed = True

    def get_credit_summary(self) -> Dict[str, int]:
        """Returns a snapshot of currently known remaining credit allowances."""
        return self._runtime_credits.copy()

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

        # --- Dynamic Strategy Order Resolution ---
        providers = ["scrapeops", "scraperapi"]
        if str(strategy).lower() == "scraperapi":
            providers = ["scraperapi", "scrapeops"]

        response_html = None

        # --- Core Provider Failover Pipeline Loop ---
        for provider in providers:
            try:
                # 1. Quota Pre-Flight Check (Reads directly from your manager class balance state)
                if self.provider._runtime_credits.get(provider, 0) <= 0:
                    logger.warning(f"Provider {provider} exhausted. Skipping configuration block.")
                    self.provider.flag_provider_exhausted(provider)
                    continue

                # 2. Dynamic Provider Class Extraction & Instantiation
                proxy_config = getattr(self.provider.config, "proxy_rotation", {}).get("providers", {})
                provider_cfg = proxy_config.get(provider, {})

                if provider == "scraperapi":
                    from src.api.ebay.providers.scraperapi_provider import ScraperApiProvider
                    # Satisfies BaseProxyProvider.__init__(self, config, provider_cfg)
                    provider_engine = ScraperApiProvider(self.provider, provider_cfg)

                elif provider == "scrapeops":
                    from src.api.ebay.providers.scrapeops_provider import ScrapeOpsProvider
                    # Satisfies BaseProxyProvider.__init__(self, config, provider_cfg)
                    provider_engine = ScrapeOpsProvider(self.provider, provider_cfg)
                else:
                    logger.error(f"⚠️ Unrecognized structural provider string configuration: {provider}")
                    continue

                # Build fully isolated parameters using decoupled classes
                request_url, payload, active_headers = provider_engine.build_request_params(target_ebay_url)
                current_provider = provider

                logger.success(f"🚀 ROUTING CHOICE | Active Provider Strategy: [{current_provider.upper()}]")
                logger.debug(f"⚙️ Compiled Request URL: {request_url}")
                logger.debug(f"⚙️ Compiled Proxy Parameters: {json.dumps({k: (v if k != 'api_key' else '***') for k, v in payload.items()})}")

                # 3. Network Transport Execution
                logger.info(f"📡 Dispatching outbound HTTP request via {current_provider}...")
                response = requests.get(
                    request_url,
                    params=payload,
                    headers=active_headers if active_headers else None,
                    timeout=self.provider.timeout
                )

                # 4. Telemetry Extraction
                raw_text = response.text or ""
                logger.info(f"📥 RESPONSE RECEIVED | Provider: [{current_provider.upper()}] | Status Code: {response.status_code} | Payload Size: {len(raw_text)} characters")

                # 5. Continuous Network Diagnostic Drop
                try:
                    with open("raw_network_checkpoint.txt", "w", encoding="utf-8") as f:
                        f.write(f"TIMESTAMP: {datetime.datetime.now()}\nPROVIDER: {current_provider}\nSTATUS CODE: {response.status_code}\n")
                        f.write(f"RESPONSE LENGTH: {len(raw_text)}\n" + "-" * 50 + "\n")
                        f.write(raw_text if raw_text else "[EMPTY BODY]")
                    logger.info("📡 Dropped full network diagnostic checkpoint to raw_network_checkpoint.txt")
                except Exception as checkpoint_err:
                    logger.error(f"⚠️ Failed to write raw network checkpoint: {checkpoint_err}")

                self.provider.update_quota_header(current_provider, response)

                # 6. Hard Rejection Checking (Auth / Rate limits)
                if response.status_code in [401, 403, 429]:
                    logger.error(f"🔒 Authentication rejection / Quota Exceeded (Status {response.status_code}) on {current_provider}.")
                    self.provider.flag_provider_exhausted(current_provider)
                    continue

                # 7. Soft Content Rejection Check (CAPTCHAs or missing layout anchors)
                html_lower = raw_text.lower()

                # Hardened Layout Guard: Verifies that layout grid elements are structural, avoiding loose title strings
                has_items_raw = "s-item__wrapper" in raw_text or 'li class="s-item' in raw_text

                if response.status_code != 200 or not raw_text or "captcha" in html_lower or "robot check" in html_lower or "security measure" in html_lower or "attention required" in html_lower or not has_items_raw:

                    title_match = re.search(r"<title>(.*?)</title>", raw_text, re.IGNORECASE)
                    page_title = title_match.group(1).strip() if title_match else "NO TITLE FOUND"
                    logger.warning(f"❌ [BOGUS RESPONSE] Headless layout validation failed for {current_provider}. Title: '{page_title}' | Has s-item container: {has_items_raw}")

                    with open(f"debug_{current_provider.lower()}_response.html", "w", encoding="utf-8") as f:
                        f.write(raw_text)
                    continue

                # 8. Integrity Audit Passed
                title_match = re.search(r"<title>(.*?)</title>", raw_text, re.IGNORECASE)
                page_title = title_match.group(1).strip() if title_match else "NO TITLE FOUND"
                logger.debug(f"🔍 Content Integrity Audit | Page Title: '{page_title}' | Raw 's-item' Substring Found: True")

                response_html = raw_text
                break

            except Exception as e:
                logger.error(f"Provider {provider} failed execution loop network transport layer: {e}")
                continue

        # --- Extrapolate Sourcing Content Out-of-Bounds ---
        if response_html:
            return self._parse_ebay_html(
                html_content=response_html,
                model_name=model_name,
                category_id=category_id,
                is_sold=True
            )

        logger.critical("❌ All configured proxy networks exhausted, unauthorized, or failing layout validation.")
        return []
    def get_proxied_request_params(
        self,
        target_url: str,
        provider_override: Optional[str] = None
    ) -> Tuple[str, dict, dict, str]:
        """
        Compiles API keys, base parameters, and targets for proxy networks.
        """
        # 1. Determine which provider to use (fall back to internal default if None)
        active_provider = provider_override if provider_override else self.current_strategy

        # Normalize to lowercase if your internal configurations expect it
        active_provider = active_provider.lower()

        # 2. Match your existing payload generation matrix
        # (Adapt the snippet below to match how your actual keys and dicts are organized)
        payload = {}
        active_headers = {"User-Agent": "BazaarData-Engine/1.0"}
        request_url = target_url

        if active_provider == "scraperapi":
            request_url = "http://api.scraperapi.com"
            payload = {
                "api_key": self.scraperapi_key,
                "url": target_url,
                "keep_headers": "true"
            }
        elif active_provider == "scrapeops":
            request_url = "https://proxy.scrapeops.io/v1/"
            payload = {
                "api_key": self.scrapeops_key,
                "url": target_url
            }
        else:
            raise ValueError(f"Unknown provider routing target: {active_provider}")

        # Return: proxy endpoint url, parameter payload dict, headers dict, normalized provider string
        return request_url, payload, active_headers, active_provider

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

        if provider == "scraperapi":
            remaining = response.headers.get("X-Amz-Meta-X-Quota-Remaining") or response.headers.get("x-scraperapi-quota-remaining")
            if remaining and str(remaining).isdigit():
                self._runtime_credits[provider] = int(remaining)
