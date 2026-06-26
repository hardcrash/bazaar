# src/api/ebay/providers/base_proxy_provider.py

from typing import Dict, Any, Tuple

class BaseProxyProvider:
    def __init__(self, config: Any, provider_cfg: Dict[str, Any]):
        self.config = config
        self.provider_cfg = provider_cfg

    def build_request_params(self, target_url: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """Returns (request_url, payload_params, headers)"""
        raise NotImplementedError
