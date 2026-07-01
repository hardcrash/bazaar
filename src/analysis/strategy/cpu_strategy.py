"""
Bazaar Concrete CPU Processing Strategy
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger
from src.analysis.strategy.base_category_strategy import BaseCategoryStrategy
from src.core.models import ActiveMarketItem, HistoricalMarketItem


class CPUStrategy(BaseCategoryStrategy):
    def __init__(self, category_name: str, yaml_config: Any):
        super().__init__(category_name, yaml_config)
        
        # 1. Structural extraction and dynamic heuristics from unified properties
        if self.is_strongly_typed:
            g_cfg = self.config.global_config
            a_cfg = self.config.active_harvest
            
            self.noise_words = g_cfg.title_noise_words
            self.blacklist = g_cfg.local_noise_blacklist
            self.multisku_models = g_cfg.multisku_models
            
            # Hydrate explicit target domain properties from config schema
            self.pin_defect_keywords = [kw.upper() for kw in getattr(a_cfg, "pin_defect_keywords", [])]
            self.salvage_keywords = [kw.upper() for kw in a_cfg.salvage_keywords]
            self.distress_keywords = [kw.upper() for kw in a_cfg.distress_keywords]
            self.functional_keywords = [kw.upper() for kw in a_cfg.functional_keywords]
            
            raw_variants = g_cfg.model_variants
            raw_patterns = [] 
        else:
            self.noise_words = self.config.get("title_noise_words", [])
            self.blacklist = self.config.get("local_noise_blacklist", [])
            self.multisku_models = self.config.get("multisku_models", [])
            
            # Fallback legacy dictionary handling to preserve safety boundaries
            active_block = self.config.get("active_harvest", {})
            self.pin_defect_keywords = [kw.upper() for kw in active_block.get("pin_defect_keywords", [])]
            self.salvage_keywords = [kw.upper() for kw in active_block.get("salvage_keywords", [])]
            self.distress_keywords = [kw.upper() for kw in active_block.get("distress_keywords", [])]
            self.functional_keywords = [kw.upper() for kw in active_block.get("functional_keywords", [])]
            
            raw_variants = self.config.get("model_variants", {})
            raw_patterns = self.config.get("patterns", [])

        # 2. Extract and pre-compile regular expressions for core processing
        if raw_patterns:
            self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in raw_patterns]
        else:
            self.compiled_patterns = [
                re.compile(r'RYZEN(?:\s+[579])?\s+(5\d{3}(?:X3D|X|G|GE|XT)?)\b', re.IGNORECASE)
            ]

        # Pre-compile structural inverse variations for pin matching
        # Examples handled: "pins are bent", "pins missing"
        self.inverse_pin_regex = re.compile(
            r'\bPIN(S)?\s+(IS|ARE|LOOKS|HAS|HAVE)?\s*(BENT|MISSING|BROKEN|SNAPPED|DAMAGED)\b',
            re.IGNORECASE
        )

        # 3. Handle model variant substitutions with soft whitespace resilience
        self.variant_regexes = {}
        for target, variants in raw_variants.items() if self.is_strongly_typed else raw_variants.items():
            target_canonical = target.replace(" ", "").upper()
            compiled_list = []
            for v in variants:
                pattern = r"\s*".join(re.escape(char) for char in v)
                pattern = r"\b" + pattern + r"\b"
                compiled_list.append((v, re.compile(pattern, re.IGNORECASE)))
            self.variant_regexes[target_canonical] = compiled_list

    def clean_title(self, raw_title: str) -> str:
        cleaned = raw_title.upper()
        cleaned = cleaned.replace("NEW LISTING", "")
        cleaned = cleaned.split("OPENS IN A NEW WINDOW")[0]
        
        for word in self.noise_words:
            cleaned = re.sub(r'\b' + re.escape(word.upper()) + r'\b', '', cleaned)
            
        return re.sub(r'\s+', ' ', cleaned).strip()

    def extract_model(self, raw_title: str) -> str:
        title_upper = raw_title.upper()

        for target_canonical, compiled_list in self.variant_regexes.items():
            for original_name, regex in compiled_list:
                if regex.search(title_upper):
                    return original_name.upper()

        for pattern in self.compiled_patterns:
            match = pattern.search(title_upper)
            if match:
                matched_str = match.group(1) if match.lastindex and match.group(1) else match.group(0)
                return matched_str.upper().replace(" ", "")
                
        return "UNKNOWN"

    def is_valid_listing(self, cleaned_title: str, extracted_model: str, condition_id: Optional[int] = None) -> bool:   
        title_upper = cleaned_title.upper()

        if extracted_model not in self.valid_models:
            return False

        if any(bad_word.upper() in title_upper for bad_word in self.blacklist):
            logger.debug(f"Disqualified unrepairable or blacklisted candidate: {cleaned_title}")
            return False

        # Condition checks
        if self.is_strongly_typed:
            allowed_conditions = self.config.active_harvest.ebay_condition
        else:
            allowed_conditions = self.config.get("active_harvest", {}).get("condition_id", [])
            
        if allowed_conditions and condition_id is not None:
            if condition_id not in allowed_conditions:
                return False

        # Structural Filter Audit: Enforce explicit confirmation of mechanical pin defects
        has_direct_pin_issue = any(kw in title_upper for kw in self.pin_defect_keywords)
        has_inverse_pin_issue = bool(self.inverse_pin_regex.search(title_upper))
        
        if not (has_direct_pin_issue or has_inverse_pin_issue):
            logger.debug(f"Disqualified listing - lack of pin-defect markers: {cleaned_title}")
            return False

        # Filter out multi-sku mixed inventory packages unless designated as salvage
        has_salvage_context = any(kw in title_upper for kw in self.salvage_keywords)
        has_distress_context = any(kw in title_upper for kw in self.distress_keywords)

        models_found = [m for m in self.multisku_models if m.upper() in title_upper]
        if len(models_found) >= 2:
            if has_salvage_context or has_distress_context:
                return True
            return False

        return True

    def get_price_brackets(self, target_type: str = "used", target_model: Optional[str] = None) -> List[Tuple[float, float]]:
        brackets = []
        
        if not self.is_strongly_typed or target_type == "active" or not target_model:
            harvest_block = self.config.get("historical_harvest" if target_type != "active" else "active_harvest", {}) if not self.is_strongly_typed else (self.config.historical_harvest if target_type != "active" else self.config.active_harvest)
            
            if self.is_strongly_typed:
                min_p = float(harvest_block.min_price)
                max_p = float(harvest_block.max_price)
                step = float(harvest_block.step_size)
            else:
                if target_type == "active":
                    min_p = float(harvest_block.get("min_price", 50.0))
                    max_p = float(harvest_block.get("max_price", 650.0))
                elif target_type == "broken":
                    min_p = float(harvest_block.get("min_price_broken", 50.0))
                    max_p = float(harvest_block.get("max_price_broken", 150.0))
                else:
                    min_p = float(harvest_block.get("min_price_used", 115.0))
                    max_p = float(harvest_block.get("max_price_used", 650.0))
                step = float(harvest_block.get("step_size", 10.0))
        
        else:
            canonical_model = target_model.upper().replace(" ", "")
            profiles = self.config.global_config.model_price_profiles
            step = float(self.config.historical_harvest.step_size)
            
            if canonical_model in profiles:
                profile = profiles[canonical_model]
                if target_type == "broken":
                    min_p = float(profile.broken_min)
                    max_p = float(profile.broken_max)
                else:
                    min_p = float(profile.used_min)
                    max_p = float(profile.used_max)
            else:
                min_p = 50.0
                max_p = 300.0

        current = min_p
        while current < max_p:
            upper = min(current + step, max_p)
            brackets.append((current, upper))
            current += step
            
        return brackets
    
    def triage_listing_intent(self, raw_title: str) -> str:
        title_upper = raw_title.upper()
        if any(kw in title_upper for kw in self.pin_defect_keywords):
            return "SALVAGE_CONFIRMED"
        if any(kw in title_upper for kw in self.distress_keywords):
            return "REQUIRES_DEEP_SCRAPE"
        return "PENDING_CLASSIFICATION"

    def parse_active(self, raw_data: Dict[str, Any], target_model: str) -> Optional[ActiveMarketItem]:
        raw_title = raw_data.get("title", "")
        extracted_model = self.extract_model(raw_title)
        cleaned_title = self.clean_title(raw_title)

        if extracted_model != target_model.upper() or not self.is_valid_listing(cleaned_title, extracted_model, condition_id=raw_data.get("condition_id")):
            return None

        price = float(raw_data.get("price", 0.0))
        shipping = float(raw_data.get("shipping", 0.0))
        condition_id = int(raw_data.get("condition_id", 3000))
        
        title_upper = raw_title.upper()
        
        # Exact flag resolution mapping to domain configurations
        has_direct_pin = any(kw in title_upper for kw in self.pin_defect_keywords)
        has_inverse_pin = bool(self.inverse_pin_regex.search(title_upper))
        has_pins_flag = has_direct_pin or has_inverse_pin

        has_explicit_salvage = any(kw in title_upper for kw in self.salvage_keywords)

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
            has_bent_pins=has_pins_flag,
            is_for_parts_or_not_working=(condition_id == 7000 or has_explicit_salvage),
            bid_count=int(raw_data.get("bid_count", 0)),
            quantity_available=int(raw_data.get("quantity_available", 1)),
            item_url=raw_data.get("item_url", ""),
            image_urls=raw_data.get("image_urls") if isinstance(raw_data.get("image_urls"), list) else []
        )
    
    def parse_historical(self, raw_data: Dict[str, Any], target_model: str) -> Optional[HistoricalMarketItem]:
        raw_title = raw_data.get("title", "")
        extracted_model = self.extract_model(raw_title)
        cleaned_title = self.clean_title(raw_title)

        if extracted_model != target_model.upper() or not self.is_valid_listing(cleaned_title, extracted_model, condition_id=raw_data.get("condition_id")):
            return None

        price = float(raw_data.get("price", 0.0))
        shipping = float(raw_data.get("shipping", 0.0))
        condition_id = int(raw_data.get("condition_id", 3000))

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
            condition_id=condition_id,
            is_sold=bool(raw_data.get("is_sold", True)),
            quantity_sold=int(raw_data.get("quantity_sold", 1)),
            bid_count=int(raw_data.get("bid_count", 0)),
            seller_username=raw_data.get("seller_username"),
            feedback_score=raw_data.get("feedback_score"),
            feedback_percentage=raw_data.get("feedback_percentage"),
            item_url=raw_data.get("item_url", "")
        )