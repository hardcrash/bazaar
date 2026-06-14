# src/analysis/strategy/base_strategy.py
from abc import ABC, abstractmethod
from src.core.models import MarketItem

class BaseCategoryStrategy(ABC):
    def __init__(self, category_name: str, yaml_data: dict):
        """
        Populates category-wide rules from config/categories.yaml
        """
        self.category_name = category_name
        self.config = yaml_data.get(category_name, {})

    @property
    def blacklist_words(self) -> list:
        return self.config.get("blacklist_words", [])

    @property
    def local_noise_blacklist(self) -> list:
        return self.config.get("local_noise_blacklist", [])

    @property
    def valid_models(self) -> list:
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
    def price_bounds(self) -> tuple[float, float]:
        """Returns a tuple of (min_price, max_price) for the current execution."""
        pass

    @property
    @abstractmethod
    def step_size(self) -> float:
        """Returns step increment for search bracket slicing."""
        pass

    @abstractmethod
    def clean_title(self, raw_title: str) -> str:
        pass

    @abstractmethod
    def extract_model(self, title_upper: str, target_upper: str) -> str:
        pass

    @abstractmethod
    def is_valid(self, title: str, target_model: str) -> str:
        pass

    @abstractmethod
    def extract_specific_attributes(self, html_content: str, item: MarketItem) -> MarketItem:
        pass

    @abstractmethod
    def is_valid_standalone(self, item: MarketItem) -> bool:
        pass
