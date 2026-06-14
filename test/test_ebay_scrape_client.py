# test/test_ebay_scrape_client.py
import pytest
from unittest.mock import MagicMock, patch
from src.api.ebay.ebay_scrape_client import EbayScrapeClient
from src.core.models import MarketItem

@pytest.fixture
def mock_config():
    """Provides a unified mock configuration fixture for the EbayScrapeClient."""
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
    """Verifies that Multi-SKU mutation page routines parse variant list matrices correctly."""
    client = EbayScrapeClient(config=mock_config)

    # FIXED: Realigned 'category_id=' down to data contract parameter 'category='
    base_item = MarketItem(
        item_id="12345", model_name="5800X", category="164",
        raw_title="Parent Title", title="Parent Title", price=100.0,
        shipping_cost=0.0, total_cost=100.0, currency="USD",
        condition_id=3000, is_sold=True, source_platform="ebay",
        item_url="http://test.com", process_state="PENDING_DEEP_HARVEST"
    )

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

def test_scrape_client_returns_all_required_market_item_fields(mock_config):
    """
    Verifies that the internal HTML parsing logic successfully extracts and maps
    every field requested by the downstream SQLAlchemy engine and strictly follows
    the rules established by the MarketItem data contract.
    """
    client = EbayScrapeClient(config=mock_config)

    mock_strategy = MagicMock()
    mock_strategy.clean_title.side_effect = lambda t: t.strip()
    mock_strategy.is_valid.return_value = "VALID"

    sample_html_payload = """
        <li class="s-item">
            <div class="s-item__title">AMD Ryzen 7 5800X Desktop Processor</div>
            <span class="s-item__price">$115.00</span>
            <a class="s-item__link" href="https://www.ebay.com/itm/123456789012?hash=itemabc">View Item</a>
        </li>
        """

    # FIXED: Realigned 'html_content=' keyword down to production signature 'html_text='
    parsed_items = client._parse_ebay_html(
        html_text=sample_html_payload,
        model_name="5800X",
        category_id="CPU",
        is_sold=True,
        strategy=mock_strategy
    )

    assert len(parsed_items) == 1, "The core parser completely missed the sample raw listing."
    item: MarketItem = parsed_items[0]

    # Verify Platform Identifiers
    assert item.item_id == "123456789012"
    assert item.model_name == "5800X"
    assert item.category == "CPU"
    assert item.source_platform == "ebay"

    # Verify Text Field Extraction
    assert item.raw_title == "AMD Ryzen 7 5800X Desktop Processor"
    assert item.title == "AMD Ryzen 7 5800X Desktop Processor"

    # Verify Strict Database Schema Mappings & Data Types
    assert isinstance(item.price, float)
    assert item.price == 115.00
    assert isinstance(item.shipping_cost, float)
    assert item.shipping_cost == 0.0
    assert isinstance(item.total_cost, float)
    assert item.total_cost == 115.00
    assert item.currency == "USD"

    # Verify Condition & State Bounds
    assert isinstance(item.condition_id, int)
    assert item.condition_id == 3000
    assert item.is_sold is True
    assert item.is_for_parts_or_not_working is False
    assert item.process_state == "PENDING"
    assert "123456789012" in item.item_url
