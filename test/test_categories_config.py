import os
import yaml
import pytest
from pydantic import ValidationError
from src.analysis.schema.config_schema import StrategyRegistry

# Resolve path dynamically relative to this test file's location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "settings", "categories.yaml")

@pytest.fixture
def load_raw_yaml():
    """Ensures file exists and is valid YAML markup."""
    assert os.path.exists(CONFIG_PATH), f"Target strategy config missing at: {CONFIG_PATH}"
    with open(CONFIG_PATH, "r") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"YAML parser failed on file formatting: {e}")

def test_categories_yaml_adheres_to_schema_contract(load_raw_yaml):
    """Verifies all mandatory structural fields exist, match type requirements, and have values."""
    try:
        # Enforce strict validation via Pydantic schema parsing
        registry = StrategyRegistry.model_validate(load_raw_yaml)
        
        # Verify the target testing model boundary configuration
        cpu_config = registry.CPU
        assert any("5800X" in model for model in cpu_config.global_config.valid_models), "Testing model 5800X must be in valid_models array"
        
    except ValidationError as e:
        # Unpack structural failures explicitly so you can pinpoint what key got dropped
        error_summary = []
        for err in e.errors():
            loc_path = " -> ".join(str(loc) for loc in err["loc"])
            error_summary.append(f"[{loc_path}]: {err['msg']} (got: {err.get('input')})")
        
        error_msg = "\n".join(error_summary)
        pytest.fail(f"Configuration validation contract breached:\n{error_msg}")

def test_model_price_profiles_match_valid_variants(load_raw_yaml):
    """Ensures each base model in variant matrix has a matching pricing constraint profile."""
    registry = StrategyRegistry.model_validate(load_raw_yaml)
    profiles = registry.CPU.global_config.model_price_profiles
    variants = registry.CPU.global_config.model_variants
    
    for model_key in variants.keys():
        assert model_key in profiles, f"Model variant array macro '{model_key}' has no entry in model_price_profiles matrix!"
        
        # Guard against zero/negative mathematical bounds
        prof = profiles[model_key]
        assert prof.used_max > prof.used_min, f"[{model_key}]: used_max must be greater than used_min"
        assert prof.broken_max > prof.broken_min, f"[{model_key}]: broken_max must be greater than broken_min"
        assert prof.used_min >= prof.broken_max, f"[{model_key}]: Price overlap error! Used min floor should sit above your broken maximum ceiling."