# src/analysis/active_analysis_controller.py

import time
from loguru import logger
from typing import Dict, Any, Optional

from src.analysis.base_controller import BaseController
from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory

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

        all_collected_summaries = []

        for p_idx, target in enumerate(target_passes):
            logger.info(f"🔄 Active Sourcing Pass [{p_idx + 1}/{len(target_passes)}]: {target['name']}")
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
                all_collected_summaries.extend(pass_summaries)

        if not all_collected_summaries:
            logger.warning("⚠️ Active pipeline search pass produced 0 index results.")
            return {"status": "EMPTY", "inserted_records": 0, "total_processed": 0}

        unseen_items = self.filter_new_items(all_collected_summaries)

        if not unseen_items:
            logger.success("✨ Active items monitored match localized records perfectly.")
            return {"status": "SUCCESS", "inserted_records": 0, "total_processed": len(all_collected_summaries)}

        inserted_counter = 0
        if not is_dry_run:
            logger.info(f"💾 Persisting {len(unseen_items)} updated live state nodes into database layers...")
            inserted_counter = self.db_manager.commit_market_items(None, unseen_items)
        else:
            inserted_counter = len(unseen_items)

        execution_duration = time.perf_counter() - start_time
        logger.info(f"⏱️ Active monitoring loop complete in {execution_duration:.2f} seconds.")

        return {
            "status": "SUCCESS",
            "inserted_records": inserted_counter,
            "total_processed": len(all_collected_summaries)
        }
