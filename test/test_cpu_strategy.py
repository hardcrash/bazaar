# test/test_cpu_strategy.py
"""
Bazaar Strategy Suite Unit Tests

Validates raw title cleaning pipelines, multi-variant keyword blacklisting,
regex model isolation boundaries, and property metadata hydration.
"""

import pytest
from src.analysis.strategy.cpu_strategy import CPUStrategy
from src.analysis.schema.config_schema import CpuStrategyConfig


@pytest.fixture
def mock_global_yaml():
    """
    Matches the exact structured nested dictionary layer parsed out of 
    settings/categories.yaml, complete with unified parsing keys.
    """
    return {
        "strategy_class": "CpuStrategy",
        "valid_models": ["5800X", "5950X"],
        "model_variants": {
            "5950X": ["5950X"],
            "5800X": ["5800X", "5800X3D", "5800XT", "5800"]
        },
        "multisku_models": ["5600X", "5700X", "5800X", "5900X", "5950X"],
        "brands": ["AMD"],
        "patterns": [r"RYZEN(?:\s+[579])?\s+(5\d{3}(?:X3D|X|G|GE|XT)?)\b"],
        "title_noise_words": ["L@@K", "MINT"],
        "local_noise_blacklist": ["BUNDLE", "LAPTOP", "PC", "SYSTEM", "MOBO COMBO"],
        "search_format": "Ryzen {model}",
        "active_harvest": {
            "ebay_category_id": 164,
            "max_price": 650.0,
            "salvage_keywords": ["BENT PINS", "PARTS ONLY", "FOR PARTS"],
            # Strategy expects 'pin_defect_keywords' instead of markers
            "pin_defect_keywords": ["BENT PINS", "BENT PIN"] 
        },
        "historical_harvest": {
            "min_price_used": 110.00,
            "max_price_used": 650.00,
            "step_size": 10.00,
            "ebay_category_id": 164
        }
    }


@pytest.fixture
def cpu_strategy(mock_global_yaml):
    """Provides a single unified strategy execution engine instance."""
    return CPUStrategy(category_name="CPU", yaml_config=mock_global_yaml)


# ==================== Core Extraction & Text Tests ====================

def test_clean_title(cpu_strategy):
    """Verifies standard layout padding and noise tokens are cleanly removed."""
    raw_title = "   L@@K AMD Ryzen 7 5800X Processor MINT   "
    assert cpu_strategy.clean_title(raw_title) == "AMD RYZEN 7 5800X PROCESSOR"


def test_is_valid_standalone(cpu_strategy):
    """Verifies target hardware matching logic validates salvage assets."""
    # Under the active broken parts strategy, a completely clean asset is now invalid
    assert cpu_strategy.is_valid_listing("AMD RYZEN 7 5800X PROCESSOR", "5800X") is False
    # A listing must contain an explicit pin-defect keyword to pass validation
    assert cpu_strategy.is_valid_listing("AMD RYZEN 7 5800X PROCESSOR - BENT PINS", "5800X") is True


def test_is_valid_blacklist_drop(cpu_strategy):
    """Verifies that items containing local_noise_blacklist items are dropped flat."""
    assert cpu_strategy.is_valid_listing("AMD RYZEN 7 5800X BUNDLE WITH COOLER", "5800X") is False


def test_extract_model_cross_bleed(cpu_strategy):
    """Ensures parser isolates specific token values, avoiding layout cross-bleed."""
    title = "[MSKU VARIANT] RYZEN 9 3950X"
    assert cpu_strategy.extract_model(title) == "UNKNOWN"


# ==================== Configuration Hydration Tests ====================

def test_strategy_extracts_nested_harvest_pricing_metrics(mock_global_yaml, cpu_strategy):
    """Ensures configuration blocks map cleanly to strategy attributes."""
    assert "BUNDLE" in cpu_strategy.blacklist
    assert cpu_strategy.config.get("active_harvest", {}).get("ebay_category_id") == 164

@pytest.fixture
def pydantic_cpu_config():
    """
    Simulates the exact Pydantic schema architecture hydrated by the factory.
    Tests dynamic attribute routing and complex dot-notation lookups.
    """
    raw_yaml_matrix = {
        "strategy_class": "CpuStrategy",
        "global": {
            "search_format": "Ryzen {model}",
            "valid_models": ["5800X", "5950X"],
            "model_price_profiles": {
                "5800X": {
                    "used_min": 120.0,
                    "used_max": 200.0,
                    "broken_min": 30.0,
                    "broken_max": 75.0
                },
                "5950X": {
                    "used_min": 250.0,
                    "used_max": 400.0,
                    "broken_min": 60.0,
                    "broken_max": 150.0
                }
            },
            "model_variants": {
                "5950X": ["5950X"],
                "5800X": ["5800X", "5800X3D"]
            },
            "multisku_models": ["5600X", "5800X"],
            "title_noise_words": ["L@@K"],
            "local_noise_blacklist": ["BUNDLE"],
            "api_blacklist_words": ["PIN"]
        },
        "active_harvest": {
            "enabled": True,
            "limit_per_sweep": 100,
            "min_price": 40.0,
            "max_price": 700.0,
            "step_size": 25.0,
            "ebay_category_id": 164,
            "ebay_condition": [3000, 4000, 7000],
            "alternative_queries": [],
            "salvage_keywords": ["BENT PINS", "PARTS ONLY", "FOR PARTS"],
            # Key renamed here to fulfill getattr lookup pattern inside your CPUStrategy constructor
            "pin_defect_keywords": ["BENT PINS", "BENT PIN"],
            "distress_keywords": ["UNTESTED", "AS IS"],
            "functional_keywords": ["WORKING", "TESTED"]
        },
        "historical_harvest": {
            "enabled": True,
            "limit_per_sweep": 200,
            "require_sold": True,
            "step_size": 10.0,
            "ebay_category_id": [164],
            "ebay_condition": [3000, 4000],
            "use_profile_bounds": True,
            "alternative_queries": []
        }
    }
    return CpuStrategyConfig.model_validate(raw_yaml_matrix)


@pytest.fixture
def typed_cpu_strategy(pydantic_cpu_config):
    """Provides a processing strategy context bound with true typed data."""
    return CPUStrategy(category_name="CPU", yaml_config=pydantic_cpu_config)


# ==================== Strongly-Typed Contract Behavior ====================

def test_pydantic_config_initialization(typed_cpu_strategy):
    """Ensures strategy resolves parameters cleanly out of nested Pydantic trees."""
    assert typed_cpu_strategy.is_strongly_typed is True
    assert "5800X" in typed_cpu_strategy.valid_models
    assert typed_cpu_strategy.search_format == "Ryzen {model}"
    assert "BENT PINS" in typed_cpu_strategy.salvage_keywords


def test_is_valid_listing_with_conditions(typed_cpu_strategy):
    """Verifies numeric conditional rules filter listings properly in modern mode."""
    # Must use a pin-defect keyword to satisfy active validation strategy rules
    assert typed_cpu_strategy.is_valid_listing("AMD RYZEN 7 5800X - BENT PINS", "5800X", condition_id=7000) is True
    assert typed_cpu_strategy.is_valid_listing("AMD RYZEN 7 5800X - BENT PINS", "5800X", condition_id=5000) is False


# ==================== Dynamic Price Bracket Chunks ====================

def test_get_price_brackets_fallback_active(typed_cpu_strategy):
    """Validates global active price window segmentation limits."""
    brackets = typed_cpu_strategy.get_price_brackets(target_type="active")
    # Active range 40.0 to 700.0 with step 25.0
    assert brackets[0] == (40.0, 65.0)
    assert brackets[-1] == (690.0, 700.0)


def test_get_price_brackets_by_model_profile(typed_cpu_strategy):
    """Verifies that individual chip definitions load isolated bracket sizes."""
    # 5800X Used limits: 120.0 to 200.0, historical step 10.0
    brackets_5800x = typed_cpu_strategy.get_price_brackets(target_type="used", target_model="5800X")
    assert brackets_5800x[0] == (120.0, 130.0)
    assert brackets_5800x[-1] == (190.0, 200.0)

    # 5950X Broken limits: 60.0 to 150.0, historical step 10.0
    brackets_5950x = typed_cpu_strategy.get_price_brackets(target_type="broken", target_model="5950X")
    assert brackets_5950x[0] == (60.0, 70.0)
    assert brackets_5950x[-1] == (140.0, 150.0)


def test_get_price_brackets_unknown_profile_fallback(typed_cpu_strategy):
    """Guards against unprofiled models gracefully falling back to safe defaults."""
    brackets = typed_cpu_strategy.get_price_brackets(target_type="used", target_model="NOT_FOUND")
    # Emergency fallback bounds: 50.0 to 300.0
    assert brackets[0] == (50.0, 60.0)


# ==================== Intent Classification / Parsing ====================

def test_triage_listing_intent(typed_cpu_strategy):
    """Ensures listing keyword flags sort listings into appropriate pipelines."""
    # Because pin_defect keyword logic is checked first in triage_listing_intent, 
    # titles containing "BENT PINS" immediately evaluate to SALVAGE_CONFIRMED.
    assert typed_cpu_strategy.triage_listing_intent("5800X WITH BENT PINS AS IS") == "SALVAGE_CONFIRMED"
    
    # Generic broken keywords that don't have a specific pin marker drop down to REQUIRES_DEEP_SCRAPE
    assert typed_cpu_strategy.triage_listing_intent("UNTESTED RYZEN 9 5950X") == "REQUIRES_DEEP_SCRAPE"
    
    # Clean/unmarked listings report as pending classification
    assert typed_cpu_strategy.triage_listing_intent("SEALED AMD RYZEN 7 5800X") == "PENDING_CLASSIFICATION"


def test_parse_active_hydrates_flags(typed_cpu_strategy):
    """Ensures custom fields like bent pins map accurately onto model attributes."""
    raw_payload = {
        "item_id": "998877",
        "title": "AMD Ryzen 7 5800X CPU - Bent Pins",
        "price": "80.00",
        "shipping": "5.50",
        "condition_id": 7000
    }
    item = typed_cpu_strategy.parse_active(raw_payload, target_model="5800X")
    
    assert item is not None
    assert item.has_bent_pins is True
    assert item.is_for_parts_or_not_working is True
    assert item.total_cost == 85.50