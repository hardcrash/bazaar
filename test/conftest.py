import pytest
import sqlite3

TEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    item_id TEXT PRIMARY KEY,
    model_name TEXT,
    category TEXT,
    raw_title TEXT,
    title TEXT,
    price REAL,
    shipping_cost REAL,
    currency TEXT,
    condition_id INTEGER,
    is_sold BOOLEAN,
    date_listed TIMESTAMP,
    source_platform TEXT DEFAULT 'ebay',
    date_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
@pytest.fixture
def mock_db():
    conn = sqlite3.connect(":memory:") # Use an in-memory DB for tests
    cursor = conn.cursor()
    cursor.execute(TEST_SCHEMA)
    yield conn
    conn.close()
