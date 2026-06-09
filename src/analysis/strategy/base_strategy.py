from abc import ABC, abstractmethod
from typing import Tuple

class BaseStrategy(ABC):
    """
    Abstract Base Class for all product analysis strategies.
    Any new category MUST implement these methods.
    """
    def __init__(self, config_dict: dict):
        """
        config_dict: The category-specific configuration dictionary
                     pulled from config.categories[category_key]
        """
        self.config = config_dict
        self.noise_words = config_dict.get("noise_words", [])
        self.blacklist_words = config_dict.get("blacklist_words", [])

    @abstractmethod
    def is_valid(self, title: str) -> bool:
        """Determines if the listing is a candidate for sourcing."""
        pass

    @abstractmethod
    def clean_title(self, title: str) -> str:
        """Removes noise words to normalize the title for matching."""
        pass

    @abstractmethod
    def extract_model(self, title: str) -> str:
        """Identifies the canonical model name from the cleaned title."""
        pass

    def parse_title(self, title: str) -> Tuple[str, str]:
        """
        Unified ingestion bridge called by the pipeline.
        Returns: (brand, model_name)
        """
        upper_title = title.upper()
        if not self.is_valid(upper_title):
            return "UNKNOWN", "UNKNOWN"

        cleaned = self.clean_title(upper_title)
        model = self.extract_model(cleaned)

        # Pull brand from config context or fallback
        brand = self.config.get("brand", "UNKNOWN").upper()
        return brand, (model if model else "UNKNOWN")

    def get_sourcing_score(self, title: str, price: float) -> float:
        """Optional: Defines how we rank a 'broken' item for purchase."""
        return 0.0
