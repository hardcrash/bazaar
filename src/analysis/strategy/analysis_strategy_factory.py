from src.analysis.strategy.cpu_strategy import CPUStrategy
from src.analysis.strategy.motherboard_strategy import MotherboardStrategy

class AnalysisStrategyFactory:
    @staticmethod
    def get_strategy_for_category(category_key: str, config) -> any:
        """
        category_key: e.g., 'CPU', 'MOTHERBOARD'
        config: The complete AppConfig provider instance
        """
        # Isolate the targeted configurations for the specific block
        cat_upper = category_key.upper()
        cat_config = config.categories.get(category_key, {}) if hasattr(config, 'categories') else {}

        if cat_upper == "CPU":
            return CPUStrategy(config_dict=cat_config)
        elif cat_upper == "MOTHERBOARD":
            return MotherboardStrategy(config_dict=cat_config)
        else:
            raise ValueError(f"❌ Unsupported pipeline execution category strategy: {category_key}")
