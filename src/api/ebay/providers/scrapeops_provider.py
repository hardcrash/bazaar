# src/api/ebay/providers/scrapeops_provider.py
#
# Purpose: Decoupled ScrapeOps engine strategy, configuring out-of-the-box routing
# payloads, geographic constraints, and DOM selector synchronization rules.

import json
from typing import Dict, Any, Tuple
from urllib.parse import unquote
from loguru import logger
from src.api.ebay.providers.base_proxy_provider import BaseProxyProvider

class ScrapeOpsProvider(BaseProxyProvider):
    def __init__(self, *args, **kwargs):
        """
        Delegates to the base proxy provider constructor to safely unpack configuration
        dictionaries, global system states, and variable position configurations.
        """
        super().__init__(*args, **kwargs)

    def build_request_params(self, target_url: str) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """
        Compiles base URLs, query components, headers, and authentication blocks
        into a unified, fully validated outbound proxy parameter bundle with 
        hardened headless wait conditions and language localization pinning.
        """
        # 1. Safely extract token using whatever dictionary name was populated in base setup
        api_key = (self.provider_cfg.get("api_key") or self.provider_cfg.get("api-key") or "").strip()
        if not api_key:
            logger.warning("⚠️ ScrapeOpsProvider initialized with an empty credentials token configuration.")

        # 2. Rebuild the base tracking endpoint matching the explicit ScrapeOps interface layout
        base_url = (self.provider_cfg.get("base_url") or "https://proxy.scrapeops.io").strip().rstrip("/")
        endpoint = (self.provider_cfg.get("endpoint_path") or "v1").strip("/")

        request_url = f"{base_url}/{endpoint}" if endpoint else base_url
        if not request_url.endswith('/'):
            request_url += '/'

        # 3. Clean target URL parameters to shield against double-encoding by HTTP clients
        clean_target_url = unquote(target_url)

        # 4. Resolve JS execution requirements based on whether selector tracing is requested
        # If a wait_for_selector condition exists, render_js MUST be True.
        has_custom_wait = "wait_for_selector" in self.provider_cfg
        render_js_val = self.provider_cfg.get("render_js", True if has_custom_wait else False)

        # 5. Assemble payload mapping parameters to native ScrapeOps types
        payload = {
            "api_key": api_key,
            "url": clean_target_url,
            "country": self.provider_cfg.get("country", "us"),
            "render_js": render_js_val,
            "residential": self.provider_cfg.get("residential", True)
        }

        # Handle wait parameters safely if JS execution engine loop is enabled
        if payload["render_js"]:
            payload["wait_for_selector"] = self.provider_cfg.get(
                "wait_for_selector", 
                "ul.srp-results, div.srp-river-results, li.s-item"
            )

        # 6. Process bypass cache overrides safely if dynamically provided
        bypass_cache_val = self.provider_cfg.get("bypass_cache", True)
        if isinstance(bypass_cache_val, str):
            payload["bypass_cache"] = bypass_cache_val.lower() == "true"
        else:
            payload["bypass_cache"] = bool(bypass_cache_val)

        # Hard-pin matching transport context expectations to match US localization rules
        active_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        # --- Provider-Level Deep Diagnostics Logging Matrix ---
        sanitized_payload = {
            k: (v if k not in ['api_key', 'api-key'] else '***')
            for k, v in payload.items()
        }

        logger.debug(f"⚙️ [ENGINE INTERNAL] Target Request URL: {request_url}")
        logger.debug(f"⚙️ [ENGINE INTERNAL] Payload Object: {json.dumps(sanitized_payload)}")
        logger.debug(f"⚙️ [ENGINE INTERNAL] Configured Transport Headers: {json.dumps(active_headers)}")

        return request_url, payload, active_headers