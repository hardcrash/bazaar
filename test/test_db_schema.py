import pytest
from sqlalchemy import inspect
from src.database.models import ActiveMarketItemModel, HistoricalMarketItemModel, Base

def get_columns(model_class):
    """Utility to extract column names and types from an SQLAlchemy model."""
    inspector = inspect(model_class)
    return {col.name: col.type for col in inspector.columns}

def test_active_and_historical_schema_symmetry():
    """
    Ensures that fields shared between Active and Historical models 
    have consistent naming and types, preventing downstream pipeline crashes.
    """
    active_cols = get_columns(ActiveMarketItemModel)
    hist_cols = get_columns(HistoricalMarketItemModel)
    
    # Define fields that MUST exist in both
    shared_fields = [
        "item_id", "source_platform", "model_name", "category", 
        "title", "price", "condition_id", "has_bent_pins"
    ]
    
    for field in shared_fields:
        assert field in active_cols, f"{field} missing from Active model"
        assert field in hist_cols, f"{field} missing from Historical model"
        assert type(active_cols[field]) == type(hist_cols[field]), \
            f"Type mismatch for {field} between Active and Historical models"

def test_model_required_fields_presence():
    """Verify core identifiers are enforced."""
    active_cols = inspect(ActiveMarketItemModel)
    # Check that item_id is indeed a primary key
    assert any(col.primary_key for col in active_cols.columns if col.name == "item_id")