# src/analysis/strategy/analysis_strategy_factory.py

from src.analysis.strategy.cpu_strategy import ActiveCPUStrategy, HistoricalCPUStrategy

class AnalysisStrategyFactory:
    @staticmethod
    def get_strategy(category_key: str, mode: str, config) -> any:
        """
        Dynamically extracts and builds execution tracking strategy objects
        based on configuration matrices and pipeline run modes.
        """
        cat_upper = category_key.upper()

        # 1. Safely extract raw global categories layout payload
        global_categories = config.categories if hasattr(config, 'categories') else {}

        # 2. Narrow it down to the specific category sub-block if nested (e.g., config.categories["CPU"])
        category_yaml = global_categories.get(cat_upper, global_categories)

        if cat_upper == "CPU":
            if mode.lower() == "historical":
                return HistoricalCPUStrategy(category_name="CPU", yaml_data=category_yaml)
            return ActiveCPUStrategy(category_name="CPU", yaml_data=category_yaml)

        elif cat_upper in ["HIGH_TIER_MOTHERBOARD", "MID_TIER_MOTHERBOARD"]:
            raise NotImplementedError("Motherboard tracking structures are coming next!")
        else:
            raise ValueError(f"❌ Unsupported pipeline category configuration flag: {category_key}")
