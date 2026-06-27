import pytest
from src.api.ebay.providers.scrapeops_provider import ScrapeOpsProvider

@pytest.fixture
def valid_provider_cfg():
    """Returns a valid ScrapeOps target configuration block."""
    return {
        "api_key": "test_token_xyz123",
        "base_url": "https://proxy.scrapeops.io",
        "endpoint_path": "v1",
        "country": "us",
        "residential": True
    }

# ==============================================================================
# 1. Constructor Initialization & Signature Signature Integrity Tests
# ==============================================================================

def test_constructor_keyword_mapping_variants(valid_provider_cfg):
    """Verifies that both provider_cfg and legacy provider_config map cleanly."""
    # Test canonical keyword name
    p1 = ScrapeOpsProvider(provider_cfg=valid_provider_cfg)
    assert p1.provider_cfg["api_key"] == "test_token_xyz123"

    # Test legacy keyword variant fallback execution
    p2 = ScrapeOpsProvider(provider_config=valid_provider_cfg)
    assert p2.provider_cfg["api_key"] == "test_token_xyz123"


def test_constructor_positional_args_deduction(valid_provider_cfg):
    """Verifies internal type-deduction and fallback ordering rules when args are used."""
    mock_global_config = {"app_env": "production"}

    # Case A: Combined (global_config, provider_cfg) positional strategy
    p1 = ScrapeOpsProvider(mock_global_config, valid_provider_cfg)
    assert p1.config == mock_global_config
    assert p1.provider_cfg["api_key"] == "test_token_xyz123"

    # Case B: Single positional dictionary arriving containing an explicit key signature
    p2 = ScrapeOpsProvider(valid_provider_cfg)
    assert p2.provider_cfg["api_key"] == "test_token_xyz123"
    assert p2.config == {}  # Gracefully falls back to empty dictionary state


def test_constructor_malformed_type_resilience():
    """Enforces type conversion rules if config arguments are invalid objects or primitives."""
    class DummyConfigObject:
        def __init__(self):
            self.api_key = "object_extracted_token"

    # 1. Verify object __dict__ extraction now works flawlessly
    p_obj = ScrapeOpsProvider(provider_cfg=DummyConfigObject())
    assert isinstance(p_obj.provider_cfg, dict)
    assert p_obj.provider_cfg["api_key"] == "object_extracted_token"

    # 2. Verify non-object primitives still gracefully degrade to an empty dictionary
    p_prim = ScrapeOpsProvider(provider_cfg=12345)
    assert isinstance(p_prim.provider_cfg, dict)
    assert p_prim.provider_cfg == {}

# ==============================================================================
# 2. Engine Payload Translation Engine Tests
# ==============================================================================

def test_build_request_params_url_normalization(valid_provider_cfg):
    """Ensures base proxy URL formatting layout matches ScrapeOps rules."""
    # Strip explicit trailing slashes inside raw config blocks to check enforcement loop
    cfg = valid_provider_cfg.copy()
    cfg["base_url"] = "https://proxy.scrapeops.io"
    cfg["endpoint_path"] = "v1/"
    
    p = ScrapeOpsProvider(provider_cfg=cfg)
    req_url, _, _ = p.build_request_params("https://ebay.com")
    
    # Must enforce exactly one trailing separator signature
    assert req_url == "https://proxy.scrapeops.io/v1/"


def test_build_request_params_api_key_variations():
    """Asserts key stripping and fallback logic for alternate key signatures."""
    cfg = {"api-key": "   token_with_whitespace   "}
    p = ScrapeOpsProvider(provider_cfg=cfg)
    _, payload, _ = p.build_request_params("https://ebay.com")
    
    assert payload["api_key"] == "token_with_whitespace"


def test_build_request_params_js_rendering_states(valid_provider_cfg):
    """Validates fallback and explicit override rules for JS rendering selectors."""
    # Case A: Default fallbacks with no custom selectors specified
    p_default = ScrapeOpsProvider(provider_cfg=valid_provider_cfg)
    _, payload_default, _ = p_default.build_request_params("https://ebay.com")
    assert payload_default["render_js"] is False
    assert "wait_for_selector" not in payload_default

    # Case B: Custom wait trace element explicitly provided inside configuration block
    cfg_with_selector = valid_provider_cfg.copy()
    cfg_with_selector["wait_for_selector"] = "div.target-card"
    
    p_selector = ScrapeOpsProvider(provider_cfg=cfg_with_selector)
    _, payload_selector, _ = p_selector.build_request_params("https://ebay.com")
    assert payload_selector["render_js"] is True
    assert payload_selector["wait_for_selector"] == "div.target-card"


@pytest.mark.parametrize("bypass_input, expected_boolean", [
    ("true", True),
    ("FALSE", False),
    (True, True),
    (False, False),
    (1, True),
    (0, False),
])
def test_build_request_params_bypass_cache_evaluation(valid_provider_cfg, bypass_input, expected_boolean):
    """Validates conversion logic over dynamic primitive types for proxy cache directives."""
    cfg = valid_provider_cfg.copy()
    cfg["bypass_cache"] = bypass_input
    
    p = ScrapeOpsProvider(provider_cfg=cfg)
    _, payload, _ = p.build_request_params("https://ebay.com")
    assert payload["bypass_cache"] is expected_boolean