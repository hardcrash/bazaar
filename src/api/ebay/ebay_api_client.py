# src/api/ebay/ebay_client.py

import requests
import base64
import logging
from typing import List, Optional, Union

logger = logging.getLogger("BazaarPipeline")

class EbayApiClient:
    def __init__(self, config):
        self.config = config

        # Handle AppConfig top-level attributes or look into a .params dictionary fallback
        if hasattr(config, "params"):
            params_dict = config.params
        else:
            params_dict = getattr(config, "_raw_config_data", {})

        # Resolve sandbox environment variables
        self.use_sandbox = getattr(config, "use_sandbox", params_dict.get("use_sandbox", True))
        env_key = "ebay_sandbox" if self.use_sandbox else "ebay_production"
        
        # Pull environment credentials safely
        creds = getattr(config, env_key, params_dict.get(env_key, {}))
        self.client_id = creds.get("client_id")
        self.client_secret = creds.get("client_secret")

        # Session network infrastructure setup
        self.session = requests.Session()
        self.platform_name = "ebay"

        # Endpoints allocation matching chosen environment context
        self.base_url = "https://api.sandbox.ebay.com" if self.use_sandbox else "https://api.ebay.com"
        self.auth_url = f"{self.base_url}/identity/v1/oauth2/token"

        self.active_search_url = f"{self.base_url}/buy/browse/v1/item_summary/search"
        self.historical_search_url = f"{self.base_url}/buy/browse/v1/item_summary/search"

    def _get_token_for_scope(self, scope: str) -> Optional[str]:
        """Fetches an isolated token matching the specific scope context required."""
        credential_string = f"{self.client_id}:{self.client_secret}"
        encoded_creds = base64.b64encode(credential_string.encode("utf-8")).decode("utf-8")

        headers = {
            "Authorization": f"Basic {encoded_creds}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "grant_type": "client_credentials",
            "scope": scope
        }

        try:
            response = self.session.post(self.auth_url, headers=headers, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                logger.error(f"[❌] OAuth Failed for scope [{scope}]: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"[❌] Network failure during token acquisition: {e}")
            return None

    def _build_filter_string(
        self,
        condition_input: Optional[Union[int, List[int]]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        category_id: Optional[str] = None,
        base_clauses: Optional[List[str]] = None
    ) -> Optional[str]:
        """Helper to safely build and format native REST filter string rules dynamically."""
        clauses = list(base_clauses) if base_clauses else []

        if condition_input:
            if isinstance(condition_input, list):
                cond_str = "|".join(str(c) for c in condition_input)
                clauses.append(f"conditions:{{{cond_str}}}")
            else:
                clauses.append(f"conditions:{{{condition_input}}}")

        if min_price is not None or max_price is not None:
            low = f"{min_price:.2f}" if min_price is not None else "*"
            high = f"{max_price:.2f}" if max_price is not None else "*"
            clauses.append(f"price:[{low}..{high}]")

        if category_id and category_id.strip():
            clauses.append(f"categoryIds:{{{category_id.strip()}}}")

        return ",".join(clauses) if clauses else None

    def _print_dry_run_url(self, url: str, headers: dict, params: dict):
        """Helper to rebuild and print the exact target string with encoded parameters."""
        req = requests.Request("GET", url, headers=headers, params=params)
        prepared = req.prepare()
       #print(f"🌐 [API TARGET URL] -> {prepared.url}")

    def search_active_items(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        condition_id: Optional[Union[int, List[int]]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        category_id: Optional[str] = None,
        dry_run: bool = False
    ) -> List[dict]:
        """Queries currently active sales listings using standard browse scope."""
        token = self._get_token_for_scope("https://api.ebay.com/oauth/api_scope")
        if not token:
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        params = {"q": query, "limit": limit}
        if offset > 0:
            params["offset"] = offset

        filter_str = self._build_filter_string(condition_id, min_price, max_price, category_id)
        if filter_str:
            params["filter"] = filter_str

        if dry_run:
            self._print_dry_run_url(self.active_search_url, headers, params)

        try:
            response = self.session.get(self.active_search_url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json().get("itemSummaries", [])
            else:
                logger.error(f"[❌] Active Search Failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"[-] Network exception during eBay active search layout: {e}")
        return []

    def search_historical_sales(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        condition_id: Optional[Union[int, List[int]]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        category_id: Optional[str] = None,
        dry_run: bool = False
    ) -> List[dict]:
        """Queries completed listings through the regular browse API proxy scope configuration."""
        token = self._get_token_for_scope("https://api.ebay.com/oauth/api_scope")
        if not token:
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        params = {"q": query, "limit": limit}
        if offset > 0:
            params["offset"] = offset

        base_clauses = ["buyingOptions:{FIXED_PRICE|AUCTION}"]
        filter_str = self._build_filter_string(condition_id, min_price, max_price, category_id, base_clauses)
        if filter_str:
            params["filter"] = filter_str

        if dry_run:
            self._print_dry_run_url(self.historical_search_url, headers, params)

        try:
            response = self.session.get(self.historical_search_url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json().get("itemSummaries", [])
            else:
                logger.error(f"[❌] Browse Historical Emulation Failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"[-] Network exception during eBay historical search fallback layout: {e}")
        return []
