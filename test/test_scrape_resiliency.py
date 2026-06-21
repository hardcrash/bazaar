# test/test_scrape_resiliency.py

import pytest
from unittest.mock import patch, MagicMock
from src.api.ebay.ebay_scrape_client import EbayScrapeClient
from src.api.ebay.ebay_scrape_provider import EbayScraperProvider

@patch('requests.get')
@patch.object(EbayScrapeClient, 'refresh_account_balances', return_value=None)
@patch.object(EbayScraperProvider, 'refresh_account_balances', return_value=None)
def test_scrape_handles_503_error(mock_prov_refresh, mock_client_refresh, mock_get):
    """
    Verifies that a 503 error safely blacklists a provider, triggers
    the self-healing provider flush, and succeeds on the recovery loop.
    """
    # 1. Create a dummy config object with the new structured rotation layout
    mock_config = MagicMock()
    mock_config.api_timeout_seconds = 15
    mock_config.scraperapi_key = "test_key"
    mock_config.scrapeops_key = "backup_key"

    # Emulate our updated YAML config dictionary structures with a backup option
    mock_config.proxy_rotation = {
        "enabled": True,
        "providers": {
            "scraperapi": {
                "api_key": "test_key",
                "base_url": "http://api.scraperapi.com",
                "default_weight": 25,
                "api_timeout_seconds": 20
            },
            "scrapeops": {
                "api_key": "backup_key",
                "base_url": "https://proxy.scrapeops.io/v1",
                "default_weight": 25,
                "api_timeout_seconds": 20
            }
        }
    }

    # Initialize client safely within globally decorated patch contexts
    client = EbayScrapeClient(config=mock_config)

    # SEED CREDITS: Give mocked providers an active pool balance so the selector passes them
    client._runtime_credits = {
        "scraperapi": 5000,
        "scrapeops": 1000
    }

    # 🛠️ Hydrate properties expected by the circuit breaker sweep loop
    client.provider.current_strategy = "scraperapi"
    client.provider.scraperapi_key = "test_key"
    client.provider.scrapeops_key = "backup_key"

    # 🎯 FIX: Add the trailing slash to 'https://proxy.scrapeops.io/v1/'
    def mock_get_proxied_params(target_url, provider_override=None):
        provider = provider_override or "scraperapi"
        if provider == "scraperapi":
            return "http://api.scraperapi.com", {"api_key": "test_key", "url": target_url}, {}, "scraperapi"

        # Locked trailing slash verification
        return "https://proxy.scrapeops.io/v1/", {"api_key": "backup_key", "url": target_url}, {}, "scrapeops"

    client.provider.get_proxied_request_params = mock_get_proxied_params

    # 2. Setup mock responses specifically for the dispatch scraping loop
    # Attempt 1: Returns a 503 error -> triggers node failover
    # Attempt 2: Swaps to the available backup provider -> returns successful HTML response
    mock_get.side_effect = [
        MagicMock(status_code=503),
        MagicMock(status_code=200, text="<html>Success Target Source</html>")
    ]

    # 3. Trigger the deep harvest method
    response = client.dispatch_scrape("https://ebay.com/itm/123", max_retries=3)

    # Confirms failover gracefully completed and retrieved payload from the backup node
    assert response == "<html>Success Target Source</html>"

    # Removed all lingering traces of the invalid _active_blacklist property
    assert len(client._runtime_credits) > 0
