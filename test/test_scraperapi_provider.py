import pytest
from src.api.ebay.providers.scraperapi_provider import ScraperApiProvider


@pytest.fixture
def valid_scraper_cfg():
    return {
        "api_key": "scraper_token_123",
        "base_url": "http://api.scraperapi.com",
        "country_code": "us",
    }


def test_scraperapi_constructor_deduction(valid_scraper_cfg):
    """Verifies that positional argument deduction handles config maps correctly."""
    mock_global = {"app_env": "testing"}
    provider = ScraperApiProvider(mock_global, valid_scraper_cfg)

    assert provider.config == mock_global
    assert provider.provider_cfg["api_key"] == "scraper_token_123"


def test_scraperapi_build_request_params_defaults(valid_scraper_cfg):
    """Verifies default parameter payloads, unquoting, and default base urls."""
    provider = ScraperApiProvider(valid_scraper_cfg)
    target = "https://www.ebay.com/sch/i.html?_nkw=test%20item"

    url, payload, headers = provider.build_request_params(target)

    assert url == "http://api.scraperapi.com"
    assert headers == {}
    assert payload["api_key"] == "scraper_token_123"
    # Target should be unquoted
    assert payload["url"] == "https://www.ebay.com/sch/i.html?_nkw=test item"
    assert payload["premium"] == "true"
    assert payload["skip_cache"] == "true"
    assert payload["keep_headers"] == "false"
    assert payload["country_code"] == "us"
    assert "session_number" not in payload


def test_scraperapi_fallbacks_and_normalization():
    """Verifies robust field mapping transformations for alternative config names."""
    cfg = {
        "api_key": "token_abc",
        "country": "UK",  # Should map to country_code and lowercase
        "session_id": 9999,  # Should map to session_number as string
    }
    provider = ScraperApiProvider(cfg)
    _, payload, _ = provider.build_request_params("https://example.com")

    assert payload["country_code"] == "uk"
    assert payload["session_number"] == "9999"


def test_scraperapi_missing_api_key_raises_error():
    """Ensures build_request_params fails early if an API key is completely absent."""
    invalid_cfg = {"base_url": "http://api.scraperapi.com", "country": "us"}
    provider = ScraperApiProvider(invalid_cfg)

    with pytest.raises(
        ValueError, match="ScraperApiProvider missing required 'api_key'"
    ):
        provider.build_request_params("https://example.com")