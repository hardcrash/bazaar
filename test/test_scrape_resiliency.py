# test/test_scrape_resiliency.py

import pytest
from unittest.mock import patch, MagicMock
from src.api.ebay.ebay_scrape_client import EbayScrapeClient

@patch('requests.get')
def test_scrape_handles_503_error(mock_get):
    """
    Verifies that a 503 error safely blacklists a provider, triggers
    the self-healing provider flush, and succeeds on the recovery loop.
    """
    # 1. Create a dummy config object with the new structured rotation layout
    mock_config = MagicMock()
    mock_config.api_timeout_seconds = 15
    mock_config.scraperapi_key = "test_key"

    # Emulate our updated YAML config dictionary structures
    mock_config.proxy_rotation = {
        "enabled": True,
        "providers": {
            "scraperapi": {"api_key": "test_key", "base_url": "http://api.scraperapi.com", "weight": 100}
        }
    }

    # FIX: Patch out 'refresh_account_balances' during instantiation
    # so it doesn't consume items from your global requests.get mock payload
    with patch.object(EbayScrapeClient, 'refresh_account_balances', return_value=None):
        client = EbayScrapeClient(config=mock_config)

    # 2. Setup mock responses specifically for the dispatch scraping loop
    # Attempt 1: Returns a 503 error -> triggers node blacklist
    # Attempt 2: After circuit-breaker reset ring, returns successful HTML response
    mock_get.side_effect = [
        MagicMock(status_code=503),
        MagicMock(status_code=200, text="<html>Success Target Source</html>")
    ]

    # 3. Trigger the deep harvest method
    response = client.fetch_raw_item_page("https://ebay.com/itm/123", max_retries=3)

    # 4. Validations
    assert response == "<html>Success Target Source</html>"
    assert mock_get.call_count == 2  # Strict 2 calls: 1 failure, 1 recovery success
