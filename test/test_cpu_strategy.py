import pytest
from src.analysis.strategy.cpu_strategy import CPUStrategy

@pytest.fixture
def cpu_strategy():
    config_dict = {
        "valid_models": ["5800X", "5950X"],
        "blacklist_words": ["bundle", "laptop", "pc", "system"],
        "search_format": "Ryzen {model}",
        "historical_harvest": {
            "min_price_used": 110.00,
            "max_price_used": 650.00,
            "step_size": 10.00,
            "ebay_category_id": "164"
        }
    }
    return CPUStrategy(config_dict=config_dict)

def test_clean_title(cpu_strategy):
    raw_title = "  AMD Ryzen 7 5800X Processor  "
    assert cpu_strategy.clean_title(raw_title) == "AMD Ryzen 7 5800X Processor"

def test_is_valid_standalone(cpu_strategy):
    # Standard valid item
    assert cpu_strategy.is_valid("AMD Ryzen 7 5800X Processor", "5800X") == "VALID"

def test_is_valid_blacklist_drop(cpu_strategy):
    # Should be rejected due to blacklisted word 'bundle'
    assert cpu_strategy.is_valid("AMD Ryzen 7 5800X BUNDLE with Cooler", "5800X") == "INVALID"

def test_extract_model_cross_bleed(cpu_strategy):
    # Ensure it doesn't cross-bleed variations
    title = "[MSKU VARIANT] RYZEN 9 3950X"
    assert cpu_strategy.extract_model(title, "5800X") != "5800X"
