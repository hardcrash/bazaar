# test/conftest.py

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
    Dynamically switches payloads depending on whether a telemetry/balance endpoint or
    an HTML search layout view is requested.
    """
    # Enforce safe dummy credentials for test runner initialization paths
    os.environ.setdefault("SCRAPERAPI_KEY", "mock_test_key_sandbox")

    with patch("requests.Session.send") as mock_send, \
         patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post:

        def smart_mock_routing(url, *args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            url_str = str(url).lower()

            # Route 1: Telemetry and Credit verification hooks
            if "account" in url_str or "quota" in url_str:
                response.text = "2500"
                response.json.return_value = {
                    "remaining_credits": 2500,
                    "requestLimit": 5000,
                    "requestCount": 2500,
                    "credit_limit": 5000,
                    "credit_used": 2500
                }
                response.headers = {
                    "X-Quota-Remaining": "2500",
                    "x-quota-remaining": "2500"
                }
            # Route 2: Default HTML Response Mock Engine
            else:
                response.text = (
                    "<html><body>"
                    "<div class='s-item'><div class='s-item__title'><span role='text'>Mocked Item Title</span></div>"
                    "<a class='s-item__link' href='https://www.ebay.com/itm/123456'>Link</a>"
                    "<span class='s-item__price'>$99.99</span></div>"
                    "<div class='listbox__option' data-sku-value-name='Mocked Test Variant'></div>"
                    "</body></html>"
                )
                response.headers = {}

            response.content = response.text.encode("utf-8")
            return response

        # Bind smart routing to standard hooks
        mock_get.side_effect = smart_mock_routing
        mock_send.side_effect = lambda req, *a, **kw: smart_mock_routing(req.url, *a, **kw)
        mock_post.side_effect = smart_mock_routing

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

@pytest.fixture
def mock_config():
    """
    Generates an isolated mock configuration model satisfying attribute requirements
    for both structural testing vectors across Client and Provider runtimes.
    """
    class DummyConfig:
        api_timeout_seconds = 5
        proxy_rotation = {
            "providers": {
                "scraperapi": {"api_key": "mock_sa_key", "endpoint_path": ""},
                "scrapeops": {"api_key": "mock_so_key", "endpoint_path": "v1"},
                "scraperbox": {"api_key": "mock_sb_key", "base_url": "https://scraperbox1.p.rapidapi.com"},
                "webscraping_ai": {"api_key": "mock_ai_key", "base_url": "https://api.webscraping.ai"}
            }
        }
    return DummyConfig()
