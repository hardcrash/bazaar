# src/analysis/historical_analysis_controller.py

import time
from loguru import logger
from typing import Dict, Any, Optional, List

from src.analysis.base_controller import BaseController
from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory

class HistoricalAnalysisController(BaseController):
    def run_harvest(self,
                    query: Optional[str] = None,
                    category_id: Optional[str] = None,
                    model_name: Optional[str] = None,
                    strategy: Optional[Any] = None,
                    **kwargs) -> Dict[str, Any]:

        display_name = model_name or f"ID: {category_id}" or "Global Root"

        logger.info(f"Launching [LIVE MUTATION RUN] [HISTORICAL] Harvesting Sweep for category: {display_name}")

        # This ensures fresh, non-poisoned rotation rounds every time you click 'Run'
        if not hasattr(self, '_active_blacklist'):
            self._active_blacklist = []
        else:
            self._active_blacklist.clear()
            logger.debug("♻️ Active provider blacklist has been reset for the new harvest sweep.")

        self.log_gateway_status()
        start_time = time.perf_counter()
        is_dry_run = kwargs.get("dry_run", False)

        if strategy is None:
            strategy = AnalysisStrategyFactory.get_strategy(
                category_key=self.category_name,
                mode="historical",
                config=self.config_data
            )

        model_name = model_name or "5800X"
        category_id = category_id or (strategy.category_id if hasattr(strategy, 'category_id') else "164")

        # Dynamically build target queries
        if not query:
            fmt = strategy.config.get("search_format", "Ryzen {model}")
            base_query = fmt.format(model=model_name)
            exclusions = " ".join([f"-{word}" for word in strategy.config.get("blacklist_words", [])])
            query = f"{base_query} {exclusions}".strip()

        # Build Historical Dual-Pass Ranges Matrix
        target_passes = []
        harvest_cfg = strategy.config.get("historical_harvest", {})
        conditions_configured = harvest_cfg.get("ebay_condition", [2000, 3000, 7000])

        # --- Pass A: Broken / Parts Only ---
        if 7000 in conditions_configured:
            for min_p, max_p in strategy.get_price_brackets(pass_type="broken"):
                target_passes.append({
                    "name": "BROKEN/PARTS_ONLY",
                    "conditions": [7000],
                    "min_p": min_p,
                    "max_p": max_p
                })

        # --- Pass B: Used / Refurbished ---
        functional_conds = [c for c in conditions_configured if c != 7000]
        if functional_conds:
            for min_p, max_p in strategy.get_price_brackets(pass_type="used"):
                target_passes.append({
                    "name": "USED/REFURBISHED_BASELINE",
                    "conditions": functional_conds,
                    "min_p": min_p,
                    "max_p": max_p
                })

        logger.info(f"Launching [LIVE MUTATION RUN] [HISTORICAL] Harvesting Sweep for category: {self.category_name}")
        if is_dry_run:
            logger.warning("🧪 Dry Run mode flag active! Database write operations will be simulated.")

        all_collected_summaries = []

        # Execute Dual-Pass Sweep Loop
        for p_idx, target in enumerate(target_passes):
            logger.info(f"🔄 Sourcing Pass [{p_idx + 1}/{len(target_passes)}]: {target['name']}")
            pass_summaries = self.scrape_client.search_historical_sales(
                query=query,
                min_price=target['min_p'],
                max_price=target['max_p'],
                category_id=category_id,
                model_name=model_name,
                strategy=strategy,
                conditions=target['conditions']
            )

            if pass_summaries:
                logger.success(f"📈 Pass '{target['name']}' successfully captured {len(pass_summaries)} raw inventory matches.")
                all_collected_summaries.extend(pass_summaries)
            else:
                logger.warning(f"⚠️ Pass '{target['name']}' returned 0 items inside bracket boundary.")

        if not all_collected_summaries:
            logger.critical("❌ All execution loops returned zero sets. Aborting hydration pipeline.")
            return {"status": "EMPTY", "inserted_records": 0, "total_processed": 0}

        # Deduplicate using base optimization checker layer
        unseen_items = self.filter_new_items(all_collected_summaries)
        skipped_count = len(all_collected_summaries) - len(unseen_items)
        if skipped_count > 0:
            logger.info(f"🔒 API Call Protection Guard: Skipped deep checking for {skipped_count} items already present in DB.")

        if not unseen_items:
            logger.success("✨ All captured sweep items match historical records. No database changes made!")
            return {"status": "SUCCESS", "inserted_records": 0, "total_processed": len(all_collected_summaries)}

        # 🦾 OPTIMIZATION GRID: Separate items based on deep harvest necessity
        deep_harvest_items = [item for item in unseen_items if item.process_state == "PENDING_DEEP_HARVEST"]
        direct_route_items = [item for item in unseen_items if item.process_state != "PENDING_DEEP_HARVEST"]

        final_items_to_commit = []

        # 🏎️ Tier 1: Direct Route Standard Items (Instantaneous Zero-Credit Hydration)
        if direct_route_items:
            logger.info(f"🏎️ Short-circuiting {len(direct_route_items)} standard items directly to queue (Credits Saved!).")
            for base_item in direct_route_items:
                if hasattr(strategy, 'is_valid_standalone') and not strategy.is_valid_standalone(base_item):
                    logger.warning(f"⏩ Strategy Filter: Dropping item {base_item.item_id} based on validation rules.")
                    continue
                base_item.process_state = "PENDING"
                final_items_to_commit.append(base_item)

        # 🛰️ Tier 2: Premium Deep Leaf Ingestion (Restricted exclusively to complex target nodes)
        if deep_harvest_items:
            logger.info(f"🛰️ Executing premium leaf hydration loops for {len(deep_harvest_items)} high-priority variants...")
            for variant_item in deep_harvest_items:
                try:
                    html_leaf = self.scrape_client.fetch_raw_item_page(variant_item.item_url)
                    if html_leaf:
                        hydrated_item = self.scrape_client.parse_standalone_item_hydration(
                            html_leaf, variant_item, strategy=strategy
                        )
                        final_items_to_commit.append(hydrated_item)
                    else:
                        logger.warning(f"Leaf fetch missed for item {variant_item.item_id}. Retaining basic record.")
                        variant_item.process_state = "PENDING"
                        final_items_to_commit.append(variant_item)
                except RuntimeError as net_err:
                    if str(net_err) == "ALL_PROXY_PROVIDERS_DOWN":
                        logger.error("🛑 Proxy gateway cluster reported absolute depletion. Saving collected rows.")
                        break
                    raise net_err
                except Exception as leaf_err:
                    logger.error(f"⚠️ Failed to process leaf page {variant_item.item_id}: {leaf_err}")
                    variant_item.process_state = "ERROR"
                    final_items_to_commit.append(variant_item)

        # Commit Operations Block
        if not final_items_to_commit:
            logger.warning("⚠️ No finalized items generated for database ingestion phase.")
            return {"status": "NO_OP", "inserted_records": 0, "total_processed": len(all_collected_summaries)}

        inserted_counter = 0
        if not is_dry_run:
            try:
                logger.info(f"💾 Sending {len(final_items_to_commit)} items to database persistence layer...")
                inserted_counter = self.db_manager.commit_market_items(None, final_items_to_commit)
                logger.success(f"🎉 Successfully committed {inserted_counter} entries to records.")
            except Exception as db_err:
                logger.critical(f"🚨 Persistence Engine crash during transaction block: {db_err}")
                raise db_err
        else:
            logger.warning(f"🧪 [DRY RUN ACTIVE] Bypassed persisting {len(final_items_to_commit)} items to disk.")
            inserted_counter = len(final_items_to_commit)

        execution_duration = time.perf_counter() - start_time
        logger.info(f"⏱️ Historical harvest workflow complete in {execution_duration:.2f} seconds.")

        return {
            "status": "SUCCESS",
            "inserted_records": inserted_counter,
            "total_processed": len(all_collected_summaries)
        }
