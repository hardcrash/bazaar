# test/test_analysis_strategy_factory.py
"""
Bazaar Analysis Strategy Factory Unit Tests

Validates configuration normalization variations, type-safe schema contracts,
unsupported domains, and validation failure exceptions.
"""

import pytest
from pydantic import ValidationError
from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory
from src.analysis.strategy.cpu_strategy import CPUStrategy


@pytest.fixture
def valid_cpu_yaml_block():
    """Provides a perfectly valid, raw YAML configuration segment for the CPU category."""
    return {
        "strategy_class": "CpuStrategy",
        "global": {
            "search_format": "Ryzen {model}",
            "valid_models": ["5800X"],
            "model_price_profiles": {},
            "model_variants": {},
            "multisku_models": [],
            "title_noise_words": [],
            "local_noise_blacklist": [],
            "api_blacklist_words": []
        },
        "active_harvest": {
            "enabled": True,
            "limit_per_sweep": 10,
            "min_price": 50.0,
            "max_price": 500.0,
            "step_size": 10.0,
            "ebay_category_id": 164,
            "ebay_condition": [3000],
            "alternative_queries": [],
            "salvage_keywords": [],
            "distress_keywords": [],
            "functional_keywords": []
        },
        "historical_harvest": {
            "enabled": False,
            "limit_per_sweep": 10,
            "require_sold": True,
            "step_size": 10.0,
            "ebay_category_id": [164],
            "ebay_condition": [3000],
            "use_profile_bounds": False,
            "alternative_queries": []
        }
    }


# ==================== Core Normalization Logic Tests ====================

def test_factory_normalizes_app_config_objects(valid_cpu_yaml_block):
    """Ensures factory can safely extract definitions when passed an AppConfig-like object."""
    class DummyAppConfig:
        def __init__(self):
            self.categories = {"CPU": valid_cpu_yaml_block}

    mock_config = DummyAppConfig()
    strategy = AnalysisStrategyFactory.get_strategy("CPU", mock_config)
    
    assert isinstance(strategy, CPUStrategy)
    assert strategy.is_strongly_typed is True


def test_factory_normalizes_nested_dict_configs(valid_cpu_yaml_block):
    """Ensures factory handles configurations where categories are inside a standard dict."""
    mock_config = {"categories": {"CPU": valid_cpu_yaml_block}}
    strategy = AnalysisStrategyFactory.get_strategy("cpu", mock_config)  # Testing case-insensitivity too
    
    assert isinstance(strategy, CPUStrategy)


# ==================== Contract & Validation Breach Tests ====================

def test_factory_raises_validation_error_on_malformed_yaml(valid_cpu_yaml_block):
    """Ensures a contract breach (e.g., mismatched variable types) trips a clear ValidationError."""
    # Break the schema constraint intentionally by giving an integer where a string format is required
    malformed_block = valid_cpu_yaml_block.copy()
    malformed_block["global"]["search_format"] = 12345  # Should be string

    mock_config = {"categories": {"CPU": malformed_block}}
    
    with pytest.raises(ValidationError):
        AnalysisStrategyFactory.get_strategy("CPU", mock_config)


# ==================== Polymorphic Boundary Matrix Tests ====================

def test_factory_raises_value_error_on_missing_category_slice():
    """Ensures factory fails fast if a tracking category is missing entirely from the matrices."""
    mock_config = {"categories": {"GPU": {}}}
    
    with pytest.raises(ValueError, match="Configuration matrix missing for category tracking tier"):
        AnalysisStrategyFactory.get_strategy("CPU", mock_config)


def test_factory_raises_not_implemented_for_motherboards(valid_cpu_yaml_block):
    """Verifies roadmap guardrail constraints for incomplete domain strategies."""
    mock_config = {"categories": {"MOTHERBOARD": {"some": "data"}}}
    
    with pytest.raises(NotImplementedError, match="Motherboard strategy structures are coming next"):
        AnalysisStrategyFactory.get_strategy("MOTHERBOARD", mock_config)


def test_factory_raises_value_error_for_completely_unsupported_categories():
    """Verifies that an unmapped, unknown category string throws an unmapped error."""
    mock_config = {"categories": {"SSD": {"some": "data"}}}
    
    with pytest.raises(ValueError, match="Unsupported marketplace tracking domain category"):
        AnalysisStrategyFactory.get_strategy("SSD", mock_config)