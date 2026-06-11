import sys
from sqlalchemy import func, desc

# Import your database manager and models
from src.database.db_manager import DatabaseManager
from src.database.models import MarketItemModel, HistoricalMetricModel

def quick_look(limit=10):
    # Pass an empty dict config to default to the standard "bazaar.db"
    # Or pass your actual application configuration object here
    config = {"database": {"path": "bazaar.db"}}

    print(f"[🔍] Initializing Database Manager...")
    db = DatabaseManager(config)

    # Generate an isolated session using your manager's factory
    session = db.SessionLocal()
    print(f"[🔍] Quick-checking latest snapshots in '{db.engine.url}'...")

    try:
        # Check Snapshots
        total_items = session.query(func.count(MarketItemModel.item_id)).scalar()
        print(f" Total snapshots recorded: {total_items}")

        # Check Metrics
        total_metrics = session.query(func.count()).select_from(HistoricalMetricModel).scalar()
        print(f" Total aggregated metric windows: {total_metrics}")

        # Print a quick sample of the newest data
        print(f"\n--- Last {limit} Records Added ---")

        latest_records = (
            session.query(MarketItemModel)
            .order_by(desc(MarketItemModel.date_fetched))
            .limit(limit)
            .all()
        )

        for item in latest_records:
            status = "SOLD" if item.is_sold else "ACTIVE"

            # Using the schema columns directly
            landed_price = item.price + item.shipping_cost

            print(f"[{status}] ID: {item.item_id} | Model: {item.model_name} | Landed: ${landed_price:,.2f}")

    except Exception as e:
        print(f"[-] Failed to read database lookup: {e}")

    finally:
        # Always release the session back to the pool
        session.close()

if __name__ == "__main__":
    # Allows you to run `python check_db.py 20` to see more rows
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    quick_look(lim)
