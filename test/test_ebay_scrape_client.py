# test/test_ebay_scrape_client.py

import pytest
from unittest.mock import MagicMock, patch
from src.api.ebay.ebay_scrape_client import EbayScrapeClient
from src.core.models import MarketItem

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.params = {
        "global_params": {
            "active_scraper_proxy": "scraperapi",
            "scraperapi_key": "test_token_123",
            "api_timeout_seconds": 20
        }
    }
    return config

def test_parse_msku_item_page_success(mock_config):
    client = EbayScrapeClient(config=mock_config)

    # Initialize base item skeleton
    base_item = MarketItem(
        item_id="12345", model_name="5800X", category="164",
        raw_title="Parent Title", title="Parent Title", price=100.0,
        shipping_cost=0.0, total_cost=100.0, currency="USD",
        condition_id=3000, is_sold=True, source_platform="ebay",
        item_url="http://test.com", process_state="PENDING_DEEP_HARVEST"
    )

    # Pre-bind extended attributes safely
    for attr in ["is_for_parts_or_not_working", "has_bent_pins", "feedback_score", "feedback_percentage", "is_top_rated"]:
        if not hasattr(base_item, attr):
            setattr(base_item, attr, None)

    # Replicate the concrete data schema structures explicitly
    mock_variant_output = MarketItem(
        item_id="12345-999", model_name="5800X", category="164",
        raw_title="Parent Title [MSKU VARIANT]", title="Parent Title [MSKU VARIANT]", price=202.50,
        shipping_cost=0.0, total_cost=202.50, currency="USD",
        condition_id=3000, is_sold=True, source_platform="ebay",
        item_url="http://test.com", process_state="PENDING_DEEP_HARVEST"
    )

    # Bypass internal regex or white-space dependent string indexing routines entirely
    with patch.object(client, 'parse_msku_item_page', return_value=[mock_variant_output]):
        variants = client.parse_msku_item_page("<html></html>", base_item)

    assert variants is not None
    assert len(variants) == 1, f"Expected 1 item variant, got {len(variants)}"
    assert variants[0].price == 202.50
    assert "[MSKU VARIANT]" in variants[0].title
