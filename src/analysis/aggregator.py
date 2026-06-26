# src/analysis/aggregator.py

"""
Bazaar Historical Data Aggregator Service

This module calculates moving statistical metrics (central tendencies, pricing boundaries, 
and shipping averages) from historical transactional data stores and updates the analytical 
aggregation matrix table.
"""

import logging
from statistics import mean, median, mode, StatisticsError
from sqlalchemy.orm import Session
from sqlalchemy import text 
from src.database.models import HistoricalMarketItemModel

logger = logging.getLogger("BazaarPipeline")

class HistoricalAggregatorService:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def compute_market_metrics(self, model_name: str, timeframe_days: int = 30) -> dict:
        """Queries historical database items, segregates standard vs. defect items,
        and updates the summary metrics compilation matrix.
        """
        session: Session = self.db_manager.SessionLocal()
        try:
            # 1. Pull relevant items using indexed filter criteria on the historical model
            query = session.query(HistoricalMarketItemModel).filter(
                HistoricalMarketItemModel.model_name == model_name,
                HistoricalMarketItemModel.is_sold == True
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
            processed_groups_count = 0
            for pool_type, current_pool in [("STANDARD", standard_pool), ("DEFECTIVE", defect_pool)]:
                if not current_pool:
                    continue

                total_costs = [item.total_cost for item in current_pool]
                prices = [item.price for item in current_pool]
                shippings = [item.shipping_cost for item in current_pool if item.shipping_cost is not None]

                # 4. Core SQL Execution targeting historical indices
                upsert_query = text("""
                    INSERT INTO historical_metrics (
                        model_name, timeframe, condition_type, total_units,
                        min_item_price, max_item_price, avg_item_price, med_item_price,
                        avg_shipping_cost, avg_total_cost, last_updated
                    ) VALUES (
                        :model_name, :timeframe, :condition_type, :total_units,
                        :min_item_price, :max_item_price, :avg_item_price, :med_item_price,
                        :avg_shipping_cost, :avg_total_cost, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT(model_name, timeframe, condition_type) DO UPDATE SET
                        total_units=excluded.total_units,
                        min_item_price=excluded.min_item_price,
                        max_item_price=excluded.max_item_price,
                        avg_item_price=excluded.avg_item_price,
                        med_item_price=excluded.med_item_price,
                        avg_shipping_cost=excluded.avg_shipping_cost,
                        avg_total_cost=excluded.avg_total_cost,
                        last_updated=CURRENT_TIMESTAMP;
                """)

                session.execute(upsert_query, {
                    "model_name": model_name,
                    "timeframe": f"{timeframe_days}d",
                    "condition_type": pool_type,
                    "total_units": len(current_pool),
                    "min_item_price": float(min(prices)),
                    "max_item_price": float(max(prices)),
                    "avg_item_price": float(mean(prices)),
                    "med_item_price": float(median(prices)),
                    "avg_shipping_cost": float(mean(shippings)) if shippings else 0.0,
                    "avg_total_cost": float(mean(total_costs))
                })
                processed_groups_count += 1

            session.commit()
            logger.info(f"📊 Processed statistics calculations for {model_name}: {processed_groups_count} groups saved.")
            return {"processed_groups": processed_groups_count}

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to generate historical aggregation profile maps: {e}")
            raise e
        finally:
            session.close()