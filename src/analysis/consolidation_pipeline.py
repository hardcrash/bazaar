# src/analysis/consolidation_pipeline.py
import json
import sqlite3
import logging
from pathlib import Path

from src.util.config_loader import load_yaml
from src.analysis.curator import MarketCurator
from src.analysis.parser import ComponentParserRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BazaarPipeline")

def run_consolidation_pipeline(categories: list = ["Motherboard", "CPU"]):
    """
    Executes an optimized multi-pass data consolidation loop over polymorphic parsing strategies.
    """
    logger.info("⚙️ Loading global settings from config.yaml...")
    try:
        cfg = load_yaml("config.yaml")
        cache_file = cfg.get("agent", {}).get("cache_output_file", "consolidated_bazaar_metrics.json")
        db_path = cfg.get("database_name", "bazaar.db")
    except Exception as e:
        logger.error(f"❌ Failed to resolve config.yaml: {e}")
        return False

    # Initialize dynamic strategy parser registry
    parser_registry = ComponentParserRegistry("config_parser.json")

    # Load all strategies up front
    strategies = {}
    for cat in categories:
        strat = parser_registry.get_strategy_for_category(cat)
        if strat:
            strategies[cat] = strat

    curator = MarketCurator(db_path=db_path)
    logger.info("🔧 Pulling unparsed raw records from Gatekeeper Curator...")
    raw_listings = curator.read_unconsolidated_listings()

    if not raw_listings:
        logger.info("✅ No 'UNKNOWN' snapshots found awaiting processing. Pipeline idling.")
        return True

    logger.info(f"📋 Retrieved {len(raw_listings)} listings requiring classification maps.")

    # Always start fresh with review queues to prevent ghost data
    consolidated_map = {"consolidated": {}, "manual_review_required": []}
    items_updated = 0

    try:
        with sqlite3.connect(curator.db_path) as conn:
            cursor = conn.cursor()

            for index, item in enumerate(raw_listings, 1):
                item_id = item['item_id']
                title = item['title']
                item_price = item['item_price']
                shipping_cost = item['shipping_cost']

                matched_category = None
                detected_brand = "UNKNOWN"
                detected_model = None

                # Multi-strategy match check
                for cat_name, strategy in strategies.items():
                    brand, model = strategy.parse_title(title.upper())
                    if model:
                        matched_category = cat_name
                        detected_model = model.upper()
                        detected_brand = brand.upper() if brand else "UNKNOWN"
                        break  # Found a match! Stop evaluating categories for this row.

                if matched_category:
                    # Update database snapshot target record
                    cursor.execute("""
                        UPDATE market_snapshots
                        SET model_name = ?
                        WHERE item_id = ?
                    """, (detected_model, item_id))

                    items_updated += 1

                    # Fold into cache tracking keys
                    key = f"{detected_brand.lower()}_{detected_model.lower().replace(' ', '_')}"
                    if key not in consolidated_map["consolidated"]:
                        consolidated_map["consolidated"][key] = {
                            "brand": detected_brand,
                            "model": detected_model,
                            "category": matched_category,
                            "listings_count": 0,
                            "raw_prices": [],
                            "shipping_costs": []
                        }

                    consolidated_map["consolidated"][key]["listings_count"] += 1
                    consolidated_map["consolidated"][key]["raw_prices"].append(item_price)
                    consolidated_map["consolidated"][key]["shipping_costs"].append(shipping_cost)
                else:
                    # True anomaly item fell completely out of all structural filters
                    consolidated_map["manual_review_required"].append({
                        "item_id": item_id,
                        "original_title": title,
                        "item_price": item_price,
                        "shipping_cost": shipping_cost,
                        "reason": f"Title structure bypassed configuration rules for: {categories}"
                    })

            conn.commit()

        logger.info(f"💾 Changes successfully written to disk. {items_updated} items normalized.")

        with open(output_file, "w") as f:
            json.dump(consolidated_data, f, indent=4)
        print(f"  ✅ Category metrics cleanly written to {output_file}")
        return True

    except Exception as e:
        logger.error(f"❌ Critical pipeline exception occurred: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    # Force the engine to loop through both hardware matrix profiles in a single pass
    run_consolidation_pipeline(["Motherboard", "CPU"])
