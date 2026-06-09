import sqlite3
import os
import json

class DatabaseManager:
    def __init__(self, config):
        self.db_path = config.params.get("database", {}).get("path", "bazaar.db")
        self.settings_dir = config.settings_dir
        self.queries = config.queries
        self.init_db()

    def init_db(self):
        schema_path = os.path.join(self.settings_dir, "schema.sql")
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(schema_sql)

    def insert_harvested_item(self, market_item_obj):
        """Accepts a MarketItem object, flattens non-primitive types, and saves to DB."""
        query = self.queries.get("insert_harvested_item")

        # Turn the dataclass or object properties into a flat dictionary
        data = market_item_obj.__dict__.copy()

        # 🌟 CRITICAL: Safely convert list to a comma-separated string for SQLite TEXT column
        if isinstance(data.get("buying_options"), list):
            data["buying_options"] = ", ".join(data["buying_options"])

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(query, data)
            conn.commit()
