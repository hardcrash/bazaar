# test/run_pipeline.py

import logging
import sys
from src.database.db_manager import DatabaseManager
from src.analysis.transformer import MarketItemTransformer
from src.analysis.aggregator import HistoricalAggregatorService

# Configure clean console logging visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("BazaarPipeline")

def main():
    logger.info("🚀 Initializing Production Persistence Layer...")

    # Define a physical path layout configuration for your local tracking stack
    config = {
        "database": {
            "path": "data/bazaar_production.db"
        }
    }

    # Initialize the database file and dynamically create tables
    db_manager = DatabaseManager(config=config)

    # 🌟 Simulating a real raw network payload incoming from an active API harvest run
    raw_api_payload = {
        "itemId": "v1-998877665544-0",
        "title": "   *** SALE *** AMD Ryzen 7 7800X3D Gaming Processor  ",
        "price": {"value": "349.00", "currency": "USD"},
        "shippingOptions": [{"shippingCost": {"value": "Free"}}],
        "conditionId": "1000", # New
        "seller": {
            "username": "apex_silicon_distribution",
            "feedbackScore": "15420",
            "positiveFeedbackPercent": "99.4"
        }
    }

    logger.info(f"📥 Processing live payload for Item ID: {raw_api_payload['itemId']}")

    # Run through translation and validation matrix layers
    market_dataclass = MarketItemTransformer.raw_ebay_json_to_market_item(
        item_json=raw_api_payload,
        category="processors",
        condition_id=1000,
        is_sold=True
    )

    # Overwrite the default tracking tag to match our database aggregation targets
    market_dataclass.model_name = "7800X3D"

    # Commit the clean record permanently to physical storage disk
    logger.info("💾 Merging record down to production SQLite database storage...")
    db_manager.insert_harvested_item(market_dataclass)

    # Trigger active analytical aggregation pass
    logger.info("📊 Re-calculating statistical rolling profiles for 7800X3D segment...")
    aggregator = HistoricalAggregatorService(db_manager=db_manager)
    results = aggregator.compute_market_metrics(model_name="7800X3D", timeframe_days=30)

    logger.info(f"✨ Run completed flawlessly! Metric Groups Built: {results.get('processed_groups', 0)}")

if __name__ == "__main__":
    main()
