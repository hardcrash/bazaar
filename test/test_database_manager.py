# tests/test_database_manager.py
import pytest
from unittest.mock import MagicMock
from src.core.models import MarketItem
from src.database.db_manager import DatabaseManager
from src.database.models import MarketItemModel, HistoricalMetricModel

@pytest.fixture
def mock_config():
    """Provides a dummy config that points to an in-memory SQLite database."""
    config = MagicMock()
    config.params = {"database": {"path": ":memory:"}}
    return config

@pytest.fixture
def db_manager(mock_config):
    """Initializes the DatabaseManager with an isolated in-memory engine."""
    manager = DatabaseManager(config=mock_config)
    return manager

@pytest.fixture
def sample_market_item():
    """Returns a realistic MarketItem dataclass instance for storage testing."""
    return MarketItem(
        item_id="123456789012",
        model_name="5800X",
        category="164",
        source_platform="ebay",
        raw_title="AMD Ryzen 7 5800X 8-Core Processor - PERFECT",
        title="AMD Ryzen 7 5800X",
        price=115.00,
        shipping_cost=5.00,
        total_cost=120.00,
        currency="USD",
        condition_id=3000,
        is_sold=True,
        is_for_parts_or_not_working=False,
        condition_description="Excellent working condition",
        seller_username="component_king",
        feedback_score=1550,
        feedback_percentage=99.8,
        buying_options="Buy It Now",  # Normalized string descriptor
        process_state="PENDING"
    )

def test_database_initialization(db_manager):
    """Verifies that DatabaseManager automatically creates tables on startup."""
    from sqlalchemy import inspect
    inspector = inspect(db_manager.engine)
    tables = inspector.get_table_names()

    assert "market_items" in tables
    assert "historical_metrics" in tables

def test_insert_harvested_item_success(db_manager, sample_market_item):
    """Verifies a fresh MarketItem dataclass converts and saves to the database."""
    db_manager.insert_harvested_item(sample_market_item)

    session = db_manager.SessionLocal()
    db_record = session.query(MarketItemModel).filter_by(item_id="123456789012").first()
    session.close()

    assert db_record is not None
    assert db_record.model_name == "5800X"
    assert db_record.total_cost == 120.00
    assert db_record.process_state == "PENDING"

def test_insert_harvested_item_upsert_behavior(db_manager, sample_market_item):
    """Verifies that inserting an item with an existing ID updates it instead of crashing."""
    db_manager.insert_harvested_item(sample_market_item)

    # Modify state parameters on the same object
    sample_market_item.process_state = "ANALYZED"
    sample_market_item.price = 110.00
    sample_market_item.total_cost = 115.00

    db_manager.insert_harvested_item(sample_market_item)

    session = db_manager.SessionLocal()
    records = session.query(MarketItemModel).filter_by(item_id="123456789012").all()
    session.close()

    assert len(records) == 1  # No duplicates created
    assert records[0].process_state == "ANALYZED"
    assert records[0].total_cost == 115.00
