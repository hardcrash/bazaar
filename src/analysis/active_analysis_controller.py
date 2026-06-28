# src/analysis/active_analysis_controller.py
"""
Bazaar Active Market Analysis Controller

This module orchestrates live marketplace sweeps using official platform REST APIs. 
It bypasses legacy HTML scraping layers to query live, volatile listings, handling 
on-the-fly field extractions (including spot pricing, bidding telemetry, and image arrays) 
before validating payloads into structured ActiveMarketItem objects for database synchronization.
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
        is_dry_run = kwargs.get("dry_run", False)

        if strategy is None:
            strategy = AnalysisStrategyFactory.get_strategy(
                category_key=self.category_name,
                mode="active",
                config=self.config_data
            )

        model_name = model_name or "5800X"
        category_id = category_id or (strategy.category_id if hasattr(strategy, 'category_id') else "164")

        if not query:
            fmt = strategy.config.get("search_format", "Ryzen {model}")
            base_query = fmt.format(model=model_name)
            exclusions = " ".join([f"-{word}" for word in strategy.config.get("blacklist_words", [])])
            query = f"{base_query} {exclusions}".strip()

        # Uniform Sweep Layout Strategy Generation
        target_passes = []
        harvest_cfg = strategy.config.get("active_harvest", {})
        conditions_configured = harvest_cfg.get("ebay_condition", [2000, 3000])

        for min_p, max_p in strategy.get_price_brackets():
            target_passes.append({
                "name": "ACTIVE_UNIFORM_SWEEP",
                "conditions": conditions_configured,
                "min_p": min_p,
                "max_p": max_p
            })

        logger.info(f"Launching [LIVE MUTATION RUN] [ACTIVE] Spot Harvesting Sweep for category: {self.category_name}")

        all_validated_items: List[ActiveMarketItem] = []

        for p_idx, target in enumerate(target_passes):
            logger.info(f"🔄 Active Sourcing Pass [{p_idx + 1}/{len(target_passes)}]: {target['name']}")
            
            # Query the official REST API layer instead of historical scraper routes
            raw_summaries = self.ebay_api_client.search_active_items(
                query=query,
                min_price=target['min_p'],
                max_price=target['max_p'],
                category_id=category_id,
                condition_id=target['conditions'],
                dry_run=is_dry_run
            )
            
            if not raw_summaries:
                continue

            for item in raw_summaries:
                try:
                    # Safely extract scalar fields out of nested REST payloads
                    p_val = float(item.get("price", {}).get("value", 0.0))
                    s_val = float(item.get("shippingOptions", [{}])[0].get("shippingCost", {}).get("value", 0.0))
                    
                    # Capture structural image URLs from primary and secondary fields
                    img_list = []
                    if "image" in item and "imageUrl" in item["image"]:
                        img_list.append(item["image"]["imageUrl"])
                    for add_img in item.get("additionalImages", []):
                        if "imageUrl" in add_img:
                            img_list.append(add_img["imageUrl"])

                    # Strongly-typed conversion matching our domain hierarchy base
                    validated_listing = ActiveMarketItem(
                        item_id=item.get("itemId", ""),
                        model_name=model_name,
                        category=self.category_name,
                        raw_title=item.get("title", ""),
                        title=item.get("title", ""),
                        price=p_val,
                        shipping_cost=s_val,
                        total_cost=p_val + s_val,
                        currency=item.get("price", {}).get("currency", "USD"),
                        item_url=item.get("itemWebUrl", ""),
                        seller_username=item.get("seller", {}).get("username"),
                        bid_count=int(item.get("bidCount", 0)),
                        quantity_available=int(item.get("quantityLimitPerBuyer", 1)),
                        image_urls=img_list
                    )
                    all_validated_items.append(validated_listing)
                except Exception as parse_err:
                    logger.debug(f"Skipping malformed live listing structural frame: {parse_err}")

        if not all_validated_items:
            logger.warning("⚠️ Active pipeline search pass produced 0 index results.")
            return {"status": "EMPTY", "inserted_records": 0, "total_processed": 0}

        # Filter against active listings cache if required by architecture
        unseen_items = self.filter_new_items(all_validated_items)

        if not unseen_items:
            logger.success("✨ Active items monitored match localized records perfectly.")
            return {"status": "SUCCESS", "inserted_records": 0, "total_processed": len(all_validated_items)}

        inserted_counter = 0
        if not is_dry_run:
            logger.info(f"💾 Persisting {len(unseen_items)} updated live state nodes into active database layers...")
            inserted_counter = self.db_manager.commit_active_listings(unseen_items)
        else:
            inserted_counter = len(unseen_items)

        execution_duration = time.perf_counter() - start_time
        logger.info(f"⏱️ Active monitoring loop complete in {execution_duration:.2f} seconds.")

        return {
            "status": "SUCCESS",
            "inserted_records": inserted_counter,
            "total_processed": len(all_validated_items)
        }
