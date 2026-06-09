# test/test_config_integrity.py
import pytest
# Import the class instead of a function
from src.util.config_loader import AppConfig
from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory

def test_yaml_configuration_schema_integrity():
    # Instantiate the class (you may need to adjust the path to your config directory)
    config = AppConfig(settings_dir="settings")

    # Verify the essential Category keys exist
    assert "CPU" in config.categories

    # Verify the Factory can spin up a strategy for all defined categories
    try:
        # Note: AnalysisStrategyFactory expects an object with a .categories attribute
        strategy = AnalysisStrategyFactory.get_strategy("CPU", "active", config)
        assert strategy is not None
        assert strategy.category_id == "164"
    except Exception as e:
        pytest.fail(f"Strategy Factory failed to hydrate from actual YAML: {e}")
