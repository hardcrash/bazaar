# src/analysis/curator.py
import sqlite3
import logging
from src.util.config_loader import load_yaml  # Leverage your utility loader

logger = logging.getLogger("BazaarPipeline")

class MarketCurator:
    def __init__(self, db_path=None):
        """
        Initializes the Gatekeeper Curator.
        If no explicit db_path is provided, it dynamically resolves it via config.yaml.
        """
        if db_path is None:
            try:
                cfg = load_yaml("config.yaml")
                self.db_path = cfg.get("database_name", "bazaar.db")
            except Exception as e:
                logger.error(f"❌ MarketCurator failed to auto-load config.yaml: {e}")
                self.db_path = "bazaar.db"  # Hard fallback
        else:
            self.db_path = db_path

    def read_unconsolidated_listings(self):
        """
        Extracts all raw snapshot records where the model_name is flagged
        as 'UNKNOWN', ready for Hermes Agent refinement.
        """
        raw_listings = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Enables column name dictionary mapping
                cursor = conn.cursor()

                # Fetch all data targets awaiting AI sorting
                cursor.execute("""
                    SELECT item_id, title, price, shipping_cost, condition_id
                    FROM market_snapshots
                    WHERE model_name = 'UNKNOWN'
                """)

                rows = cursor.fetchall()

                for row in rows:
                    title = row["title"]
                    price = row["price"] or 0.0
                    shipping = row["shipping_cost"] or 0.0
                    total_cost = price + shipping
                    cond_id = row["condition_id"] or 3000

                    # Validate using your filtering gates (blacklist checks, outliers, etc.)
                    if self.is_valid_discovery("UNKNOWN", title, total_cost, cond_id):
                        raw_listings.append({
                            "item_id": row["item_id"],
                            "title": title,
                            "item_price": price,         # Preserved raw seller amount
                            "shipping_cost": shipping,   # Preserved raw carrier amount
                            "total_cost": total_cost,     # Explicit math summary for Hermes
                            "condition_id": cond_id
                        })

            return raw_listings

        except Exception as e:
            logger.error(f"❌ Error extracting unconsolidated listings from database: {e}")
            return []

    def is_valid_discovery(self, model_name, title, total_cost, condition_id):
        """
        Your gatekeeper validation logic.
        Filters out retail trash, empty component boxes, or extreme pricing anomalies.
        """
        title_lower = title.lower()

        # Immediate extraction filters (Add or adjust these as needed)
        blacklist = ["box only", "empty box", "wrapper", "case only", "damaged box"]
        if any(term in title_lower for term in blacklist):
            return False

        # Prevent zero-value or wild outlier errors
        if total_cost <= 0.0 or total_cost > 5000.0:
            return False

        return True
