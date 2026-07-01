# src/analysis/schema/config_schema.py

"""
Configuration Schema Module for the Bazaar Data Pipeline.

This module defines the strict Pydantic structural models used to validate 
the operational thresholds, keyword matching rules, strategy profiles, and 
pricing matrices defined in the system's runtime settings (e.g., categories.yaml).
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional

class PriceProfile(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    used_min: float
    used_max: float
    broken_min: float
    broken_max: float

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

class GlobalConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    search_format: str
    valid_models: List[str]
    model_price_profiles: Dict[str, PriceProfile]
    model_variants: Dict[str, List[str]]
    multisku_models: List[str]
    title_noise_words: List[str]
    local_noise_blacklist: List[str]
    api_blacklist_words: List[str]

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

class ActiveHarvestConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool
    limit_per_sweep: int
    min_price: float
    max_price: float
    step_size: float
    ebay_category_id: int
    ebay_condition: List[int]
    alternative_queries: List[str]
    pin_defect_keywords: List[str] = Field(default_factory=list)
    salvage_keywords: List[str]
    distress_keywords: List[str]
    functional_keywords: List[str]

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

class HistoricalHarvestConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool
    limit_per_sweep: int
    require_sold: bool
    step_size: float
    ebay_category_id: List[int]
    ebay_condition: List[int]
    use_profile_bounds: bool
    alternative_queries: List[str]

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

class CpuStrategyConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())
    
    strategy_class: str
    global_config: GlobalConfig = Field(..., alias="global")
    active_harvest: ActiveHarvestConfig
    historical_harvest: HistoricalHarvestConfig

    def get(self, key: str, default: Any = None) -> Any:
        """Enables seamless duck-typing for legacy config.get assertions."""
        return getattr(self, key, default)

class StrategyRegistry(BaseModel):
    """
    Root registration schema for configuration profiles.
    Maps high-level keys from categories.yaml natively into structural objects.
    """
    model_config = ConfigDict(protected_namespaces=())
    
    CPU: CpuStrategyConfig