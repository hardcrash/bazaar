# src/analysis/strategy/base_category_strategy.py
"""
Bazaar Strategy Contract Infrastructure

Defines the abstract interface for hardware-specific domain strategies.
Strategies are responsible for parsing, normalization, validation, and schema
hydration, abstracting marketplace-specific layouts away from core business logic.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
from src.core.models import ActiveMarketItem, HistoricalMarketItem


class BaseCategoryStrategy(ABC):
    def __init__(self, category_name: str, yaml_config: dict):
        """
        Initializes the category strategy with isolated configuration parameters.
        
        Args:
            category_name: Uppercase string identifier (e.g., 'CPU').
            yaml_config: Pre-sliced segment corresponding strictly to this category 
                        from categories.yaml.
        """
        self.category_name = category_name.upper()
        self.config = yaml_config or {}

    @property
    def valid_models(self) -> List[str]:
        """List of target model numbers or string names allowed under this category."""
        return self.config.get("valid_models", [])

    @property
    def search_format(self) -> str:
        """The platform-specific query template used to build search strings."""
        return self.config.get("search_format", "{model}")

    @property
    def price_bounds(self) -> Tuple[float, float]:
        """
        Fallback hard limits for parsing sweeps. 
        Returns a tuple of (min_price, max_price).
        """
        bounds = self.config.get("price_bounds", [0.0, 9999.0])
        return float(bounds[0]), float(bounds[1])

    @abstractmethod
    def clean_title(self, raw_title: str) -> str:
        """Strips marketing clutter, emojis, and structural noise out of a raw listing title."""
        pass

    @abstractmethod
    def extract_model(self, raw_title: str) -> str:
        """Applies regex pattern matching to map structural titles to canonical model references."""
        pass

    @abstractmethod
    def is_valid_listing(self, cleaned_title: str, extracted_model: str) -> bool:
        """Evaluates blacklist tokens and string combinations to drop junk listings."""
        pass

    # 🚀 Unified Model Construction Engine Gateway Contracts
    @abstractmethod
    def parse_active(self, raw_data: Dict[str, Any], target_model: str) -> Optional[ActiveMarketItem]:
        """
        Transforms a raw scraper payload into a validated ActiveMarketItem.
        Returns None if validation criteria or blacklists fail.
        """
        pass

    @abstractmethod
    def parse_historical(self, raw_data: Dict[str, Any], target_model: str) -> Optional[HistoricalMarketItem]:
        """
        Transforms a raw scraper payload into a validated HistoricalMarketItem.
        Returns None if validation criteria or blacklists fail.
        """
        pass