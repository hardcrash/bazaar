# src/analysis/strategy/base_category_strategy.py

from abc import ABC, abstractmethod
from typing import List, Tuple
from src.core.models import HistoricalMarketItem

class BaseCategoryStrategy(ABC):
    def __init__(self, category_name: str, yaml_data: dict):
        # 1. Core identification markers
        self.category_name = category_name.upper()
        self.raw_yaml_matrix = yaml_data

        # 2. Extract and scope target category child block safely
        if isinstance(yaml_data, dict) and category_name in yaml_data:
            self.config = yaml_data[category_name]
        else:
            self.config = yaml_data or {}

        # 3. Guard property fallback states internally
        self._blacklist_words = self.config.get("blacklist_words", [])
        self._local_noise_blacklist = self.config.get("local_noise_blacklist", [])

    @property
    def blacklist_words(self) -> List[str]:
        return getattr(self, '_blacklist_words', self.config.get("blacklist_words", []))

    @property
    def local_noise_blacklist(self) -> List[str]:
        return self.config.get("local_noise_blacklist", [])

    @property
    def valid_models(self) -> List[str]:
        return self.config.get("valid_models", [])

    @property
    def search_format(self) -> str:
        return self.config.get("search_format", "{model}")

    @property
    @abstractmethod
    def category_id(self) -> str:
        """Returns targeted operational pathway category ID string."""
        pass

    @property
    @abstractmethod
    def price_bounds(self) -> Tuple[float, float]:
        """Returns a tuple of (min_price, max_price) for the current execution."""
        pass

    @property
    @abstractmethod
    def step_size(self) -> float:
        """Returns step increment for search bracket slicing."""
        pass

    @abstractmethod
    def clean_title(self, raw_title: str) -> str:
        """Strips out marketing and structural noise phrases from source string."""
        pass

    @abstractmethod
    def extract_model(self, title_upper: str, target_upper: str) -> str:
        """Identifies and assigns exact canonical component matches."""
        pass

    @abstractmethod
    def is_valid(self, title: str, target_model: str) -> str:
        """Evaluates noise blacklists and structural constraints to return state tags."""
        pass

    @abstractmethod
    def extract_specific_attributes(self, html_content: str, item: MarketItem) -> MarketItem:
        """Parses leaf page contents to mutate items up to enriched data grades (e.g., SILVER/GOLD)."""
        pass

    @abstractmethod
    def is_valid_standalone(self, item: MarketItem) -> bool:
        """Verifies if an item can bypass custom multi-sku or combo rule exclusions."""
        pass
