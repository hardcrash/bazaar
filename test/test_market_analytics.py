# test/test_market_analytics.py

import pytest
from sqlalchemy import text
from src.database.db_manager import DatabaseManager
from src.analysis.market_analytics_engine import MarketAnalyticsEngine
from src.database.models import HistoricalMarketItemModel

@pytest.fixture
def isolated_db_manager(tmp_path):
    test_db_file = tmp_path / "bazaar_analytics_test.db"
    config = {"database": {"path": str(test_db_file)}}
    return DatabaseManager(config=config)

def test_market_analytics_segregates_and_computes_metrics(isolated_db_manager):
    """
    Validates that MarketAnalyticsEngine correctly separates standard vs defective items
    and fires the correct mathematical aggregations into the metrics database.
    """
    session = isolated_db_manager.SessionLocal()
    
    # 1. Seed historical database with valid non-null text records
    mock_historical_data = [
        # Standard Pool Items (Average Price: $300, Average Shipping: $10)
        HistoricalMarketItemModel(
            item_id="1", model_name="7800X3D", category="processors",
            raw_title="AMD Ryzen 7 7800X3D Processor", title="AMD Ryzen 7 7800X3D",
            price=290.0, shipping_cost=10.0, total_cost=300.0, is_sold=True, condition_id=1000
        ),
        HistoricalMarketItemModel(
            item_id="2", model_name="7800X3D", category="processors",
            raw_title="AMD Ryzen 7 7800X3D 8-Core", title="AMD Ryzen 7 7800X3D",
            price=310.0, shipping_cost=10.0, total_cost=320.0, is_sold=True, condition_id=1000
        ),
        
        # Defective Pool Item (Condition 7000 / For parts)
        HistoricalMarketItemModel(
            item_id="3", model_name="7800X3D", category="processors",
            raw_title="AMD Ryzen 7 7800X3D BENT PINS", title="AMD Ryzen 7 7800X3D",
            price=100.0, shipping_cost=20.0, total_cost=120.0, is_sold=True, condition_id=7000
        )
    ]
    
    session.add_all(mock_historical_data)
    session.commit()
    session.close()

    # 2. Fire up the analytics engine offline
    engine = MarketAnalyticsEngine(db_manager=isolated_db_manager)
    metrics_result = engine.compute_market_metrics(model_name="7800X3D", timeframe_days=30)

    # 3. Verify it identified both groups successfully
    assert metrics_result["processed_groups"] == 2

    # 4. Pull raw metrics from SQLite to confirm math assertions
    session = isolated_db_manager.SessionLocal()
    standard_metrics = session.execute(
        text("SELECT * FROM historical_metrics WHERE model_name='7800X3D' AND condition_type='STANDARD'")
    ).fetchone()
    
    defective_metrics = session.execute(
        text("SELECT * FROM historical_metrics WHERE model_name='7800X3D' AND condition_type='DEFECTIVE'")
    ).fetchone()
    session.close()

    # Match database indices against computed central tendencies
    assert standard_metrics._mapping["total_units"] == 2
    assert standard_metrics._mapping["avg_item_price"] == 300.0
    assert standard_metrics._mapping["med_item_price"] == 300.0
    
    assert defective_metrics._mapping["total_units"] == 1
    assert defective_metrics._mapping["avg_item_price"] == 100.0