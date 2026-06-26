# standalone_utils/utility/inspect_database.py
#
# Purpose: Initializes a local database connection to query total record counts 
# and stream a styled log output of the most recently fetched market items.

import sys
from pathlib import Path
from loguru import logger
from sqlalchemy import desc, func

# Find project root and inject it into sys.path to resolve src.* imports safely
def find_project_root(current_path: Path) -> Path:
    for parent in current_path.resolve().parents:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists() or (parent / "requirements.txt").exists():
            return parent
    return current_path.resolve().parent

ROOT_DIR = find_project_root(Path(__file__))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.database.db_manager import DatabaseManager
from src.database.models import MarketItemModel

def quick_look(limit=20):
    # Dynamically point to the bazaar.db file in your true project root folder
    db_path = ROOT_DIR / "bazaar.db"
    config = {"database": {"path": str(db_path)}}

    logger.info("Initializing Database Manager...")
    db = DatabaseManager(config)

    session = db.SessionLocal()
    logger.debug(f"Connected to database engine at: {db.engine.url}")

    try:
        # Check Snapshots
        total_items = session.query(func.count(MarketItemModel.item_id)).scalar()
        logger.info(f"Total snapshots recorded: {total_items}")

        # Print a quick sample of the newest data
        logger.info(f"Fetching last {limit} records added...")

        latest_records = (
            session.query(MarketItemModel)
            .order_by(desc(MarketItemModel.timestamp))
            .limit(limit)
            .all()
        )

        for item in latest_records:
            status = "SOLD" if item.is_sold else "ACTIVE"
            landed_price = item.price + item.shipping_cost

            # Extract processing state context defaults securely if none exist on row
            p_state = getattr(item, "process_state", "UNKNOWN").upper()

            # Using logger.success for parsed records containing process_state bounds
            logger.success(
                f"[{status}] [{p_state}] ID: {item.item_id} | "
                f"Model: {item.model_name} | Landed: ${landed_price:,.2f}"
            )

    except Exception as e:
        logger.exception(f"Failed to execute database lookup")

    finally:
        session.close()
        logger.debug("Database session closed successfully.")

if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    quick_look(lim)