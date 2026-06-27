# src/api/ebay/scrape_parsers/msku.py
"""
Multi-SKU (MSKU) Variation Parsing Utilities for eBay.

This module provides functional logic to decompose complex eBay multi-variation listings,
extracting product variants, pricing adjustments, and seller-level metadata from 
raw JSON payloads and DOM structures.
"""

import re
import json
import logging
from bs4 import Tag, BeautifulSoup
from typing import List, Optional
from src.core.models import MarketItem  

logger = logging.getLogger(__name__)

def extract_msku_metadata(html_content: str) -> dict:
    """Extracts shared seller/listing metadata from the raw HTML."""
    html_upper = html_content.upper()
    return {
        "feedback_score": int(m.group(1)) if (m := re.search(r'feedbackScore"\s*:\s*(\d+)', html_content)) else None,
        "feedback_percentage": float(m.group(1)) if (m := re.search(r'positiveFeedbackPercent"\s*:\s*([\d\.]+)', html_content)) else None,
        "is_top_rated": "TOP-RATED SELLER" in html_upper or "TOP_RATED_SELLER" in html_upper,
        "has_bent_pins": any(x in html_upper for x in ["BENT PIN", "BROKEN PIN", "DAMAGED PIN", "MISSING PIN"])
    }

def parse_msku_json(html_content: str, base_item: MarketItem) -> List[MarketItem]:
    """Parses the primary MSKU JSON engine."""
    msku_match = re.search(r'"MSKU"\s*:\s*({.+?}),\s*"(?:QUANTITY|[A-Za-z_]+)"', html_content)
    if not msku_match: 
        return []
    
    records = []
    try:
        data = json.loads(msku_match.group(1))
        v_map = data.get("variationsMap", {})
        menu_map = data.get("menuItemMap", {})
        combos = data.get("variationCombinations", {})
        
        for combo_key, variant_id in combos.items():
            details = v_map.get(variant_id, {})
            if not details: continue
            
            labels = [menu_map.get(idx, {}).get("valueValue") or menu_map.get(idx, {}).get("displayValue", "") for idx in combo_key.split("_")]
            labels = [l.strip() for l in labels if l]
            
            price_info = details.get("priceValue") or details.get("price", {})
            price = float(price_info.get("value") if isinstance(price_info, dict) else price_info)
            
            records.append(_build_child_item(base_item, f"-{variant_id}", f" ({' - '.join(labels)})" if labels else f" (Variant {variant_id})", labels, price, details.get("isOutOfStock", False)))
    except Exception as e:
        logger.error(f"MSKU engine block failed: {e}")
    return records

def _build_child_item(base: MarketItem, id_suffix: str, title_suffix: str, labels: List[str], price: float, out_of_stock: bool) -> MarketItem:
    """Helper to maintain consistency in MarketItem construction."""
    return MarketItem(
        item_id=f"{base.item_id}{id_suffix}",
        model_name=base.model_name,
        category=base.category,
        raw_title=f"{base.raw_title} [{', '.join(labels)}]" if labels else base.raw_title,
        title=f"{base.title}{title_suffix}",
        price=price,
        shipping_cost=base.shipping_cost,
        total_cost=round(price + base.shipping_cost, 2),
        currency=base.currency,
        condition_id=base.condition_id,
        is_sold=base.is_sold,
        source_platform="ebay",
        item_url=base.item_url,
        quantity_sold=0 if out_of_stock else 1,
        process_state="COMPLETED",
        data_grade="SILVER"
    )

def parse_var_model_json(html_content: str, base_item: MarketItem) -> List[MarketItem]:
    """Handles the alternative itmVarModel/ItemJson variant extraction."""
    var_model_match = re.search(r'"itmVarModel"\s*:\s*(\{.*?\})(?:,\s*"|\s*\})', html_content)
    if not var_model_match:
        var_model_match = re.search(r'ItemJson["\']\s*:\s*(\{.*?\})(?:,\s*"|\s*\})', html_content)

    if not var_model_match:
        return []

    records = []
    try:
        model_data = json.loads(var_model_match.group(1))
        menu_items = model_data.get("menuItemMap") or model_data.get("menuViewModel", {}).get("menuItemMap", {})

        for idx, (menu_id, details) in enumerate(menu_items.items()):
            variant_text = details.get("text") or details.get("valueValue")
            if not variant_text or variant_text.upper() == "SELECT":
                continue

            variant_price = base_item.price
            if "price" in details:
                try:
                    variant_price = float("".join(c for c in str(details["price"]) if c.isdigit() or c == "."))
                except ValueError:
                    pass

            records.append(_build_child_item(
                base_item, f"-v{idx}", f" ({variant_text})", [variant_text], variant_price, False
            ))
    except Exception as e:
        logger.error(f"Error decoding alternative variant context model: {e}")
    return records

def parse_dom_sku_options(soup: BeautifulSoup, base_item: MarketItem) -> List[MarketItem]:
    """Handles the final fallback: DOM based SKU listbox extraction."""
    records = []
    sku_options = soup.find_all(class_="listbox__option", attrs={"data-sku-value-name": True})
    
    for index, option in enumerate(sku_options):
        variant_text = option["data-sku-value-name"].strip()
        if not variant_text or variant_text.upper() == "SELECT":
            continue
        if option.has_attr("aria-disabled") and option["aria-disabled"].lower() == "true":
            continue

        records.append(_build_child_item(
            base_item, f"-dom{index}", f" ({variant_text})", [variant_text], base_item.price, False
        ))
    return records