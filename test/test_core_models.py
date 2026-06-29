# test/test_core_models.py
"""
Bazaar Domain Model Structural Tests

Validates Pydantic enforcement, field type coercions, default values, 
and inheritance integrity across Active and Historical domain models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from src.core.models import ActiveMarketItem, HistoricalMarketItem


@pytest.fixture
def base_valid_payload():
    """A minimal dictionary providing all required fields for BaseMarketItem."""
    return {
        "item_id": "ebay_123456789",
        "model_name": "Ryzen 5800X",
        "category": "CPU",
        "raw_title": "  AMD Ryzen 7 5800X CPU !!  ",
        "title": "AMD Ryzen 7 5800X",
        "price": 115.00,
        "shipping_cost": 5.50,
        "total_cost": 120.50,
    }


def test_active_market_item_initialization(base_valid_payload):
    """Verifies that ActiveMarketItem hydrates perfectly with valid data and handles defaults."""
    # Inject active-specific metrics if desired, or let defaults drop in
    item = ActiveMarketItem(**base_valid_payload)
    
    assert item.item_id == "ebay_123456789"
    assert item.source_platform == "ebay"  # Verifies default field works
    assert item.process_state == "ACTIVE"  # Overridden default working
    assert isinstance(item.date_fetched, datetime)
    assert item.has_bent_pins is False     # Default Boolean flag
    assert item.image_urls == []          # Default empty array factory


def test_historical_market_item_initialization(base_valid_payload):
    """Verifies that HistoricalMarketItem hydrates with accurate archival defaults."""
    item = HistoricalMarketItem(**base_valid_payload)
    
    assert item.item_id == "ebay_123456789"
    assert item.process_state == "PENDING"
    assert item.is_sold is True
    assert item.data_grade == "BRONZE"
    assert isinstance(item.timestamp, datetime)


def test_pydantic_type_coercion(base_valid_payload):
    """Confirms that Pydantic properly coerces numeric strings into floats/ints."""
    base_valid_payload["price"] = "145.50"          # String to be coerced to float
    base_valid_payload["condition_id"] = "3000"     # String to be coerced to int
    
    item = ActiveMarketItem(**base_valid_payload)
    assert item.price == 145.50
    assert item.condition_id == 3000


def test_missing_required_fields_raises_validation_error():
    """Ensures Pydantic throws a ValidationError when key metrics are missing."""
    incomplete_payload = {
        "item_id": "123",
        # model_name is missing
        "category": "CPU"
    }
    
    with pytest.raises(ValidationError) as exc_info:
        ActiveMarketItem(**incomplete_payload)
        
    assert "model_name" in str(exc_info.value)


def test_item_specifics_default_factory(base_valid_payload):
    """Ensures dict items can be dynamically altered without sharing references across instances."""
    item_1 = ActiveMarketItem(**base_valid_payload)
    item_2 = ActiveMarketItem(**base_valid_payload)
    
    item_1.item_specifics["Socket"] = "AM4"
    
    assert "Socket" in item_1.item_specifics
    assert "Socket" not in item_2.item_specifics  # Proves reference separation