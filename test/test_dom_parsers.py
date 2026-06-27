import pytest
from bs4 import BeautifulSoup
from src.api.ebay.scrape_parsers.dom import (
    should_skip_title,
    bubble_to_container_root,
    is_valid_listing,
    harvest_item_identifiers
)

def test_should_skip_title():
    # Test empty or None
    assert should_skip_title(None) == (True, "no_title")
    assert should_skip_title("") == (True, "no_title")
    # Test ad
    assert should_skip_title("Shop on eBay for great deals") == (True, "shop_on")
    # Test valid
    assert should_skip_title("Intel Core i9 Processor") == (False, None)

def test_bubble_to_container_root():
    html = '<li class="s-item"><div><span class="target">Child</span></div></li>'
    soup = BeautifulSoup(html, "html.parser")
    target = soup.select_one(".target")
    
    root = bubble_to_container_root(target)
    assert root.name == 'li'
    assert 's-item' in root.get('class')

def test_is_valid_listing():
    # Test sponsored/ad filtering
    html_ad = '<li class="s-item"><span class="s-item__sponsored-label">SPONSORED</span></li>'
    soup_ad = BeautifulSoup(html_ad, "html.parser")
    assert is_valid_listing(soup_ad.li) is False
    
    # Test valid item
    html_valid = '<li class="s-item"><span>Product Name</span></li>'
    soup_valid = BeautifulSoup(html_valid, "html.parser")
    assert is_valid_listing(soup_valid.li) is True

def test_harvest_item_identifiers():
    # Test extracting from data-id
    html = '<div data-itemid="12345"><a href="https://ebay.com/itm/12345">Link</a></div>'
    soup = BeautifulSoup(html, "html.parser")
    item_id, url = harvest_item_identifiers(soup.div, [])
    assert item_id == "12345"
    assert "https://ebay.com/itm/12345" in url

    # Test fallback extraction from URL string
    html_fallback = '<div><a href="https://ebay.com/itm/98765?hash=123">Link</a></div>'
    soup_fallback = BeautifulSoup(html_fallback, "html.parser")
    item_id, url = harvest_item_identifiers(soup_fallback.div, [])
    assert item_id == "98765"
    assert url == "https://ebay.com/itm/98765"