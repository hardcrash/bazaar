# src/api/ebay/providers/scraperapi_provider.py
#
# Purpose: Decoupled ScraperAPI engine strategy, configuring out-of-the-box routing
# payloads, bypass configurations, and localization flags.

import json
from typing import Dict, Any, Tuple
from urllib.parse import unquote
from loguru import logger
from src.api.ebay.providers.base_proxy_provider import BaseProxyProvider

class ScraperApiProvider(BaseProxyProvider):
    def __init__(self, *args, **kwargs):
        """
        Delegates to the base proxy provider constructor to safely unpack configuration
        dictionaries, global system states, and variable position configurations.
        """
        super().__init__(*args, **kwargs)

    def build_request_params(self, target_url: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """
        Compiles base URLs, query components, headers, and authentication blocks
        into a unified outbound proxy parameter bundle targeting ScraperAPI endpoints.
        """
        api_key = self.provider_cfg.get("api_key", "").strip()

        base_url = (self.provider_cfg.get("base_url") or "http://api.scraperapi.com").strip().rstrip('/')
        endpoint_path = (self.provider_cfg.get("endpoint_path") or "").strip().strip('/')
        request_url = f"{base_url}/{endpoint_path}" if endpoint_path else base_url

        # Use the unquoted target URL to prevent double-encoding downstream
        clean_target_url = unquote(target_url)

        # 1. Base Core Payload Parameters
        payload = {
            "api_key": api_key,
            "url": clean_target_url,
            "premium": "true",
            "skip_cache": "true",
            "keep_headers": "false",  # Let ScraperAPI optimize header fingerprint generation
            "country_code": self.provider_cfg.get("country_code", "us")
        }

        # 2. Add Session Stickiness if provided in config
        if self.provider_cfg.get("session_id"):
            payload["session_number"] = str(self.provider_cfg.get("session_id"))

        # 3. Strip manual headers to prevent proxy fingerprint mismatches
        active_headers = {} 

        # --- Provider-Level Deep Diagnostics Logging Matrix ---
        sanitized_payload = {
            k: (v if k not in ['api_key', 'api-key'] else '***')
            for k, v in payload.items()
        }

        logger.debug(f"⚙️ [ENGINE INTERNAL] Target Request URL: {request_url}")
        logger.debug(f"⚙️ [ENGINE INTERNAL] Payload Object: {json.dumps(sanitized_payload)}")

        return request_url, payload, active_headers