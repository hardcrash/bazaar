import sqlite3
import sys

def quick_look(limit=10):
    db_path = "bazaar.db"
    print(f"[🔍] Quick-checking latest snapshots in '{db_path}'...")

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check Snapshots
            cursor.execute("SELECT COUNT(*) FROM market_snapshots")
            print(f" Total snapshots recorded: {cursor.fetchone()[0]}")

            # Check Metrics
            cursor.execute("SELECT COUNT(*) FROM historical_metrics")
            print(f" Total aggregated metric windows: {cursor.fetchone()[0]}")

            # Print a quick sample of the newest sold data
            print(f"\n--- Last {limit} Records Added ---")
            cursor.execute("""
                SELECT item_id, model_name, price, shipping_cost, is_sold
                FROM market_snapshots
                ORDER BY date_fetched DESC
                LIMIT ?
            """, (limit,))

            for row in cursor.fetchall():
                status = "SOLD" if row['is_sold'] else "ACTIVE"
                print(f"[{status}] ID: {row['item_id']} | Model: {row['model_name']} | Landed: ${row['price'] + row['shipping_cost']:.2_f}")

    except Exception as e:
        print(f"[-] Failed to read database lookup: {e}")

if __name__ == "__main__":
    # Allows you to run `python check_db.py 20` to see more rows
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    quick_look(lim)
