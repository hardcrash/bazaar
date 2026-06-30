# src/analysis/active_analysis_controller.py
"""
Bazaar Active Market Analysis Controller

Orchestrates live marketplace sweeps using official platform REST APIs. 
Routes unstructured payloads directly through concrete category evaluation strategies
to filter layout noise and ensure robust validation before committing items to the database.
"""

import time
from loguru import logger
from typing import Dict, Any, Optional, List

from src.analysis.base_controller import BaseController
from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory
from src.core.models import ActiveMarketItem

class ActiveAnalysisController(BaseController):
    def run_harvest(self,
                    query: Optional[str] = None,
                    category_id: Optional[str] = None,
                    model_name: Optional[str] = None,
                    strategy: Optional[Any] = None,
                    **kwargs) -> Dict[str, Any]:

        self.log_gateway_status()
        start_time = time.perf_counter()

        # 1. Hydrate our consolidated strategy object via the single-class factory
        if strategy is None:
            strategy = AnalysisStrategyFactory.get_strategy(
                category_key=self.category_name,
                config=self.config_data
            )

        model_name = model_name or "5800X"
        
        # Pull category id directly out of active_harvest slice settings
        harvest_cfg = strategy.config.get("active_harvest", {})
        category_id = category_id or str(harvest_cfg.get("ebay_category_id", "164"))

        # 2. Build our query with compiled exclusion filtering blocks
        if not query:
            fmt = strategy.config.get("search_format", "Ryzen {model}")
            base_query = fmt.format(model=model_name)
            
            # Read from unified categories structure keys
            blacklist_words = strategy.config.get("blacklist_words", []) or strategy.config.get("local_noise_blacklist", [])
            exclusions = " ".join([f"-{word}" for word in blacklist_words])
            query = f"{base_query} {exclusions}".strip()

        # 3. Generate pricing step windows
        target_passes = []
        conditions_configured = harvest_cfg.get("ebay_condition", [2000, 3000, 7000])

        for min_p, max_p in strategy.get_price_brackets(target_type="active"):
            target_passes.append({
                "name": "ACTIVE_UNIFORM_SWEEP",
                "conditions": conditions_configured,
                "min_p": min_p,
                "max_p": max_p
            })

        logger.info(f"Launching Spot Harvesting Sweep for category: {self.category_name} (Target: {model_name})")

        all_validated_items: List[ActiveMarketItem] = []

        # 4. Perform network sweeps
        for p_idx, target in enumerate(target_passes):
            logger.info(f"🔄 Active Sourcing Pass [{p_idx + 1}/{len(target_passes)}]: {target['min_p']} to {target['max_p']}")
            
            raw_summaries = self.ebay_api_client.search_active_items(
                query=query,
                min_price=target['min_p'],
                max_price=target['max_p'],
                category_id=category_id,
                condition_id=target['conditions']
            )
            
            if not raw_summaries:
                continue

            for raw_item in raw_summaries:
                try:
                    # Map API parameters into strategy processing data keys
                    shipping_opts = raw_item.get("shippingOptions", [{}])
                    shipping_cost = float(shipping_opts[0].get("shippingCost", {}).get("value", 0.0)) if shipping_opts else 0.0
                    
                    normalized_data = {
                        "item_id": raw_item.get("itemId"),
                        "source_platform": "ebay",
                        "title": raw_item.get("title", ""),
                        "price": float(raw_item.get("price", {}).get("value", 0.0)),
                        "shipping": shipping_cost,
                        "condition_id": int(raw_item.get("conditionId", 3000)),
                        "seller_username": raw_item.get("seller", {}).get("username"),
                        "item_url": raw_item.get("itemWebUrl", ""),
                        "bid_count": int(raw_item.get("bidCount", 0)),
                        "quantity_available": int(raw_item.get("quantityLimitPerBuyer", 1)),
                        "image_urls": [raw_item.get("image", {}).get("imageUrl")] if raw_item.get("image") else []
                    }

                    # 🎯 FIXED: Let the strategy handle validation, model checks, and parsing entirely!
                    validated_listing = strategy.parse_active(raw_data=normalized_data, target_model=model_name)
                    if validated_listing:
                        all_validated_items.append(validated_listing)
                        
                except Exception as parse_err:
                    logger.debug(f"Skipping malformed live listing frame: {parse_err}")

        if not all_validated_items:
            logger.warning("⚠️ Active pipeline search pass produced 0 index results after strategy validation.")
            return {"status": "EMPTY", "inserted_records": 0, "total_processed": 0}

        # 5. Filter against existing primary key IDs in database
        unseen_items = self.filter_new_items(all_validated_items)

        if not unseen_items:
            logger.success("✨ Active items monitored match localized records perfectly. 0 updates needed.")
            return {"status": "SUCCESS", "inserted_records": 0, "total_processed": len(all_validated_items)}

        # 6. Database Commit (Dry run flags removed—this is the real deal)
        logger.info(f"💾 Persisting {len(unseen_items)} verified live listings directly into database...")
        inserted_counter = self.db_manager.commit_active_listings(unseen_items)

        execution_duration = time.perf_counter() - start_time
        logger.info(f"⏱️ Active monitoring loop complete in {execution_duration:.2f} seconds.")

        return {
            "status": "SUCCESS",
            "inserted_records": inserted_counter,
            "total_processed": len(all_validated_items)
        }