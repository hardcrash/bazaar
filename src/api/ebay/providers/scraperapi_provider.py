from typing import Dict, Any, Tuple
from src.api.ebay.providers.base_proxy_provider import BaseProxyProvider

class ScraperApiProvider(BaseProxyProvider):
    def __init__(self, *args, **kwargs):
        """Flexible constructor wrapper capable of handling legacy single-arg or dual-arg formats."""
        # 1. Extract provider configuration block safely across all signature variations
        self.provider_cfg = kwargs.get("provider_cfg") or kwargs.get("provider_config")

        if not self.provider_cfg and args:
            # If two positional arguments arrive, provider_cfg is the second parameter
            self.provider_cfg = args[1] if len(args) > 1 else args[0]

        self.config = args[0] if (args and len(args) > 1) else kwargs.get("config", None)

        # Ensure fallback dictionaries exist to prevent downstream AttributeError exceptions
        if not isinstance(self.provider_cfg, dict):
            self.provider_cfg = {}

    def build_request_params(self, target_url: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        api_key = self.provider_cfg.get("api_key", "")

        base_url = (self.provider_cfg.get("base_url") or "http://api.scraperapi.com").strip().rstrip('/')
        endpoint_path = (self.provider_cfg.get("endpoint_path") or "").strip().strip('/')

        request_url = f"{base_url}/{endpoint_path}" if endpoint_path else base_url

        payload = {
            "api_key": api_key,
            "url": target_url,
            "premium": "true",
            "skip_cache": "true",
            "render": "true"
        }

        return request_url, payload, {}
