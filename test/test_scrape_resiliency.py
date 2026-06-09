import pytest
from unittest.mock import patch, MagicMock
from src.api.ebay.ebay_scrape_client import EbayScrapeClient

@patch('requests.get')
def test_scrape_handles_503_error(mock_get):
    # 1. Create a dummy config object
    mock_config = MagicMock()
    mock_config.params = {"global_params": {"active_scraper_proxy": "scrapeops"}}

    # 2. Pass the mock_config to the client
    client = EbayScrapeClient(config=mock_config)

    # Setup mock to fail first, then succeed
    mock_get.side_effect = [
        MagicMock(status_code=503),
        MagicMock(status_code=200, text="<html>Success</html>")
    ]

    # Note: You'll need to call your method that actually uses requests.get
    # Assuming you call perform_request or similar (update to match your call signature)
    response = client.fetch_raw_item_page("https://ebay.com/itm/123")

    assert response == "<html>Success</html>"
    assert mock_get.call_count == 2
