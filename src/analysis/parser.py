# src/analysis/parser.py
import re
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, List

class ParsingStrategy(ABC):
    """
    Abstract Base Class strategy interface for parsing specific hardware domains.
    """
    @abstractmethod
    def configure(self, config_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def parse_title(self, title_upper: str) -> Tuple[str, str]:
        """Returns (brand, model) or (None, None)"""
        pass


class RegexChipsetStrategy(ParsingStrategy):
    """Handles multi-pattern chipset and companion modifier scanning (Motherboards/GPUs)."""
    def __init__(self):
        self.brands: List[str] = []
        self.patterns: List[re.Pattern] = []
        self.noise_rx: re.Pattern = None

    def configure(self, config_data: Dict[str, Any]) -> None:
        self.brands = [b.upper() for b in config_data.get("brands", [])]
        self.patterns = [re.compile(p, re.IGNORECASE) for p in config_data.get("patterns", [])]

        noise_words = config_data.get("noise_words", [])
        if noise_words:
            # Compiles words like \b(AM4|DDR4|CPU)\b for quick cleanup strips
            self.noise_rx = re.compile(r'\b(' + '|'.join(map(re.escape, noise_words)) + r')\b', re.IGNORECASE)

    def parse_title(self, title_upper: str) -> Tuple[str, str]:
        # Resolve Vendor Brand
        detected_brand = None
        for brand in self.brands:
            if brand in title_upper:
                detected_brand = brand
                break

        # Resolve Model Core
        for pattern in self.patterns:
            match = pattern.search(title_upper)
            if match:
                parts = [m.strip() for m in match.groups() if m]
                model_raw = " ".join(parts).strip()

                # Clean out trailing qualifier noise
                if self.noise_rx:
                    model_raw = self.noise_rx.sub('', model_raw).strip()

                if model_raw:
                    return detected_brand or "UNKNOWN", model_raw

        return None, None


class RegexLookaheadStrategy(ParsingStrategy):
    """Handles structured tracking patterns requiring clean static string prefixes (CPUs)."""
    def __init__(self):
        self.brands: List[str] = []
        self.patterns: List[re.Pattern] = []
        self.prefix: str = ""

    def configure(self, config_data: Dict[str, Any]) -> None:
        self.brands = [b.upper() for b in config_data.get("brands", [])]
        self.patterns = [re.compile(p, re.IGNORECASE) for p in config_data.get("patterns", [])]
        self.prefix = config_data.get("prefix", "").strip()

    def parse_title(self, title_upper: str) -> Tuple[str, str]:
        detected_brand = self.brands[0] if self.brands else "UNKNOWN"

        for pattern in self.patterns:
            match = pattern.search(title_upper)
            if match:
                model_core = match.group(1).strip()
                full_model = f"{self.prefix} {model_core}".strip() if self.prefix else model_core
                return detected_brand, full_model

        return None, None


class ComponentParserRegistry:
    """
    Factory orchestrating configuration files and dynamically routing strategies.
    """
    def __init__(self, config_json_path: str = "parser_config.json"):
        import json
        with open(config_json_path, "r") as f:
            self.config_data = json.load(f)

        # Strategy Registry Binding Map
        self._strategies_map = {
            "RegexChipsetStrategy": RegexChipsetStrategy,
            "RegexLookaheadStrategy": RegexLookaheadStrategy
        }

    def get_strategy_for_category(self, category: str) -> ParsingStrategy:
        cat_meta = self.config_data["categories"].get(category)
        if not cat_meta:
            return None

        class_name = cat_meta["strategy_class"]
        strategy_class = self._strategies_map.get(class_name)
        if not strategy_class:
            return None

        strategy_instance = strategy_class()
        strategy_instance.configure(cat_meta["config"])
        return strategy_instance
