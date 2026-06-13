import os
import pytest
import sqlite3
from unittest.mock import patch, MagicMock

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

@pytest.fixture(autouse=True, scope="session")
def secure_test_sandbox():
    """
    Globally intercepts all outbound requests at the networking layer during testing.
    Prevents live proxy budget consumption and eliminates console stdout log pollution.
    """
    # Enforce safe dummy credentials for test runner initialization paths
    os.environ.setdefault("SCRAPERAPI_KEY", "mock_test_key_sandbox")

    with patch("requests.Session.send") as mock_send, \
         patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post:

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><div class='listbox__option' data-sku-value-name='Mocked Test Variant'></div></body></html>"
        mock_response.content = mock_response.text.encode("utf-8")

        mock_send.return_value = mock_response
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response

        yield

@pytest.fixture
def mock_db():
    """
    Provides an isolated, in-memory SQLite database pre-populated with the tracking schema.
    Automatically handles transaction tear-downs per test execution block.
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(TEST_SCHEMA)
    conn.commit()
    yield conn
    conn.close()
