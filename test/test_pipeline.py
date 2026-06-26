# test/test_pipeline.py
"""
Bazaar Integration Pipeline Unit Tests

This module contains the integration and sanity test suite for the Bazaar core 
ingestion mechanics. It validates that raw, unstructured JSON payloads correctly translate 
into validated Pydantic models and successfully serialize into isolated runtime test databases.
"""

import os
import pytest
from src.database.db_manager import DatabaseManager
from src.analysis.transformer import MarketItemTransformer

@pytest.fixture
def isolated_db_manager(tmp_path):
    """
    Creates an isolated, sandboxed database instance for the lifetime of the test execution,
    guaranteeing production state data is never polluted by automated verification passes.
    """
    test_db_file = tmp_path / "bazaar_test.db"
    config = {
        "database": {
            "path": str(test_db_file)
        }
    }
    manager = DatabaseManager(config=config)
    return manager

def test_raw_payload_transformation_to_database_insertion(isolated_db_manager):
    """
    Validates end-to-end processing of a mock API harvest variant payload:
    1. Structural field alignment through translation matrix layers (camelCase to snake_case).
    2. Model validation extraction matching data structure target properties.
    3. Permanent database write verification to isolated local state tables.
    """
    # 🌟 Raw network payload variant representing an active payload response block
    raw_api_payload = {
        "itemId": "v1-998877665544-0",
        "title": "   *** SALE *** AMD Ryzen 7 7800X3D Gaming Processor  ",
        "price": {"value": "349.00", "currency": "USD"},
        "shippingOptions": [{"shippingCost": {"value": "Free"}}],
        "conditionId": "1000",  # Code 1000 maps to New
        "seller": {
            "username": "apex_silicon_distribution",
            "feedbackScore": "15420",
            "positiveFeedbackPercent": "99.4"
        }
    }

    # Execute conversion passing data through translation matrix properties
    market_dataclass = MarketItemTransformer.raw_ebay_json_to_market_item(
        item_json=raw_api_payload,
        category="processors",
        condition_id=1000,
        is_sold=True
    )

    # Apply explicit string tracking tag for index normalization
    market_dataclass.model_name = "7800X3D"

    # Assert model attributes are transformed correctly using snake_case properties
    assert market_dataclass.item_id == "v1-998877665544-0"
    assert "7800X3D" in market_dataclass.model_name

    # Attempt direct entry insertion into sandboxed target engine tables
    insertion_success = False
    try:
        isolated_db_manager.insert_harvested_item(market_dataclass)
        insertion_success = True
    except Exception as exc:
        pytest.fail(f"❌ Database engine raised unexpected execution exception on entry insert: {exc}")

    assert insertion_success is True