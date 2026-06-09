# src/analysis/strategy/cpu_strategy.py
import re
from src.analysis.strategy.base_strategy import BaseCategoryStrategy
from src.core.models import MarketItem

class BaseCPUStrategy(BaseCategoryStrategy):
    def __init__(self, category_name: str, yaml_data: dict):
        super().__init__(category_name, yaml_data)
        self.multisku_models = self.config.get("multisku_models", [])
        self.noise_words = self.config.get("noise_words", [])

        # Pre-compile regexes for each variant to allow for optional whitespace
        raw_variants = self.config.get("model_variants", {})
        self.variant_regexes = {}
        for target, variants in raw_variants.items():
            target_canonical = target.replace(" ", "").upper()
            compiled_list = []
            for v in variants:
                # Create a regex: 5\s*8\s*0\s*0\s*X (matches 5800X, 5 8 0 0 X, etc.)
                pattern = r"\s*".join(re.escape(char) for char in v)
                compiled_list.append((v, re.compile(pattern, re.IGNORECASE)))
            self.variant_regexes[target_canonical] = compiled_list

        yaml_patterns = self.config.get("patterns", [])
        if yaml_patterns:
            self.model_pattern = re.compile("|".join(yaml_patterns), re.IGNORECASE)
        else:
            self.model_pattern = re.compile(r'RYZEN(?:\s+[579])?\s+(5\d{3}(?:X3D|X|G|GE|XT)?)\b', re.IGNORECASE)

    def clean_title(self, title: str) -> str:
        cleaned = title.replace("New Listing", "")
        cleaned = cleaned.split("Opens in a new window")[0]
        for word in self.noise_words:
            cleaned = re.sub(r'\b' + re.escape(word) + r'\b', '', cleaned, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def extract_model(self, title_upper: str, target_upper: str) -> str:
        # 1. Priority: Check dynamic configuration variants with "fuzzy" spacing
        target_canonical = target_upper.replace(" ", "").upper()
        allowed_variants = self.variant_regexes.get(target_canonical, [])

        for original_name, regex in allowed_variants:
            if regex.search(title_upper):
                return original_name.upper()

        # 2. Priority: Check target model (strict boundary check)
        if re.search(r'\b' + re.escape(target_upper) + r'\b', title_upper):
            return target_upper

        # 3. Fallback to Regex pattern
        match = self.model_pattern.search(title_upper)
        if match:
            matched_str = match.group(1) if match.lastindex and match.group(1) else match.group(0)
            return matched_str.upper().strip()

        return "UNKNOWN"

    def is_valid(self, title: str, target_model: str) -> str:
        title_upper = title.upper()
        if any(word.upper() in title_upper for word in self.blacklist_words): return "INVALID"
        if any(term.upper() in title_upper for term in self.local_noise_blacklist): return "INVALID"

        models_found = [m for m in self.multisku_models if m.upper() in title_upper]
        if len(models_found) >= 2: return "MSKU"

        if self.extract_model(title_upper, target_model.upper()) != target_model.upper():
            return "INVALID"
        return "VALID"

    def extract_specific_attributes(self, html_content: str, item: MarketItem) -> MarketItem:
        item.has_bent_pins = any(q.lower() in html_content.lower() for q in self.config.get("defect_queries", []))
        return item

    def is_valid_standalone(self, item: MarketItem) -> bool:
        return "combo" not in item.title.lower()

# ActiveCPUStrategy and HistoricalCPUStrategy remain unchanged as you had them...

class ActiveCPUStrategy(BaseCPUStrategy):
    @property
    def category_id(self) -> str:
        return str(self.config.get("active_harvest", {}).get("ebay_category_id", "164"))

    @property
    def price_bounds(self) -> tuple[float, float]:
        harvest = self.config.get("active_harvest", {})
        return float(harvest.get("min_price", 50.0)), float(harvest.get("max_price", 650.0))

    @property
    def step_size(self) -> float:
        return float(self.config.get("active_harvest", {}).get("step_size", 10.0))

    # 🌟 Satisfies BaseCategoryStrategy abstract constraint cleanly
    @property
    def max_price_cap(self) -> float:
        _, max_p = self.price_bounds
        return max_p


class HistoricalCPUStrategy(BaseCPUStrategy):
    @property
    def category_id(self) -> str:
        return str(self.config.get("historical_harvest", {}).get("ebay_category_id", "164"))

    @property
    def price_bounds(self) -> tuple[float, float]:
        harvest = self.config.get("historical_harvest", {})
        return float(harvest.get("min_price_used", 115.0)), float(harvest.get("max_price_used", 650.0))

    @property
    def step_size(self) -> float:
        return float(self.config.get("historical_harvest", {}).get("step_size", 10.0))

    # 🌟 Satisfies BaseCategoryStrategy abstract constraint cleanly
    @property
    def max_price_cap(self) -> float:
        _, max_p = self.price_bounds
        return max_p
