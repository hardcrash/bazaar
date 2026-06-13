# src/analysis/aggregator.py

import logging
from statistics import mean, median, mode, StatisticsError
from datetime import datetime
from sqlalchemy.orm import Session
from src.database.models import MarketItemModel, HistoricalMetricModel

logger = logging.getLogger("BazaarPipeline")

class HistoricalAggregatorService:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def compute_market_metrics(self, model_name: str, timeframe_days: int = 30) -> dict:
        """Queries database items, segregates standard vs. defect items,
        and updates the summary metrics compilation matrix.
        """
        session: Session = self.db_manager.SessionLocal()
        try:
            # 1. Pull relevant items using indexed filter criteria
            query = session.query(MarketItemModel).filter(
                MarketItemModel.model_name == model_name,
                MarketItemModel.is_sold == True
            )

            all_items = query.all()
            if not all_items:
                logger.info(f"No metric calculations found for model query pool: {model_name}")
                return {}

            # 2. Segregate Defect and Risk-Adjusted Arrays
            standard_pool = []
            defect_pool = []

            for item in all_items:
                if item.is_for_parts_or_not_working or item.has_bent_pins or item.condition_id == 7000:
                    defect_pool.append(item)
                else:
                    standard_pool.append(item)

            # 3. Compute Aggregations for standard tier conditions
            metrics_payload = []
            for pool_type, current_pool in [("STANDARD", standard_pool), ("DEFECTIVE", defect_pool)]:
                if not current_pool:
                    continue

                total_costs = [item.total_cost for item in current_pool]
                prices = [item.price for item in current_pool]
                shippings = [item.shipping_cost for item in current_pool if item.shipping_cost is not None]

                # Compute Central Tendencies
                try:
                    calculated_mode = mode(prices)
                except StatisticsError:
                    calculated_mode = prices[0]  # Fallback if no clean frequency dominant value exists

                # 4. Unit Velocity Tracker: Calculate mean days on market (DoM)
                dom_deltas = []
                for item in current_pool:
                    if item.item_start_date and item.date_fetched:
                        # Fallback calculation matching database timestamp profiles
                        delta = (item.date_fetched - item.item_start_date).days
                        dom_deltas.append(max(0, delta))

                mean_dom = mean(dom_deltas) if dom_deltas else 0.0

                # Assemble database persistence metric target payload
                metric_entry = HistoricalMetricModel(
                    model_name=model_name,
                    timeframe=f"{timeframe_days}d",
                    condition_type=pool_type,
                    total_units=len(current_pool),
                    min_item_price=min(prices),
                    max_item_price=max(prices),
                    avg_item_price=mean(prices),
                    med_item_price=median(prices),
                    avg_shipping_cost=mean(shippings) if shippings else 0.0,
                    avg_total_cost=mean(total_costs),
                    # We can store the velocity tracking calculation on an extended metrics column if needed
                )

                session.merge(metric_entry)
                metrics_payload.append(metric_entry)

            session.commit()
            logger.info(f"📊 Processed statistics calculations for {model_name}: {len(metrics_payload)} groups saved.")
            return {"processed_groups": len(metrics_payload)}

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to generate historical aggregation profile maps: {e}")
            raise e
        finally:
            session.close()
