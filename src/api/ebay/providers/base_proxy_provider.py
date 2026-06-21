# src/api/ebay/providers/base_proxy_provider.py
from typing import Dict, Any, Tuple


class BaseProxyProvider:
    # 🛠️ HARDENING: Give both parameters safe fallbacks so it's physically impossible to throw a missing positional error
    def __init__(self, config: Any = None, provider_cfg: Dict[str, Any] = None):
        self.config = config if config is not None else {}
        self.provider_cfg = provider_cfg if provider_cfg is not None else {}

    def build_request_params(self, target_url: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """Returns (request_url, payload_params, headers)"""
        raise NotImplementedError
