# test/test_sanitation.py
"""
Bazaar Ingestion Sanitation and Schema Test Suite

This module provides field-level parsing validation, currency string cleaning checks, 
and text formatting guardrail metrics. It also checks formatting bounds for 
ActiveMarketItemModel string representations.
"""

import pytest
from pydantic import ValidationError
from src.core.sanitation_schemas import EbayAPIItemSchema
import datetime
from src.database.models import ActiveMarketItemModel

@pytest.fixture
def valid_ebay_json():
    """Provides a pristine mock of an incoming multi-SKU API JSON payload."""
    return {
        "itemId": "v1-257461931760-0",
        "title": "AMD Ryzen 7 5800X 8-Core Processor ",
        "price": "$249.99",
        "shippingCost": "+$5.00",
        "conditionId": 3000,
        "sellerUser": "bazaar_components_edge",
        "feedbackScore": 1425,
        "positiveFeedbackPercent": 99.4
    }

def test_successful_sanitation_and_transformation(valid_ebay_json):
    """Verifies that pristine payloads are correctly parsed and numeric types cleaned."""
    schema = EbayAPIItemSchema(**valid_ebay_json)

    assert schema.item_id == "v1-257461931760-0"
    assert schema.title == "AMD Ryzen 7 5800X 8-Core Processor"
    assert float(schema.price_string) == 249.99
    assert float(schema.shipping_string) == 5.00
    assert schema.condition_id == 3000

def test_currency_stripping_on_messy_strings(valid_ebay_json):
    """Ensures weird currency formats, localized commas, and symbols are scrubbed."""
    valid_ebay_json["price"] = "USD 1,249.50"
    valid_ebay_json["shippingCost"] = "FREE"

    schema = EbayAPIItemSchema(**valid_ebay_json)
    assert float(schema.price_string) == 1249.50
    assert float(schema.shipping_string) == 0.0

def test_missing_required_fields_raises_validation_error(valid_ebay_json):
    """Asserts that missing vital tracking keys causes an immediate execution rejection."""
    del valid_ebay_json["itemId"]  # Remove crucial structural key

    with pytest.raises(ValidationError) as exc_info:
        EbayAPIItemSchema(**valid_ebay_json)

    assert "itemId" in str(exc_info.value)

def test_invalid_condition_id_brackets_rejected(valid_ebay_json):
    """Verifies our custom validator interceptor throws flags on rogue condition numbers."""
    valid_ebay_json["conditionId"] = 9999  # Out of range non-existent eBay tier

    with pytest.raises(ValidationError) as exc_info:
        EbayAPIItemSchema(**valid_ebay_json)

    assert "Invalid eBay condition ID specification" in str(exc_info.value)

def test_repr_line_length_bounds_enforcement():
    """Verifies that large models with extensive attribute sets format their
    __repr__ output such that no individual line exceeds 80 characters.
    """
    # Create an artificially data-dense record instance to force character overflow
    dense_item = ActiveMarketItemModel(
        item_id="v1-999999999999-99",
        model_name="AMD_RYZEN_9_5950X_EXTREME_EDITION",
        category="COMPUTING_HARDWARE_PROCESSORS_CPUS",
        raw_title="AMD Ryzen 9 5950X 16-Core 32-Thread Unlocked Desktop Processor New",
        title="AMD Ryzen 9 5950X (New)",
        price=549.99,
        shipping_cost=15.45,
        total_cost=565.44,
        currency="USD",
        seller_username="premium_silicon_distribution_hub",
        is_top_rated=True,
        date_fetched=datetime.datetime(2026, 6, 11, 12, 0, 0),
        process_state="PROCESSED_BY_DEEP_HARVEST_PIPELINE_ENGINE"
    )

    # Generate the string representation via our mixin
    repr_output = repr(dense_item)

    # Isolate individual lines from the generated text block
    lines = repr_output.split("\n")

    # Assert conditions against every generated component line
    for index, line in enumerate(lines):
        line_length = len(line)
        assert line_length <= 80, (
            f"Line breaking failure on row index {index}! "
            f"Length is {line_length} chars (Max: 80). Content: '{line}'"
        )

def test_title_sanitation_removes_embedded_whitespace_clutter(valid_ebay_json):
    """
    Validates that messy titles featuring internal spacing clutter, tabs, or newline
    escapes are normalized cleanly into predictable single-spaced strings.
    """
    valid_ebay_json["title"] = "AMD\tRyzen   7 \n 5800X  Processor  "

    schema = EbayAPIItemSchema(**valid_ebay_json)

    # Internal spacing layout is collapsed down to simple single-character bounds
    assert schema.title == "AMD Ryzen 7 5800X Processor"    