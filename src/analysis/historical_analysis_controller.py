# src/analysis/historical_analysis_controller.py

import time
from loguru import logger
from typing import Dict, Any, Optional, List

from src.analysis.base_controller import BaseController
from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory

class HistoricalAnalysisController(BaseController):
    def run_harvest(self,
                    query: Optional[str] = None,
                    category_id: Optional[Any] = None,
                    model_name: Optional[str] = None,
                    strategy: Optional[Any] = None,
                    **kwargs) -> Dict[str, Any]:

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
        
        # 1. Resolve and normalize Category IDs (Support strings, integers, lists, or empty arrays)
        if not category_id:
            harvest_cfg = strategy.config.get("historical_harvest", {})
            raw_cat = harvest_cfg.get("ebay_category_id", [164])
            if isinstance(raw_cat, list):
                category_ids = [str(c) for c in raw_cat]
            elif raw_cat:
                category_ids = [str(raw_cat)]
            else:
                category_ids = [""]
        else:
            category_ids = [str(category_id)] if not isinstance(category_id, list) else [str(c) for c in category_id]

        # 2. Dynamically build target queries (Using ONLY upstream blacklist words)
        if not query:
            fmt = strategy.config.get("search_format", "Ryzen {model}")
            base_query = fmt.format(model=model_name)
            
            # Strict isolation: Only pull words meant for upstream API exclusion
            upstream_blacklist = strategy.config.get("blacklist_words", [])
            exclusions = " ".join([f"-{word}" for word in upstream_blacklist if word])
            query = f"{base_query} {exclusions}".strip()

        # 3. Build Historical Ranges Matrix
        target_passes = []
        harvest_cfg = strategy.config.get("historical_harvest", {})
        conditions_configured = harvest_cfg.get("ebay_condition", [])

        # --- Strategy A: No Condition Restriction Configured ---
        if not conditions_configured:
            min_p = harvest_cfg.get("min_price_used", strategy.config.get("active_harvest", {}).get("min_price", 50))
            max_p = harvest_cfg.get("max_price_used", strategy.config.get("active_harvest", {}).get("max_price", 650))
            
            brackets = (strategy.get_price_brackets(pass_type="used") 
                        if hasattr(strategy, "get_price_brackets") 
                        else [(min_p, max_p)])
            
            for min_p, max_p in brackets:
                target_passes.append({
                    "name": "UNFILTERED_CONDITION_MATRIX",
                    "conditions": [], 
                    "min_p": min_p,
                    "max_p": max_p
                })
        else:
            # --- Strategy B: Explicit Condition Filtering ---
            if 7000 in conditions_configured:
                for min_p, max_p in strategy.get_price_brackets(pass_type="broken"):
                    target_passes.append({
                        "name": "BROKEN/PARTS_ONLY",
                        "conditions": [7000],
                        "min_p": min_p,
                        "max_p": max_p
                    })

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

        # 4. Execute Multi-Category / Multi-Pass Sweep Loop Matrix
        total_runs = len(category_ids) * len(target_passes)
        run_counter = 1

        for cat_id in category_ids:
            for target in target_passes:
                logger.info(f"🔄 Sourcing Pass [{run_counter}/{total_runs}]: {target['name']} | Category: {cat_id or 'GLOBAL'}")
                
                pass_summaries = self.scrape_client.search_historical_sales(
                    query=query,
                    min_price=target['min_p'],
                    max_price=target['max_p'],
                    category_id=cat_id if cat_id else None,
                    model_name=model_name,
                    strategy=strategy,
                    conditions=target['conditions'] if target['conditions'] else None
                )

                if pass_summaries:
                    logger.success(f"📈 Pass '{target['name']}' successfully captured {len(pass_summaries)} matches.")
                    all_collected_summaries.extend(pass_summaries)
                else:
                    logger.warning(f"⚠️ Pass '{target['name']}' returned 0 items inside bracket boundary.")
                
                run_counter += 1

        # Handle empty harvest groups gracefully
        if not all_collected_summaries:
            logger.warning("🏁 All execution loops returned empty result sets (Market slice contains no entries).")
            return {
                "status": "SUCCESS",
                "inserted_records": 0,
                "total_processed": 0
            }

        # Deduplicate using base optimization checker layer
        unseen_items = self.filter_new_items(all_collected_summaries)
        skipped_count = len(all_collected_summaries) - len(unseen_items)
        if skipped_count > 0:
            logger.info(f"🔒 API Call Protection Guard: Skipped deep checking for {skipped_count} items already present in DB.")

        if not unseen_items:
            logger.success("✨ All captured sweep items match historical records. No credit expenditures needed!")
            return {"status": "SUCCESS", "inserted_records": 0, "total_processed": len(all_collected_summaries)}

        # OPTIMIZATION GRID: Separate items based on deep harvest necessity
        deep_harvest_items = [item for item in unseen_items if item.process_state == "PENDING_DEEP_HARVEST"]
        direct_route_items = [item for item in unseen_items if item.process_state != "PENDING_DEEP_HARVEST"]

        final_items_to_commit = []

        # Tier 1: Direct Route Standard Items
        if direct_route_items:
            logger.info(f"🏎️ Short-circuiting {len(direct_route_items)} standard items directly to queue.")
            for base_item in direct_route_items:
                if hasattr(strategy, 'is_valid_standalone') and not strategy.is_valid_standalone(base_item):
                    logger.warning(f"⏩ Strategy Filter: Dropping item {base_item.item_id} based on validation rules.")
                    continue
                base_item.process_state = "PENDING"
                final_items_to_commit.append(base_item)

        # Tier 2: Premium Deep Leaf Ingestion
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