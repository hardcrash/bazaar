import pytest
from sqlalchemy import text
from src.database.db_manager import DatabaseManager
from src.analysis.aggregator import HistoricalAggregatorService
from src.database.models import MarketItemModel

@pytest.fixture
def memory_db_manager():
    """Spins up a volatile, decoupled in-memory database workspace for sandboxed pipeline testing."""
    config = {"database": {"path": ":memory:"}}
    return DatabaseManager(config=config)

def test_historical_aggregation_and_defect_segregation(memory_db_manager):
    """Ensures that the calculator properly filters and processes defect items
    separate from standard pool averages, generating clear statistical summaries.
    """
    session = memory_db_manager.SessionLocal()

    item_1 = MarketItemModel(
        item_id="t1",
        model_name="5800X",
        category="1",
        raw_title="AMD Ryzen 7 5800X CPU",
        title="AMD Ryzen 7 5800X CPU",
        price=200.0,
        total_cost=210.0,
        shipping_cost=10.0,
        is_sold=True,
        is_for_parts_or_not_working=False
    )
    item_2 = MarketItemModel(
        item_id="t2",
        model_name="5800X",
        category="1",
        raw_title="AMD Ryzen 7 5800X Brand New",
        title="AMD Ryzen 7 5800X Brand New",
        price=220.0,
        total_cost=220.0,
        shipping_cost=0.0,
        is_sold=True,
        is_for_parts_or_not_working=False
    )
    item_3 = MarketItemModel(
        item_id="t3",
        model_name="5800X",
        category="1",
        raw_title="AMD Ryzen 7 5800X BENT PINS AS-IS",
        title="AMD Ryzen 7 5800X BENT PINS AS-IS",
        price=90.0,
        total_cost=100.0,
        shipping_cost=10.0,
        is_sold=True,
        is_for_parts_or_not_working=True
    )

    session.add_all([item_1, item_2, item_3])
    session.commit()
    session.close()

    service = HistoricalAggregatorService(db_manager=memory_db_manager)
    summary = service.compute_market_metrics(model_name="5800X", timeframe_days=30)

    assert summary["processed_groups"] == 2

    verify_session = memory_db_manager.SessionLocal()
    query = text("SELECT total_units, avg_item_price FROM historical_metrics WHERE model_name = :m AND condition_type = :c")
    
    standard_stats = verify_session.execute(query, {"m": "5800X", "c": "STANDARD"}).fetchone()
    defect_stats = verify_session.execute(query, {"m": "5800X", "c": "DEFECTIVE"}).fetchone()

    assert standard_stats is not None
    assert standard_stats.total_units == 2
    assert standard_stats.avg_item_price == 210.0
    
    assert defect_stats is not None
    assert defect_stats.total_units == 1
    assert defect_stats.avg_item_price == 90.0

    verify_session.close()

def test_historical_aggregation_handles_empty_datasets_gracefully(memory_db_manager):
    """Ensures that when statistical profiling runs against a missing hardware model target,
    the system avoids math division crashes and responds with clean baseline defaults.
    """
    service = HistoricalAggregatorService(db_manager=memory_db_manager)
    summary = service.compute_market_metrics(model_name="NON-EXISTENT-CPU", timeframe_days=30)

    assert isinstance(summary, dict)
    assert summary.get("processed_groups", 0) == 0
