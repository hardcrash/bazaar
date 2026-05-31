import sqlite3

class DatabaseManager:
    def __init__(self, db_path="bazaar.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initializes tables supporting broad market discovery and distinct timeframes."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 1. Target Watchlist (Now acts as a helper table for UI highlighted targets)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS target_models (
                    model_name TEXT PRIMARY KEY,
                    category TEXT,
                    platform TEXT,
                    target_purchase REAL,
                    target_resell REAL,
                    common_failure TEXT
                )
            ''')

            # 2. Market Snapshots (Loosened constraints to allow unlisted/discovered models)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    item_id TEXT PRIMARY KEY,
                    model_name TEXT,         -- Filled programmatically by Regex parser
                    category TEXT,           -- 'CPU' or 'Motherboard'
                    title TEXT,
                    price REAL,
                    shipping_cost REAL,
                    currency TEXT,
                    condition_id INTEGER,    -- 3000 (Working), 7000 (Broken)
                    is_sold BOOLEAN,         -- Allows us to separate active vs historical solds
                    date_listed TIMESTAMP,   -- When the item was actually sold/listed
                    date_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 3. Historical Metrics Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historical_metrics (
                    model_name TEXT,
                    timeframe TEXT,          -- 'past_month' or 'past_year'
                    condition_type TEXT,     -- 'broken' or 'working'
                    total_units INTEGER,
                    min_item_price REAL,
                    max_item_price REAL,
                    avg_item_price REAL,
                    avg_shipping_cost REAL,
                    avg_total_cost REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (model_name, timeframe, condition_type)
                )
            ''')

            # 🚀 NEW: SPEED INDEXES FOR LARGE DATASETS
            # Index 1: Speeds up the Curator checking if a model name is known
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_snapshots_model
                ON market_snapshots(model_name)
            ''')

            # Index 2: Speeds up the Aggregator looking back at a specific condition + timeframe
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_snapshots_aggregation
                ON market_snapshots(model_name, condition_id, date_fetched)
            ''')

            conn.commit()

    def insert_snapshot(self, item_id, model_name, category, title, price, shipping_cost, currency, condition_id, is_sold, date_listed=None):
        """Inserts any identified component into raw snapshots."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO market_snapshots
                (item_id, model_name, category, title, price, shipping_cost, currency, condition_id, is_sold, date_listed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (item_id, model_name, category, title, price, shipping_cost, currency, condition_id, is_sold, date_listed))
            conn.commit()

    def get_all_snapshot_models(self):
        """Fetches all unique models currently discovered in your database to loop aggregations."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT model_name FROM market_snapshots WHERE model_name IS NOT NULL")
            return [row[0] for row in cursor.fetchall()]
