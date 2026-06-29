# test/test_config_integrity.py

import os
import pytest
from src.util.config_loader import AppConfig
from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory

def test_yaml_configuration_schema_integrity():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(current_dir, ".."))
    settings_path = os.path.join(project_root, "settings")

    config = AppConfig(settings_dir=settings_path)
    assert "CPU" in config.categories

    try:
        strategy = AnalysisStrategyFactory.get_strategy("CPU", config)
        assert strategy is not None
        
        # Pulls from the actual configuration blocks safely
        active_harvest = strategy.config.get("active_harvest", {})
        assert active_harvest.get("ebay_category_id") == 164
    except Exception as e:
        pytest.fail(f"Strategy Factory failed to hydrate from actual YAML: {e}")