"""
Bazaar Integration Pipeline Unit Tests

This module validates that raw HTML structures process cleanly through the active 
EbayScrapeClient and successfully serialize into isolated runtime test databases.
"""

import pytest
from src.database.db_manager import DatabaseManager
from src.api.ebay.ebay_scrape_client import EbayScrapeClient

@pytest.fixture
def isolated_db_manager(tmp_path):
    """
    Creates an isolated, sandboxed database instance for testing.
    """
    test_db_file = tmp_path / "bazaar_test.db"
    config = {
        "database": {
            "path": test_db_file
        }
    }
    return DatabaseManager(config=config)

def test_raw_payload_transformation_to_database_insertion(isolated_db_manager):
    """
    Validates end-to-end processing using the active production HTML parsing path.
    """
    # 1. Pull the actual sandboxed database path directly out of the SQLAlchemy engine
    test_db_path = isolated_db_manager.engine.url.database

    mock_unified_config = {
        "app_env": "testing",
        "api_key": "fake_key",
        "database": {
            "path": test_db_path
        }
    }
    
    client = EbayScrapeClient(config=mock_unified_config)

    # 2. Build a raw HTML string snippet simulating a simplified eBay listing structure
    # (Using generic standard list-item structures to hit your selectors)
    mock_html = """
    <html>
        <body>
            <ul class="srp-results srp-list clearfix">
                <li class="s-item s-item__pl-on-bottom">
                    <div class="s-item__info clearfix">
                        <a href="https://www.ebay.com/itm/12345" class="s-item__link">
                            <span role="heading" aria-level="3" class="s-item__title">AMD Ryzen 7 7800X3D Gaming Processor</span>
                        </a>
                        <span class="s-item__price">$349.00</span>
                        <span class="s-item__shipping s-item__logisticsCost">Free shipping</span>
                        <span class="s-item__seller-info">
                            <span class="s-item__seller-name">apex_silicon_distribution</span>
                        </span>
                    </div>
                </li>
            </ul>
        </body>
    </html>
    """

    # 3. Process the HTML via the production engine path
    market_items = client._parse_ebay_html(
        html_content=mock_html,
        model_name="7800X3D",
        category_id="processors",
        is_sold=True
    )

    # Verify a listing was found and successfully hydrated into a MarketItem object
    assert len(market_items) > 0, "❌ DOM Ingestion failed to parse any items out of mock HTML."
    market_item = market_items[0]

    assert "7800X3D" in market_item.model_name
    
    # 4. Verify permanent database write serialization
    insertion_success = False
    try:
        isolated_db_manager.insert_harvested_item(market_item)
        insertion_success = True
    except Exception as exc:
        pytest.fail(f"❌ Database engine raised unexpected exception on insert: {exc}")

    assert insertion_success is True

def test_parse_ebay_html_empty_dom(isolated_db_manager):
    """Ensures an empty or unmatchable DOM returns an empty list gracefully."""
    mock_config = {"app_env": "testing", "api_key": "fake", "database": {"path": isolated_db_manager.engine.url.database}}
    client = EbayScrapeClient(config=mock_config)
    
    # Missing completely or empty body text
    results = client._parse_ebay_html("<html><body></body></html>", "7800X3D", "processors")
    assert results == []

def test_parse_ebay_html_skips_invalid_items(isolated_db_manager):
    """Ensures items missing crucial fields (price, identifiers) are skipped safely."""
    mock_config = {"app_env": "testing", "api_key": "fake", "database": {"path": isolated_db_manager.engine.url.database}}
    client = EbayScrapeClient(config=mock_config)

    # HTML containing one listing missing a price, and one listing missing an item link/ID
    malformed_html = """
    <html>
        <body>
            <ul class="srp-results">
                <!-- Item 1: Missing Price -->
                <li class="s-item">
                    <a href="https://www.ebay.com/itm/111" class="s-item__link">
                        <span class="s-item__title">AMD Ryzen 7 7800X3D</span>
                    </a>
                    <!-- Price class missing entirely -->
                </li>
                <!-- Item 2: Missing Identifiers -->
                <li class="s-item">
                    <!-- Link missing entirely -->
                    <span class="s-item__title">AMD Ryzen 9 7900X</span>
                    <span class="s-item__price">$400.00</span>
                </li>
            </ul>
        </body>
    </html>
    """

    results = client._parse_ebay_html(malformed_html, "7800X3D", "processors")
    
    # Both items should fail validation checks and be excluded from final results
    assert len(results) == 0