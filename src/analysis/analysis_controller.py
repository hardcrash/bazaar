# src/analysis/analysis_controller.py

import time
from loguru import logger
from typing import Dict, Any, Optional

from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory
from src.api.ebay.ebay_scrape_client import EbayScrapeClient
from src.database.db_manager import DatabaseManager

class AnalysisController:
    def __init__(self, config, category: str = "CPU"):
        self.config_data = config
        self.category_name = category.upper()

        # 1️⃣ Core Sourcing Client Engine
        self.scrape_client = EbayScrapeClient(config=config)

        # 2️⃣ Hydrate relational persistence data store dependency
        self.db_manager = DatabaseManager(config=config)

        # 3️⃣ Hydrate automated baseline analytics tracking service
        # If your class is initialized slightly differently, adjust it here.
        # self.analytics_service = HistoricalAggregatorService(config=config)
        self.analytics_service = getattr(self, "analytics_service", None)

    def run_harvest(self,
                    query: Optional[str] = None,
                    min_price: Optional[float] = None,
                    max_price: Optional[float] = None,
                    category_id: Optional[str] = None,
                    model_name: Optional[str] = None,
                    strategy: Optional[Any] = None,
                    **kwargs) -> Dict[str, Any]:

        self.scrape_client.refresh_account_balances()
        credits = self.scrape_client.get_credit_summary()
        logger.info(f"⚡ Proxy Gateway Status: {credits}")

        """
        Executes a complete 2-Stage data harvest sweep.
        Leverages AnalysisStrategyFactory to dynamically instantiate the operational rules layer.
        """
        start_time = time.perf_counter()

        harvest_mode = kwargs.get("mode", "historical")
        is_dry_run = kwargs.get("dry_run", False)

        # Resolve strategies cleanly via your Factory pattern
        if strategy is None:
            logger.debug(f"Factory resolving strategy matrix for category: {self.category_name} [{harvest_mode.upper()}]")
            strategy = AnalysisStrategyFactory.get_strategy(
                category_key=self.category_name,
                mode=harvest_mode,
                config=self.config_data
            )

        # Hydrate defaults from strategy rules boundaries if parameters aren't given explicitly
        model_name = model_name or "5800X"
        category_id = category_id or (strategy.category_id if hasattr(strategy, 'category_id') else "164")
        query = query or "Ryzen 5800X -BUNDLE -LAPTOP -PC -BAREBONES -SYSTEM -OPTANE -P4800X -P5800X -METER -RADIO"

        if min_price is None or max_price is None:
            bounds = getattr(strategy, "price_bounds", (115.00, 650.00))
            min_price = min_price if min_price is not None else bounds[0]
            max_price = max_price if max_price is not None else bounds[1]

        logger.info(f"Launching [LIVE MUTATION RUN] [{harvest_mode.upper()}] Harvesting Sweep for category: {self.category_name}")
        if is_dry_run:
            logger.warning("🧪 Dry Run mode flag active! Database write operations will be simulated.")

        logger.info(f"Targeting Query: '{query}' | Category ID: {category_id}")
        logger.debug(f"Slicing Bracket Range: ${min_price:.2f} to ${max_price:.2f}")

        # ------------------------------------------------------------------
        # PRE-FLIGHT CAPA_CITY GUARD: Verify provider credit telemetry limits
        # ------------------------------------------------------------------
        if harvest_mode == "historical" and hasattr(self.scrape_client, "get_remaining_credits"):
            account_check = self.scrape_client.get_remaining_credits()
            if account_check.get("status") == "SUCCESS":
                remaining = account_check.get("remaining", 0)
                if remaining < 50:
                    logger.critical(f"🚨 CRITICAL: ScraperAPI capacity exhausted ({remaining} left)! Aborting execution window.")
                    return {"status": "INSUFFICIENT_CREDITS", "inserted_records": 0, "total_processed": 0}
            else:
                logger.warning("⚠️ Could not verify credit balance parameters. Proceeding at risk...")

        # ------------------------------------------------------------------
        # STAGE 1: Search Scrape / Initial Inventory Assessment
        # ------------------------------------------------------------------
        raw_summaries = self.scrape_client.search_historical_sales(
            query=query,
            min_price=min_price,
            max_price=max_price,
            category_id=category_id,
            model_name=model_name,
            strategy=strategy
        )

        if not raw_summaries:
            logger.warning(f"⚠️ Stage 1 returned 0 raw matching summaries for pattern '{model_name}'. Terminating pipeline early.")
            return {"status": "EMPTY", "inserted_records": 0, "total_processed": 0}

        logger.debug(f"Captured {len(raw_summaries)} items from slice bracket pool.")

        standard_items = [item for item in raw_summaries if item.process_state != "PENDING_DEEP_HARVEST"]
        msku_items = [item for item in raw_summaries if item.process_state == "PENDING_DEEP_HARVEST"]

        final_items_to_commit = []
        final_items_to_commit.extend(standard_items)

        # ------------------------------------------------------------------
        # STAGE 2: Multi-SKU Deep Variation Extraction Loop
        # ------------------------------------------------------------------
        if msku_items:
            logger.info(f"Stage 2 Deep Harvesting: Processing {len(msku_items)} multi-variation listings...")
            for base_item in msku_items:
                logger.debug(f"Processing Multi-Sku Matrix for Item ID: {base_item.item_id}")
                html_leaf = self.scrape_client.fetch_raw_item_page(base_item.item_url)
                if html_leaf:
                    variants = self.scrape_client.parse_msku_item_page(html_leaf, base_item)
                    if variants:
                        final_items_to_commit.extend(variants)
                else:
                    logger.warning(f"Failed to fetch product details view for parent listing container: {base_item.item_id}")
                    base_item.process_state = "PENDING"
                    final_items_to_commit.append(base_item)

        # ------------------------------------------------------------------
        # STAGE 3: Database Commit & Real-Time Reporting
        # ------------------------------------------------------------------
        total_discovered = len(final_items_to_commit)
        actual_new_inserts = 0
        ignored_duplicates = total_discovered

        if is_dry_run:
            logger.info(f"💾 [DRY RUN] Would have committed {total_discovered} verified items down to tracking store.")
        else:
            logger.info(f"💾 Committing {total_discovered} verified items down to relational tracking store...")
            # Fire data array down through your SQLAlchemy / SQLite manager layer
            actual_new_inserts = self.db_manager.commit_market_items(None, final_items_to_commit)
            ignored_duplicates = total_discovered - actual_new_inserts

            logger.success(
                f"💾 Ingestion complete. Inserted {actual_new_inserts} new records "
                f"({ignored_duplicates} duplicate index keys safely ignored)."
            )

        # ------------------------------------------------------------------
        # STAGE 4: Analytics Refresh Pipeline Trigger
        # ------------------------------------------------------------------
        if self.analytics_service and hasattr(self.analytics_service, 'update_historical_baselines'):
            logger.info("📊 Re-calculating statistical rolling data segments...")
            stat_windows = self.analytics_service.update_historical_baselines(model_name=model_name, category_id=category_id)
            logger.info(f"      └── {model_name}: Calculated {stat_windows} statistic windows.")
        else:
            logger.debug("📊 Analytics calculation service skipped (not instantiated or verified yet).")

        elapsed_seconds = time.perf_counter() - start_time
        minutes, seconds = divmod(elapsed_seconds, 60)

        logger.success(
            f"📊 [{self.category_name}] HARVESTING PIPELINE SUMMARY - "
            f"Time: {int(minutes)}m {seconds:.2f}s | "
            f"Total Target Items Found: {len(raw_summaries)} | "
            f"MSKUs Expanded: {len(msku_items)} -> {total_discovered - len(standard_items)} variants | "
            f"DB New Rows Inserted: {actual_new_inserts}"
        )

        return {
            "status": "SUCCESS",
            "inserted_records": actual_new_inserts,
            "ignored_records": ignored_duplicates,
            "total_processed": total_discovered
        }

    def filter_new_items(self, scraped_items: List[MarketItem]) -> List[MarketItem]:
        existing_ids = {row.item_id for row in self.db_session.query(MarketItem.item_id).all()}
        return [item for item in scraped_items if item.item_id not in existing_ids]


    def get_credit_summary(self) -> str:
        """Returns a formatted string of remaining credits for all providers."""
        summaries = [f"{name.upper()}: {count}" for name, count in self._runtime_credits.items()]
        return " | ".join(summaries)
