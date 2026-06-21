# src/analysis/strategy/analysis_strategy_factory.py

from src.analysis.strategy.cpu_strategy import CPUStrategy, ActiveCPUStrategy, HistoricalCPUStrategy
from src.analysis.strategy.base_category_strategy import BaseCategoryStrategy

class AnalysisStrategyFactory:
    @staticmethod
    def get_strategy(category_key: str, mode: str, config) -> BaseCategoryStrategy:
        """
        Dynamically extracts and builds execution tracking strategy objects
        based on configuration matrices and pipeline run modes.
        """
        cat_upper = category_key.upper()

        # 1. Handle configuration safely whether it's an Object (Attr) or a Dict (Key)
        if hasattr(config, 'categories'):
            global_categories = config.categories
        elif isinstance(config, dict) and 'categories' in config:
            global_categories = config['categories']
        elif isinstance(config, dict):
            global_categories = config
        else:
            global_categories = {}

        # 2. Narrow it down to the specific category sub-block
        category_yaml = global_categories.get(cat_upper, global_categories)

        # 3. Strategy Routing Matrix
        if cat_upper == "CPU":
            if mode.lower() == "historical":
                return HistoricalCPUStrategy(category_name="CPU", yaml_data=category_yaml)
            return ActiveCPUStrategy(category_name="CPU", yaml_data=category_yaml)

        elif cat_upper in ["HIGH_TIER_MOTHERBOARD", "MID_TIER_MOTHERBOARD"]:
            raise NotImplementedError("Motherboard tracking structures are coming next!")
        else:
            raise ValueError(f"❌ Unsupported pipeline category configuration flag: {category_key}")
