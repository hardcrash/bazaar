# src/analysis/base_controller.py

import time
from loguru import logger
from typing import Dict, Any, Optional, List

# 🚀 Bring in both client tracks cleanly
from src.api.ebay.ebay_api_client import EbayApiClient
from src.api.ebay.ebay_scrape_client import EbayScrapeClient
from src.database.db_manager import DatabaseManager

class BaseController:
    def __init__(self, config, category: str = "CPU", db_manager: Optional[DatabaseManager] = None):
        self.config_data = config
        self.category_name = category.upper()

        # Database Manager passed down as a single source of truth dependency
        self.db_manager = db_manager or DatabaseManager(config=config)

        # 🛸 Direct REST API Engine (Active Sweep Track)
        self.ebay_api_client = EbayApiClient(config=config)

        # 🕷️ Scrape client remains isolated to parsing and mapping data collections (Historical Track)
        self.scrape_client = EbayScrapeClient(config=config)
        self.analytics_service = getattr(self, "analytics_service", None)

    def log_gateway_status(self) -> None:
        """Polls provider gateway status details before execution passes."""
        if hasattr(self.scrape_client, 'provider') and self.scrape_client.provider:
            self.scrape_client.provider.refresh_account_balances()
            credits_summary = self.scrape_client.provider.get_credit_summary()
            logger.info(f"⚡ Proxy Gateway Status via Provider: {credits_summary}")
        else:
            # Fallback legacy interface matching previous client layout if provider is not yet attached
            if hasattr(self.scrape_client, 'refresh_account_balances'):
                self.scrape_client.refresh_account_balances()
                credits_summary = self.scrape_client.get_credit_summary()
                logger.info(f"⚡ Proxy Gateway Status: {credits_summary}")

    def filter_new_items(self, items: List[Any]) -> List[Any]:
        """Queries the database to identify which items are missing or require structural updates."""
        if not items:
            return []

        item_ids = [str(item.item_id) for item in items]
        existing_ids = self.db_manager.get_existing_item_ids(item_ids)

        return [item for item in items if str(item.item_id) not in existing_ids]

    @staticmethod
    def generate_price_brackets(min_p: float, max_p: float, step: float = 30.0) -> List[tuple]:
        """Utility fallback method to construct sliding window boundaries."""
        brackets = []
        current = min_p
        while current < max_p:
            upper = min(current + step, max_p)
            brackets.append((current, upper))
            current += step
        return brackets

    def run_harvest(self, *args, **kwargs) -> Dict[str, Any]:
        """To be implemented distinctly by downstream specialized subclass execution engines."""
        raise NotImplementedError("Subclasses must implement distinct execution pipelines via run_harvest().")