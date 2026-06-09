import re
from src.analysis.strategy.base_strategy import BaseStrategy

class CPUStrategy(BaseStrategy):
    def __init__(self, config_dict: dict):
        """
        Initializes the CPU Strategy as the single source of truth for configuration,
        parsing filters, and bounding criteria derived from categories.yaml.
        """
        super().__init__(config_dict)

        # ----------------------------------------------------------------------
        # 1. CORE SEARCH ATTRIBUTES & PATTERNS
        # ----------------------------------------------------------------------
        self.valid_models = config_dict.get("valid_models", ["5800X"])
        # 🌟 Safely bind the multi-sku list with a resilient hardcoded fallback pool
        self.multisku_models = config_dict.get("multisku_models", ["5600X", "5700X", "5700X3D", "5800X", "5800X3D", "5900X", "5950X"])
        self.brands = config_dict.get("brands", ["AMD"])
        self.search_format = config_dict.get("search_format", "Ryzen {model}")
        self.defect_queries = config_dict.get("defect_queries", [])

        # Compile regex rules natively from configuration
        yaml_patterns = config_dict.get("patterns", [])
        if yaml_patterns:
            combined_pattern = "|".join(yaml_patterns)
            self.model_pattern = re.compile(combined_pattern, re.IGNORECASE)
        else:
            self.model_pattern = re.compile(r'RYZEN(?:\s+[579])?\s+(5\d{3}(?:X3D|X|G|GE|XT)?)\b', re.IGNORECASE)

        # ----------------------------------------------------------------------
        # 2. STRING BLACKLISTS & FILTER MATRICES
        # ----------------------------------------------------------------------
        self.noise_words = config_dict.get("noise_words", ["DDR4", "DDR5", "CPU", "SOCKET"])
        self.blacklist_words = config_dict.get("blacklist_words", [])
        self.local_noise_blacklist = config_dict.get("local_noise_blacklist", [])

        # ----------------------------------------------------------------------
        # 3. HARVEST PIPELINE PARAMETERS (ACTIVE & HISTORICAL)
        # ----------------------------------------------------------------------
        active_cfg = config_dict.get("active_harvest", {})
        self.active_enabled = active_cfg.get("enabled", True)
        self.active_limit = int(active_cfg.get("limit_per_sweep", 200))
        self.active_min_price = float(active_cfg.get("min_price", 50.0))
        self.active_max_price = float(active_cfg.get("max_price", 250.0))
        self.active_step_size = float(active_cfg.get("step_size", 10.0))
        self.active_category_id = str(active_cfg.get("ebay_category_id", "164"))
        self.active_conditions = active_cfg.get("ebay_condition", [7000])

        hist_cfg = config_dict.get("historical_harvest", {})
        self.hist_enabled = hist_cfg.get("enabled", True)
        self.hist_lookback_days = int(hist_cfg.get("lookback_days", 365))
        self.hist_limit = int(hist_cfg.get("limit_per_sweep", 2000))
        self.hist_require_sold = hist_cfg.get("require_sold", True)
        self.hist_step_size = float(hist_cfg.get("step_size", 10.0))
        self.hist_min_price_broken = float(hist_cfg.get("min_price_broken", 50.0))
        self.hist_max_price_broken = float(hist_cfg.get("max_price_broken", 250.0))
        self.hist_min_price_used = float(hist_cfg.get("min_price_used", 115.0))
        self.hist_max_price_used = float(hist_cfg.get("max_price_used", 120.0))
        self.hist_category_id = str(hist_cfg.get("ebay_category_id", "164"))
        self.hist_conditions = hist_cfg.get("ebay_condition", [2000, 3000, 7000])

    def is_valid(self, title: str, target_model: str) -> str:
        """
        Evaluates a cleaned marketplace title against internal configuration rules.
        Returns: 'VALID', 'MSKU', or 'INVALID'
        """
        title_upper = title.upper()
        target_upper = target_model.upper()

        # 1. Global Exclusions
        if any(word.upper() in title_upper for word in self.blacklist_words):
            return "INVALID"

        # 2. Local Engine Noise Array Filter Pass
        if any(term.upper() in title_upper for term in self.local_noise_blacklist):
            return "INVALID"

        if any(term in title_upper for term in ["COMBO", "MOBO", "KIT", "BUNDLE"]):
            return "INVALID"

        # 3. CRITICAL: Multi-Sku Variation Dropdown Detection
        # 🌟 Dynamically loops over the configured multisku_models instead of a hardcoded array
        models_found = [m for m in self.multisku_models if m.upper() in title_upper]
        if len(models_found) >= 2:
            return "MSKU"

        # 4. Strict Model Cross-Bleed Isolation
        extracted = self.extract_model(title_upper, target_upper)
        if extracted != target_upper:
            return "INVALID"

        return "VALID"

    def clean_title(self, title: str) -> str:
        cleaned = title.replace("New Listing", "")
        cleaned = cleaned.split("Opens in a new window")[0]

        for word in self.noise_words:
            cleaned = re.sub(r'\b' + re.escape(word) + r'\b', '', cleaned, flags=re.IGNORECASE)

        return re.sub(r'\s+', ' ', cleaned).strip()

    def extract_model(self, title_upper: str, target_upper: str) -> str:
        if "5800X3D" in title_upper:
            return "5800X3D"
        if "5700X3D" in title_upper:
            return "5700X3D"

        if re.search(r'\b' + re.escape(target_upper) + r'\b', title_upper):
            return target_upper

        match = self.model_pattern.search(title_upper)
        if match:
            matched_str = match.group(1) if match.lastindex and match.group(1) else match.group(0)
            return matched_str.upper().strip()

        return "UNKNOWN"
