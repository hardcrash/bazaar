# src/analysis/strategy/analysis_strategy_factory.py
from src.analysis.strategy.cpu_strategy import ActiveCPUStrategy, HistoricalCPUStrategy

class AnalysisStrategyFactory:
    @staticmethod
    def get_strategy(category_key: str, mode: str, config) -> any:
        """
        category_key: e.g., 'CPU'
        mode: 'active' or 'historical'
        """
        cat_upper = category_key.upper()
        # Pass the global yaml data payload raw to the strategy initializer
        yaml_data = config.categories if hasattr(config, 'categories') else {}

        if cat_upper == "CPU":
            if mode.lower() == "historical":
                return HistoricalCPUStrategy(category_name="CPU", yaml_data=yaml_data)
            return ActiveCPUStrategy(category_name="CPU", yaml_data=yaml_data)

        elif cat_upper in ["HIGH_TIER_MOTHERBOARD", "MID_TIER_MOTHERBOARD"]:
            # Placeholder for upcoming Motherboard classes
            raise NotImplementedError("Motherboard tracking structures are coming next!")
        else:
            raise ValueError(f"❌ Unsupported pipeline category: {category_key}")
