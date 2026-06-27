import pytest
from src.api.ebay.scrape_parsers.metrics import sanitize_title_noise

def test_sanitize_title_noise_basics():
    # Test global noise removal
    raw = "New Listing Vintage Camera Opens in a new window or tab"
    expected = "Vintage Camera"
    assert sanitize_title_noise(raw) == expected

def test_sanitize_title_noise_case_insensitive():
    # Test that it handles mixed case
    raw = "new listing VINTAGE CAMERA sponsored"
    expected = "VINTAGE CAMERA"
    assert sanitize_title_noise(raw) == expected

def test_sanitize_title_noise_with_custom_blacklist():
    # Test custom injection + global noise
    raw = "New Listing Sony TV 55-inch [REFURBISHED]"
    blacklist = ["[REFURBISHED]"]
    expected = "Sony TV 55-inch"
    assert sanitize_title_noise(raw, custom_blacklist=blacklist) == expected

def test_sanitize_title_noise_ordering():
    # Test that longer phrases are stripped before shorter ones
    raw = "New Listing New List Item"
    
    # We must explicitly provide the blacklist to strip both terms
    blacklist = ["New Listing", "New List"]
    
    expected = "Item"
    assert sanitize_title_noise(raw, custom_blacklist=blacklist) == expected

@pytest.mark.parametrize("input_text, expected", [
    ("   Spaces are trimmed   ", "Spaces are trimmed"),
    ("NoNoiseHere", "NoNoiseHere"),
    ("", ""),
])
def test_sanitize_title_noise_edge_cases(input_text, expected):
    assert sanitize_title_noise(input_text) == expected