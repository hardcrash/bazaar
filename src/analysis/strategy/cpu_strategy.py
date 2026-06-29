# src/analysis/strategy/cpu_strategy.py
"""
Bazaar Concrete CPU Processing Strategy

Implements title purification, token pattern extraction, data-grade evaluation,
and dynamic price slicing for active and historical central processing units.
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger
from src.analysis.strategy.base_category_strategy import BaseCategoryStrategy
from src.core.models import ActiveMarketItem, HistoricalMarketItem


class CPUStrategy(BaseCategoryStrategy):
    def __init__(self, category_name: str, yaml_config: dict):
        super().__init__(category_name, yaml_config)
        
        # 1. Structural extraction
        self.noise_words = self.config.get("title_noise_words", [])
        self.blacklist = self.config.get("local_noise_blacklist", [])
        self.multisku_models = self.config.get("multisku_models", [])
        
        # 2. Extract and pre-compile regular expressions for core processing
        raw_patterns = self.config.get("patterns", [])
        if raw_patterns:
            self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in raw_patterns]
        else:
            # Domain-resilient fallback pattern targeting common desktop processor series
            self.compiled_patterns = [
                re.compile(r'RYZEN(?:\s+[579])?\s+(5\d{3}(?:X3D|X|G|GE|XT)?)\b', re.IGNORECASE)
            ]

        # 3. Handle model variant substitutions with soft whitespace resilience
        raw_variants = self.config.get("model_variants", {})
        self.variant_regexes = {}
        for target, variants in raw_variants.items():
            target_canonical = target.replace(" ", "").upper()
            compiled_list = []
            for v in variants:
                pattern = r"\s*".join(re.escape(char) for char in v)
                pattern = r"\b" + pattern + r"\b"
                compiled_list.append((v, re.compile(pattern, re.IGNORECASE)))
            self.variant_regexes[target_canonical] = compiled_list

    def clean_title(self, raw_title: str) -> str:
        """Strips structural boilerplate text and noise terms out of the listing title."""
        cleaned = raw_title.upper()
        cleaned = cleaned.replace("NEW LISTING", "")
        cleaned = cleaned.split("OPENS IN A NEW WINDOW")[0]
        
        for word in self.noise_words:
            cleaned = re.sub(r'\b' + re.escape(word.upper()) + r'\b', '', cleaned)
            
        return re.sub(r'\s+', ' ', cleaned).strip()

    def extract_model(self, raw_title: str) -> str:
        """Applies configuration variants and regex signatures to find canonical CPU models."""
        title_upper = raw_title.upper()

        # Check explicit spatial structural variants first
        for target_canonical, compiled_list in self.variant_regexes.items():
            for original_name, regex in compiled_list:
                if regex.search(title_upper):
                    return original_name.upper()

        # Run primary pattern scanners
        for pattern in self.compiled_patterns:
            match = pattern.search(title_upper)
            if match:
                matched_str = match.group(1) if match.lastindex and match.group(1) else match.group(0)
                return matched_str.upper().replace(" ", "")
                
        return "UNKNOWN"

    def is_valid_listing(self, cleaned_title: str, extracted_model: str) -> bool:
        """Verifies model boundaries, local word blacklists, and Multi-SKU hazards."""
        title_upper = cleaned_title.upper()

        if extracted_model not in self.valid_models:
            return False

        # Drop any records matching standard local blacklisted terms
        if any(bad_word.upper() in title_upper for bad_word in self.blacklist):
            return False

        # Protect against multi-SKU combo listings (e.g., "5600X OR 5800X")
        models_found = [m for m in self.multisku_models if m.upper() in title_upper]
        if len(models_found) >= 2:
            logger.debug(f"Dropped MSKU listing candidate: {cleaned_title}")
            return False

        return True

    def get_price_brackets(self, target_type: str = "used") -> List[Tuple[float, float]]:
        """
        Dynamically chunks search windows into targeted steps based on category profiles.
        Supports: 'active', 'used', or 'broken'.
        """
        harvest_block = self.config.get("historical_harvest" if target_type != "active" else "active_harvest", {})
        
        # Determine explicit bounds using fallback parameters matching system thresholds
        if target_type == "active":
            min_p = float(harvest_block.get("min_price", 50.0))
            max_p = float(harvest_block.get("max_price", 650.0))
        elif target_type == "broken":
            min_p = float(harvest_block.get("min_price_broken", 50.0))
            max_p = float(harvest_block.get("max_price_broken", 150.0))
        else:  # 'used'
            min_p = float(harvest_block.get("min_price_used", 115.0))
            max_p = float(harvest_block.get("max_price_used", 650.0))

        step = float(harvest_block.get("step_size", 10.0))
        
        brackets = []
        current = min_p
        while current < max_p:
            upper = min(current + step, max_p)
            brackets.append((current, upper))
            current += step
            
        return brackets

    def parse_active(self, raw_data: Dict[str, Any], target_model: str) -> Optional[ActiveMarketItem]:
        raw_title = raw_data.get("title", "")
        extracted_model = self.extract_model(raw_title)
        cleaned_title = self.clean_title(raw_title)

        if extracted_model != target_model.upper() or not self.is_valid_listing(cleaned_title, extracted_model):
            return None

        price = float(raw_data.get("price", 0.0))
        shipping = float(raw_data.get("shipping", 0.0))
        condition_id = int(raw_data.get("condition_id", 3000))

        return ActiveMarketItem(
            item_id=str(raw_data.get("item_id")),
            source_platform=raw_data.get("source_platform", "ebay"),
            model_name=extracted_model,
            category=self.category_name,
            raw_title=raw_title,
            title=cleaned_title,
            price=price,
            shipping_cost=shipping,
            total_cost=round(price + shipping, 2),
            condition_id=condition_id,
            seller_username=raw_data.get("seller_username"),
            feedback_score=raw_data.get("feedback_score"),
            feedback_percentage=raw_data.get("feedback_percentage"),
            is_top_rated=bool(raw_data.get("is_top_rated", False)),
            has_bent_pins="BENT" in raw_title.upper(),
            is_for_parts_or_not_working=(condition_id == 7000 or "PARTS" in raw_title.upper()),
            bid_count=int(raw_data.get("bid_count", 0)),
            quantity_available=int(raw_data.get("quantity_available", 1)),
            item_url=raw_data.get("item_url", ""),
            image_urls=raw_data.get("image_urls") if isinstance(raw_data.get("image_urls"), list) else []
        )

    def parse_historical(self, raw_data: Dict[str, Any], target_model: str) -> Optional[HistoricalMarketItem]:
        raw_title = raw_data.get("title", "")
        extracted_model = self.extract_model(raw_title)
        cleaned_title = self.clean_title(raw_title)

        if extracted_model != target_model.upper() or not self.is_valid_listing(cleaned_title, extracted_model):
            return None

        price = float(raw_data.get("price", 0.0))
        shipping = float(raw_data.get("shipping", 0.0))

        return HistoricalMarketItem(
            item_id=str(raw_data.get("item_id")),
            source_platform=raw_data.get("source_platform", "ebay"),
            model_name=extracted_model,
            category=self.category_name,
            raw_title=raw_title,
            title=cleaned_title,
            price=price,
            shipping_cost=shipping,
            total_cost=round(price + shipping, 2),
            condition_id=int(raw_data.get("condition_id", 3000)),
            is_sold=bool(raw_data.get("is_sold", True)),
            quantity_sold=int(raw_data.get("quantity_sold", 1)),
            bid_count=int(raw_data.get("bid_count", 0)),
            seller_username=raw_data.get("seller_username"),
            feedback_score=raw_data.get("feedback_score"),
            feedback_percentage=raw_data.get("feedback_percentage"),
            item_url=raw_data.get("item_url", "")
        )