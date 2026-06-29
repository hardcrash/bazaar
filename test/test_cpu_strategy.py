# test/test_cpu_strategy.py
"""
Bazaar Strategy Suite Unit Tests

Validates raw title cleaning pipelines, multi-variant keyword blacklisting,
regex model isolation boundaries, and property metadata hydration.
"""

import pytest
from src.analysis.strategy.cpu_strategy import CPUStrategy


@pytest.fixture
def mock_global_yaml():
    """
    Matches the exact structured nested dictionary layer parsed out of 
    settings/categories.yaml, complete with unified parsing keys.
    """
    return {
        "strategy_class": "CpuStrategy",
        "valid_models": ["5800X", "5950X"],
        "model_variants": {
            "5950X": ["5950X"],
            "5800X": ["5800X", "5800X3D", "5800XT", "5800"]
        },
        "multisku_models": ["5600X", "5700X", "5800X", "5900X", "5950X"],
        "brands": ["AMD"],
        "patterns": [r"RYZEN(?:\s+[579])?\s+(5\d{3}(?:X3D|X|G|GE|XT)?)\b"],
        "title_noise_words": ["L@@K", "MINT"],
        "local_noise_blacklist": ["BUNDLE", "LAPTOP", "PC", "SYSTEM", "MOBO COMBO"],
        "search_format": "Ryzen {model}",
        "active_harvest": {
            "ebay_category_id": 164,
            "max_price": 650.0
        },
        "historical_harvest": {
            "min_price_used": 110.00,
            "max_price_used": 650.00,
            "step_size": 10.00,
            "ebay_category_id": 164
        }
    }


@pytest.fixture
def cpu_strategy(mock_global_yaml):
    """Provides a single unified strategy execution engine instance."""
    return CPUStrategy(category_name="CPU", yaml_config=mock_global_yaml)


# ==================== Core Extraction & Text Tests ====================

def test_clean_title(cpu_strategy):
    """Verifies standard layout padding and noise tokens are cleanly removed."""
    raw_title = "   L@@K AMD Ryzen 7 5800X Processor MINT   "
    assert cpu_strategy.clean_title(raw_title) == "AMD RYZEN 7 5800X PROCESSOR"


def test_is_valid_standalone(cpu_strategy):
    """Verifies target hardware matching logic validates clean assets."""
    assert cpu_strategy.is_valid_listing("AMD RYZEN 7 5800X PROCESSOR", "5800X") is True


def test_is_valid_blacklist_drop(cpu_strategy):
    """Verifies that items containing local_noise_blacklist items are dropped flat."""
    assert cpu_strategy.is_valid_listing("AMD RYZEN 7 5800X BUNDLE WITH COOLER", "5800X") is False


def test_extract_model_cross_bleed(cpu_strategy):
    """Ensures parser isolates specific token values, avoiding layout cross-bleed."""
    title = "[MSKU VARIANT] RYZEN 9 3950X"
    assert cpu_strategy.extract_model(title) == "UNKNOWN"


# ==================== Configuration Hydration Tests ====================

def test_strategy_extracts_nested_harvest_pricing_metrics(mock_global_yaml, cpu_strategy):
    """Ensures configuration blocks map cleanly to strategy attributes."""
    assert "BUNDLE" in cpu_strategy.blacklist
    assert cpu_strategy.config.get("active_harvest", {}).get("ebay_category_id") == 164