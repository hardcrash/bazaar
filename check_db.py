import sys
from loguru import logger
from sqlalchemy import func, desc

from src.database.db_manager import DatabaseManager
from src.database.models import MarketItemModel, HistoricalMetricModel

def quick_look(limit=10):
    config = {"database": {"path": "bazaar.db"}}

    logger.info("Initializing Database Manager...")
    db = DatabaseManager(config)

    session = db.SessionLocal()
    logger.debug(f"Connected to database engine at: {db.engine.url}")

    try:
        # Check Snapshots
        total_items = session.query(func.count(MarketItemModel.item_id)).scalar()
        logger.info(f"Total snapshots recorded: {total_items}")

        # Check Metrics
        total_metrics = session.query(func.count()).select_from(HistoricalMetricModel).scalar()
        logger.info(f"Total aggregated metric windows: {total_metrics}")

        # Print a quick sample of the newest data
        logger.info(f"Fetching last {limit} records added...")

        latest_records = (
            session.query(MarketItemModel)
            .order_by(desc(MarketItemModel.date_fetched))
            .limit(limit)
            .all()
        )

        for item in latest_records:
            status = "SOLD" if item.is_sold else "ACTIVE"
            landed_price = item.price + item.shipping_cost

            # Using logger.success for parsed records
            logger.success(f"[{status}] ID: {item.item_id} | Model: {item.model_name} | Landed: ${landed_price:,.2f}")

    except Exception as e:
        # Loguru handles the exception tracking beautifully
        logger.exception(f"Failed to execute database lookup lookup")

    finally:
        session.close()
        logger.debug("Database session closed successfully.")

if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    quick_look(lim)
