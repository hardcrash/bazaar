"""
Bazaar Analysis Strategy Factory

Responsible for parsing settings matrices, slicing localized category definitions
out of global configurations, and initializing domain processing strategies.
"""

from typing import Any
from loguru import logger
from pydantic import ValidationError
from src.analysis.strategy.cpu_strategy import CPUStrategy
from src.analysis.strategy.base_category_strategy import BaseCategoryStrategy
from src.analysis.schema.config_schema import CpuStrategyConfig


class AnalysisStrategyFactory:
    @staticmethod
    def get_strategy(category_key: str, config: Any) -> BaseCategoryStrategy:
        """
        Extracts relevant category slices out of the configuration map
        and initializes a unified domain evaluation strategy object.
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

        # 3. Polymorphic routing matrix with validation step
        if cat_upper == "CPU":
            try:
                # Validate raw dictionary data against Pydantic schema contract
                validated_config = CpuStrategyConfig.model_validate(category_yaml)
                logger.success("✅ CPU Category configurations verified successfully against schema contract.")
            except ValidationError as e:
                logger.critical(f"❌ Configuration contract breach detected for CPU category specifications!")
                raise e
    
            # FIX: Match the positional parameter name expected by CPUStrategy's constructor
            return CPUStrategy(category_name="CPU", yaml_config=validated_config)
            
        elif "MOTHERBOARD" in cat_upper:
            raise NotImplementedError("Motherboard strategy structures are coming next!")
            
        else:
            raise ValueError(f"❌ Unsupported marketplace tracking domain category: {category_key}")