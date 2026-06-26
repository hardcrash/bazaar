# src/api/ebay/providers/base_proxy_provider.py
#
# Purpose: Abstract base class enforcing interface typing compliance for downstream
# proxy engines while centralizing constructor signature safety matrices.

from typing import Dict, Any, Tuple, Optional
from loguru import logger

class BaseProxyProvider:
    """
    Unified abstract provider layer establishing parameters and constructor layouts 
    across all derived proxy integration strategy systems.
    """
    def __init__(self, *args, **kwargs):
        """
        Hardened base constructor engineered to correctly map legacy single-arg, 
        dual-arg, and variable keyword configurations without dropping system state context.
        """
        # 1. Resolve localized sub-provider configuration blocks cleanly
        self.provider_cfg: Dict[str, Any] = kwargs.get("provider_cfg") or kwargs.get("provider_config") or {}
        
        # 2. Extract shared core global application config runtime state safely
        self.config: Optional[Any] = kwargs.get("config")

        # 3. Handle complex positional fallback layouts gracefully
        if args:
            if len(args) >= 2:
                self.config = args[0]
                if not self.provider_cfg:
                    self.provider_cfg = args[1]
            elif len(args) == 1:
                # If only one item arrives, deduce identity by dict type or structural key composition
                if isinstance(args[0], dict) and any(k in args[0] for k in ["api_key", "api-key", "base_url"]):
                    if not self.provider_cfg:
                        self.provider_cfg = args[0]
                else:
                    if self.config is None:
                        self.config = args[0]

        # 4. Enforce structural type defaults to eliminate downstream missing dictionary errors
        if not isinstance(self.provider_cfg, dict):
            self.provider_cfg = dict(self.provider_cfg) if hasattr(self.provider_cfg, '__dict__') else {}
            
        if self.config is None:
            self.config = {}

    def build_request_params(self, target_url: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """
        Compiles base URLs, query components, headers, and credentials into a
        unified outbound parameter bundle. Must be implemented by derived child strategy classes.
        
        Returns:
            Tuple[str, Dict[str, Any], Dict[str, Any]]: (request_url, payload_params, active_headers)
        """
        logger.critical(f"🚨 Interface Execution Violation: build_request_params not implemented on child layout.")
        raise NotImplementedError("Derived proxy providers must explicitly override build_request_params().")