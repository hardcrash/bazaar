# src/analysis/strategy/analysis_strategy_factory.py
"""
Bazaar Analysis Strategy Factory

Responsible for parsing settings matrices, slicing localized category definitions
out of global configurations, and initializing domain processing strategies.
"""

from typing import Any
from src.analysis.strategy.cpu_strategy import CPUStrategy
from src.analysis.strategy.base_category_strategy import BaseCategoryStrategy


class AnalysisStrategyFactory:
    @staticmethod
    def get_strategy(category_key: str, config: Any) -> BaseCategoryStrategy:
        """
        Extracts relevant category slices out of the configuration map
        and initializes a unified domain evaluation strategy object.
        
        Args:
            category_key: Target hardware category token (e.g., 'CPU').
            config: Global application config object or raw dictionary layout.
            
        Returns:
            An instantiated concrete instance of CPUStrategy.
        """
        cat_upper = category_key.upper()

        # 1. Safely normalize configuration structures down to a dictionary core
        if hasattr(config, 'categories'):
            global_categories = config.categories
        elif isinstance(config, dict) and 'categories' in config:
            global_categories = config['categories']
        elif isinstance(config, dict):
            global_categories = config
        else:
            global_categories = {}

        # 2. Extract this specific category's block out of the matrix
        category_yaml = global_categories.get(cat_upper, {})
        if not category_yaml:
            raise ValueError(f"❌ Configuration matrix missing for category tracking tier: {cat_upper}")

        # 3. Polymorphic routing matrix
        if cat_upper == "CPU":
            return CPUStrategy(category_name="CPU", yaml_config=category_yaml)
            
        elif "MOTHERBOARD" in cat_upper:
            raise NotImplementedError("Motherboard strategy structures are coming next!")
            
        else:
            raise ValueError(f"❌ Unsupported marketplace tracking domain category: {category_key}")
