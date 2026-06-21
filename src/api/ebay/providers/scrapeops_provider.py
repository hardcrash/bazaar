
# src/api/ebay/providers/scrapeops_provider.py

import json
from typing import Dict, Any, Tuple
from loguru import logger
from src.api.ebay.providers.base_proxy_provider import BaseProxyProvider

class ScrapeOpsProvider(BaseProxyProvider):
    def __init__(self, *args, **kwargs):
        """
        Flexible constructor wrapper capable of handling legacy single-arg
        or dual-arg initialization formats from the provider loop registry.
        """
        # 1. Isolate the custom configuration block from either kwargs or positional arguments
        self.provider_cfg = kwargs.get("provider_cfg") or kwargs.get("provider_config")

        if not self.provider_cfg and args:
            self.provider_cfg = args[1] if len(args) > 1 else args[0]

        # 2. Extract parent configuration state references safely
        self.config = args[0] if (args and len(args) > 1) else kwargs.get("config", None)

        if not isinstance(self.provider_cfg, dict):
            self.provider_cfg = {}

    def build_request_params(self, target_url: str) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """
        Compiles base URLs, query components, headers, and authentication blocks
        into a unified, fully validated outbound proxy parameter bundle.
        """
        # 1. Safely extract token using whatever dictionary name was populated
        api_key = self.provider_cfg.get("api_key") or self.provider_cfg.get("api-key")

        # 2. Rebuild the base tracking endpoint matching the explicit ScrapeOps interface layout
        base_url = self.provider_cfg.get("base_url", "https://proxy.scrapeops.io").rstrip("/")
        endpoint = self.provider_cfg.get("endpoint_path", "v1").strip("/")

        # Assemble target path and guarantee a trailing slash is locked into the request endpoint path
        request_url = f"{base_url}/{endpoint}" if endpoint else base_url
        if not request_url.endswith('/'):
            request_url += '/'

        # 3. 🎯 Force the correct underscore API key name matching live gateway requirements
        payload = {
            "api_key": api_key,
            "url": target_url,
            "country": "us"
        }

        if str(self.provider_cfg.get("bypass_cache", "true")).lower() == "true":
            payload["bypass_cache"] = "true"

        active_headers = {"Accept": "text/html"}

        # =======================================================
        # --- Provider-Level Deep Diagnostics Logging Matrix ---
        # =======================================================
        # Securely mask the authentication value regardless of key variant format
        sanitized_payload = {
            k: (v if k not in ['api_key', 'api-key'] else '***')
            for k, v in payload.items()
        }

        logger.debug(f"⚙️ [ENGINE INTERNAL] Target Request URL: {request_url}")
        logger.debug(f"⚙️ [ENGINE INTERNAL] Payload Object: {json.dumps(sanitized_payload)}")
        logger.debug(f"⚙️ [ENGINE INTERNAL] Configured Transport Headers: {json.dumps(active_headers)}")
        # =======================================================

        return request_url, payload, active_headers
