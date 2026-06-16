# src/analysis/strategy/cpu_strategy.py

import re
from loguru import logger
from src.analysis.strategy.base_category_strategy import BaseCategoryStrategy
from src.core.models import MarketItem

class BaseCPUStrategy(BaseCategoryStrategy):

    def __init__(self, category_name: str, yaml_data: dict):
        # 1. Let BaseCategoryStrategy handle structural dictionary scoping and private backing arrays
        super().__init__(category_name, yaml_data)

        # 2. Extract specific CPU strategy structural constraints safely from self.config
        self.multisku_models = self.config.get("multisku_models", [])
        self.noise_words = self.config.get("noise_words", [])

        # Pre-compile regexes for each variant to allow for optional whitespace
        raw_variants = self.config.get("model_variants", {})
        self.variant_regexes = {}
        for target, variants in raw_variants.items():
            target_canonical = target.replace(" ", "").upper()
            compiled_list = []
            for v in variants:
                # 🛠️ BUG FIX: Escape each character first, THEN join them with \s*
                pattern = r"\s*".join(re.escape(char) for char in v)
                # Ensure the loose whitespace check matches bounding word limits
                pattern = r"\b" + pattern + r"\b"
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

        # 1. Clean up eBay UI boilerplate text immediately so it doesn't trigger false flags
        clean_title = title_upper.replace("OPENS IN A NEW WINDOW OR TAB", "").strip()

        # 2. Base structural API blacklist (Safe for straight substring checks)
        if any(word.upper() in clean_title for word in self.blacklist_words):
            return "INVALID"

        # 3. Local Noise Check with Strict Word Boundaries 🛡️
        for term in self.local_noise_blacklist:
            # \b rules ensure "FOR" won't look inside words or adjacent formatting slices
            pattern = rf"\b{re.escape(term.upper())}\b"
            if re.search(pattern, clean_title):
                logger.debug(f"Drop -> Filter item contains blacklisted word token: '{term}'")
                return "INVALID"

        # 4. Multi-SKU Protection Loop
        models_found = [m for m in self.multisku_models if m.upper() in clean_title]
        if len(models_found) >= 2:
            return "MSKU"

        # 5. Extract and verify precise model target matching
        if self.extract_model(clean_title, target_model.upper()) != target_model.upper():
            return "INVALID"

        return "VALID"

    def extract_specific_attributes(self, html_content: str, item: MarketItem) -> MarketItem:
        """Parses raw leaf-node description HTML to evaluate and flag potential
        hardware defect indicators such as bent processor pins or general failures.
        """
        html_lower = html_content.lower()

        # Evaluate dynamic defect queries from config
        defect_queries = self.config.get("defect_queries", ["bent", "broken", "parts only"])
        has_defect = any(q.lower() in html_lower for q in defect_queries)

        # Specific target patterns matching your DB schema fields
        has_bent_pins = "bent pin" in html_lower or "bent pins" in html_lower
        is_parts_only = item.condition_id == 7000 or "parts only" in html_lower

        # Mutate flags into dataclass properties safely
        item.is_for_parts_or_not_working = is_parts_only or has_defect
        item.has_bent_pins = has_bent_pins
        item.process_state = "HYDRATED"

        return item

    def is_valid_standalone(self, item: MarketItem) -> bool:
        return "combo" not in item.title.lower()

    def get_price_brackets(self, pass_type: str = "used") -> list[tuple[float, float]]:
        harvest = self.config.get("historical_harvest", {})

        # Determine which YAML keys to use based on the pass type
        prefix = "broken" if pass_type == "broken" else "used"
        min_p = float(harvest.get(f"min_price_{prefix}", 110.0))
        max_p = float(harvest.get(f"max_price_{prefix}", 140.0))
        step = float(harvest.get("step_size", 5.0))

        brackets = []
        current = min_p
        while current < max_p:
            upper = min(current + step, max_p)
            brackets.append((current, upper))
            current += step
        return brackets


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

    @property
    def max_price_cap(self) -> float:
        _, max_p = self.price_bounds
        return max_p
