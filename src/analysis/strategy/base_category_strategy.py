"""
Bazaar Strategy Contract Infrastructure

Defines the abstract interface for hardware-specific domain strategies.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
from src.core.models import ActiveMarketItem, HistoricalMarketItem
from src.analysis.schema.config_schema import CpuStrategyConfig


class BaseCategoryStrategy(ABC):
    def __init__(self, category_name: str, yaml_config: Any):
        """
        Initializes the category strategy with isolated configuration parameters.
        
        Args:
            category_name: Uppercase string identifier (e.g., 'CPU').
            yaml_config: Pre-sliced segment configuration (Can be dict or typed Pydantic config).
        """
        self.category_name = category_name.upper()
        # Keep backward compatibility if a raw dict is still passed anywhere
        self.config = yaml_config or {}
        self.is_strongly_typed = isinstance(yaml_config, CpuStrategyConfig)

    @property
    def valid_models(self) -> List[str]:
        """List of target model numbers or string names allowed under this category."""
        if self.is_strongly_typed:
            return self.config.global_config.valid_models
        return self.config.get("valid_models", [])

    @property
    def search_format(self) -> str:
        """The platform-specific query template used to build search strings."""
        if self.is_strongly_typed:
            return self.config.global_config.search_format
        return self.config.get("search_format", "{model}")

    @property
    def price_bounds(self) -> Tuple[float, float]:
        """Fallback hard limits for parsing sweeps."""
        if self.is_strongly_typed:
            return float(self.config.active_harvest.min_price), float(self.config.active_harvest.max_price)
        bounds = self.config.get("price_bounds", [0.0, 9999.0])
        return float(bounds[0]), float(bounds[1])

    def get(self, key: str, default: Any = None) -> Any:
        """
        Unified utility method to maintain backward compatibility with legacy test suites 
        querying configuration options via standard dictionary `.get()` syntax.
        """
        if self.is_strongly_typed:
            # Check if the key matches a top-level field or a nested sub-model
            if hasattr(self.config, key):
                val = getattr(self.config, key)
                # If it's a sub-model, wrap it so it supports dict-like .get() down the chain
                if hasattr(val, "model_dump"):
                    return val.model_dump()
                return val
            return default
        return self.config.get(key, default)

    @abstractmethod
    def clean_title(self, raw_title: str) -> str:
        pass

    @abstractmethod
    def extract_model(self, raw_title: str) -> str:
        pass

    @abstractmethod
    def is_valid_listing(self, cleaned_title: str, extracted_model: str) -> bool:
        pass

    @abstractmethod
    def parse_active(self, raw_data: Dict[str, Any], target_model: str) -> Optional[ActiveMarketItem]:
        pass

    @abstractmethod
    def parse_historical(self, raw_data: Dict[str, Any], target_model: str) -> Optional[HistoricalMarketItem]:
        pass