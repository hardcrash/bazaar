import pytest
from bs4 import BeautifulSoup
from src.api.ebay.scrape_parsers.msku import (
    extract_msku_metadata, 
    parse_msku_json, 
    parse_var_model_json, 
    parse_dom_sku_options
)
from src.core.models import MarketItem

# Mock MarketItem fixture
@pytest.fixture
def base_item():
    return MarketItem(
        item_id="123",
        model_name="TestModel",
        category="Tech",
        raw_title="Generic Product",
        title="Generic Product",
        price=10.0,
        shipping_cost=5.0,
        currency="USD",
        condition_id="1000",
        is_sold=False,
        item_url="https://ebay.com/itm/123",
        process_state="PENDING",
        data_grade="BRONZE"
    )

def test_extract_msku_metadata():
    html = '... "feedbackScore": 99, "positiveFeedbackPercent": 98.5 ... TOP-RATED SELLER ... BENT PIN ...'
    meta = extract_msku_metadata(html)
    assert meta["feedback_score"] == 99
    assert meta["feedback_percentage"] == 98.5
    assert meta["is_top_rated"] is True
    assert meta["has_bent_pins"] is True

def test_parse_msku_json(base_item):
    # Added quotes to keys and ensured strict JSON format
    json_part = '{"variationsMap": {"v1": {"price": 20.0}}, "menuItemMap": {"0": {"valueValue": "Red"}}, "variationCombinations": {"0": "v1"}}'
    html = '{"MSKU": {"variationsMap": {"v1": {"price": 20.0}}, "menuItemMap": {"0": {"valueValue": "Red"}}, "variationCombinations": {"0": "v1"}}}'
    
    records = parse_msku_json(html, base_item)
    assert len(records) == 1

def test_parse_msku_json(base_item):
    # Added quotes to keys and ensured strict JSON format
    json_part = '{"variationsMap": {"v1": {"price": 20.0}}, "menuItemMap": {"0": {"valueValue": "Red"}}, "variationCombinations": {"0": "v1"}}'
    html = f'"MSKU": {json_part}' 
    
    records = parse_msku_json(html, base_item)
    assert len(records) == 1

def test_parse_var_model_json(base_item):
    # Added quotes to ItemJson key
    json_part = '{"menuItemMap": {"m1": {"text": "Blue", "price": "25.00"}}}'
    html = f'"ItemJson": {json_part}'
    
    records = parse_var_model_json(html, base_item)
    assert len(records) == 1

def test_parse_dom_sku_options(base_item):
    html = '<div class="listbox__option" data-sku-value-name="Green"></div>'
    soup = BeautifulSoup(html, "html.parser")
    
    records = parse_dom_sku_options(soup, base_item)
    assert len(records) == 1
    assert "Green" in records[0].title
    assert records[0].price == 10.0  # Should inherit base_item price