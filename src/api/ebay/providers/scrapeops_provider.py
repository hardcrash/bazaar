from typing import Dict, Any, Tuple
from src.api.ebay.providers.base_proxy_provider import BaseProxyProvider

class ScrapeOpsProvider(BaseProxyProvider):
    def __init__(self, *args, **kwargs):
        """Flexible constructor wrapper capable of handling legacy single-arg or dual-arg formats."""
        self.provider_cfg = kwargs.get("provider_cfg") or kwargs.get("provider_config")

        if not self.provider_cfg and args:
            self.provider_cfg = args[1] if len(args) > 1 else args[0]

        self.config = args[0] if (args and len(args) > 1) else kwargs.get("config", None)

        if not isinstance(self.provider_cfg, dict):
            self.provider_cfg = {}

    def build_request_params(self, target_url: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        api_key = self.provider_cfg.get("api_key", "")

        base_url = (self.provider_cfg.get("base_url") or "https://proxy.scrapeops.io").strip().rstrip('/')
        endpoint_path = (self.provider_cfg.get("endpoint_path") or "v1").strip().strip('/')

        request_url = f"{base_url}/{endpoint_path}" if endpoint_path else base_url

        payload = {
            "api_key": api_key,
            "url": target_url,
            "residential": "true",
            "country": "us",
            "bypass_cache": "true",
            "render_js": "true"
        }

        return request_url, payload, {}
