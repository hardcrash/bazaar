# test/test_config_integrity.py

import os
import pytest
from src.util.config_loader import AppConfig
from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory

def test_yaml_configuration_schema_integrity():
    # 1. Get absolute path to the directory containing this test file
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. Go up one level to the project root (bazaar-data)
    project_root = os.path.normpath(os.path.join(current_dir, ".."))

    # 3. Target the settings folder at the root
    settings_path = os.path.join(project_root, "settings")

    # --- Quick Debugging Check ---
    if not os.path.exists(os.path.join(settings_path, "categories.yaml")):
        print(f"\n[DEBUG] Project Root detected as: {project_root}")
        print(f"[DEBUG] Looking for settings at: {settings_path}")
        if os.path.exists(settings_path):
            print(f"[DEBUG] Files actually found in settings/: {os.listdir(settings_path)}")
        else:
            print(f"[DEBUG] The directory '{settings_path}' does not seem to exist from here.")
    # -----------------------------

    # 4. Initialize config with the foolproof absolute path
    config = AppConfig(settings_dir=settings_path)

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
