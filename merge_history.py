import sqlite3
from pathlib import Path

OLD_DATABASES = [
    "bazaar-old-1.db",
    "bazaar-old-2.db",
    "bazaar-old-3.db",
    "bazaar-old-4.db",
    "bazaar-old-5.db"
]
NEW_DATABASE = "bazaar.db"

# Pure SQL Schema based exactly on your high-grade v0.1.0 specifications
SCHEMA_ACTIVE_MARKETITEMS = """
CREATE TABLE IF NOT EXISTS active_marketitems (
    item_id VARCHAR PRIMARY KEY,
    model_name VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    source_platform VARCHAR NOT NULL,
    raw_title VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    price FLOAT NOT NULL,
    shipping_cost FLOAT,
    total_cost FLOAT NOT NULL,
    currency VARCHAR,
    condition_id INTEGER NOT NULL,
    is_sold BOOLEAN,
    is_for_parts_or_not_working BOOLEAN,
    has_bent_pins BOOLEAN,
    seller_username VARCHAR,
    feedback_score INTEGER,
    feedback_percentage FLOAT,
    is_top_rated BOOLEAN,
    epid VARCHAR,
    buying_options VARCHAR,
    quantity_sold INTEGER,
    bid_count INTEGER,
    item_start_date VARCHAR,
    item_end_date VARCHAR,
    date_listed DATETIME,
    date_fetched DATETIME DEFAULT CURRENT_TIMESTAMP,
    image_urls VARCHAR,
    item_url VARCHAR,
    process_state VARCHAR,
    data_grade VARCHAR NOT NULL DEFAULT 'BRONZE',
    is_parsed_by_agent BOOLEAN
);
"""

SCHEMA_HISTORICAL_METRICS = """
CREATE TABLE IF NOT EXISTS historical_metrics (
    model_name VARCHAR,
    timeframe VARCHAR,
    condition_type VARCHAR,
    total_units INTEGER,
    min_item_price FLOAT,
    max_item_price FLOAT,
    avg_item_price FLOAT,
    med_item_price FLOAT,
    avg_shipping_cost FLOAT,
    avg_total_cost FLOAT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model_name, timeframe, condition_type)
);
"""

def get_db_columns(cursor, table_name):
    try:
        cursor.execute(f"PRAGMA table_info({table_name});")
        return [row[1] for row in cursor.fetchall()]
    except Exception:
        return []

def migrate_data():
    print(f"🚀 Initializing Unified Standalone Historical Data Merge into {NEW_DATABASE}...")
    
    # Secure connection and force layout initialization instantly
    target_conn = sqlite3.connect(NEW_DATABASE)
    target_cursor = target_conn.cursor()
    target_cursor.execute(SCHEMA_ACTIVE_MARKETITEMS)
    target_cursor.execute(SCHEMA_HISTORICAL_METRICS)
    target_conn.commit()
    
    total_market_items = 0
    total_metrics = 0

    for db_name in OLD_DATABASES:
        db_path = Path(db_name)
        if not db_path.exists():
            print(f"⚠️  Skipping {db_name}: File not found in this directory.")
            continue
            
        print(f"📦 Processing data streaming from {db_name}...")
        source_conn = sqlite3.connect(db_path)
        source_cursor = source_conn.cursor()
        
        # 1. STREAM MARKET ITEMS
        source_cols = get_db_columns(source_cursor, "market_items")
        if source_cols:
            col_selectors = ", ".join(source_cols)
            source_cursor.execute(f"SELECT {col_selectors} FROM market_items;")
            rows = source_cursor.fetchall()
            
            for row in rows:
                item = dict(zip(source_cols, row))
                
                # Default fill missing schema variants (DB 1 & 3)
                if "data_grade" not in item:
                    item["data_grade"] = "BRONZE"
                
                columns = ", ".join(item.keys())
                placeholders = ", ".join(["?"] * len(item))
                
                # Safe upsert handling to seamlessly unify rows matching across identical primary keys
                query = f"INSERT OR IGNORE INTO active_marketitems ({columns}) VALUES ({placeholders});"
                target_cursor.execute(query, list(item.values()))
                total_market_items += 1

        # 2. STREAM HISTORICAL METRICS
        metric_cols = get_db_columns(source_cursor, "historical_metrics")
        if metric_cols:
            col_selectors = ", ".join(metric_cols)
            source_cursor.execute(f"SELECT {col_selectors} FROM historical_metrics;")
            rows = source_cursor.fetchall()
            
            for row in rows:
                metric = dict(zip(metric_cols, row))
                
                columns = ", ".join(metric.keys())
                placeholders = ", ".join(["?"] * len(metric))
                
                query = f"INSERT OR IGNORE INTO historical_metrics ({columns}) VALUES ({placeholders});"
                target_cursor.execute(query, list(metric.values()))
                total_metrics += 1
                
        source_conn.close()
        
    target_conn.commit()
    target_conn.close()
    print("\n✅ Merge Engine Processing Complete!")
    print(f"✨ Aggregated Rows: {total_market_items} Market Items | {total_metrics} Historical Metrics combined.")

if __name__ == "__main__":
    migrate_data()