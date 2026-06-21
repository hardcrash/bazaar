# test/cpu_strategy.py

import pytest
# Update imports to pull our decoupled architecture classes
from src.analysis.strategy.cpu_strategy import ActiveCPUStrategy, HistoricalCPUStrategy

@pytest.fixture
def mock_global_yaml():
    """Matches the exact nested structure of config/categories.yaml"""
    return {
        "CPU": {
            "strategy_class": "CpuStrategy",
            "valid_models": ["5800X", "5950X"],
            "blacklist_words": ["bundle", "laptop", "pc", "system"],
            "search_format": "Ryzen {model}",
            "active_harvest": {
                "ebay_category_id": 164,
                "max_price": 650.0
            },
            "historical_harvest": {
                "min_price_used": 110.00,
                "max_price_used": 650.00,
                "step_size": 10.00,
                "ebay_category_id": "164"
            }
        }
    }

@pytest.fixture
def active_cpu_strategy(mock_global_yaml):
    """Provides an Active execution pathway strategy instance."""
    return ActiveCPUStrategy(category_name="CPU", yaml_data=mock_global_yaml)

@pytest.fixture
def historical_cpu_strategy(mock_global_yaml):
    """Provides a Historical/Sold execution pathway strategy instance."""
    return HistoricalCPUStrategy(category_name="CPU", yaml_data=mock_global_yaml)


# ==================== Core Extraction & Text Tests ====================

def test_clean_title(active_cpu_strategy):
    raw_title = "   AMD Ryzen 7 5800X Processor  "
    assert active_cpu_strategy.clean_title(raw_title) == "AMD Ryzen 7 5800X Processor"

def test_is_valid_standalone(active_cpu_strategy):
    # Enforces active sourcing filtering
    assert active_cpu_strategy.is_valid("AMD Ryzen 7 5800X Processor", "5800X") == "VALID"

def test_is_valid_blacklist_drop(active_cpu_strategy):
    # Active pipeline rejects bundled configurations
    assert active_cpu_strategy.is_valid("AMD Ryzen 7 5800X BUNDLE with Cooler", "5800X") == "INVALID"

def test_extract_model_cross_bleed(active_cpu_strategy):
    # Confirms text parser blocks validation cross-bleed
    title = "[MSKU VARIANT] RYZEN 9 3950X"
    assert active_cpu_strategy.extract_model(title, "5800X") != "5800X"


# ==================== Configuration Hydration Tests ====================

def test_strategy_extracts_nested_harvest_pricing_metrics(mock_global_yaml):
    active_strat = ActiveCPUStrategy(category_name="CPU", yaml_data=mock_global_yaml)
    hist_strat = HistoricalCPUStrategy(category_name="CPU", yaml_data=mock_global_yaml)

    # Assert that global categorical core lists parse smoothly via properties
    assert "bundle" in active_strat.blacklist_words

    # Assert that distinct strategy instances pick up their custom nested price thresholds
    assert active_strat.category_id == "164"
    assert active_strat.max_price_cap == 650.0

    assert hist_strat.category_id == "164"
    assert hist_strat.max_price_cap == 650.0
