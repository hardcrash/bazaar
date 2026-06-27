# src/api/ebay/scrape_parsers/dom.py
"""
DOM Traversal and Structural Parsing Utilities for eBay Scraping Operations.

This module provides stateless functional utilities to navigate the HTML document 
object model (DOM), isolate product listing card containers, filter structural noise/ads, 
and handle fallback link-driven tree-walking routines.
"""

from typing import List, Optional, Any, Set
from bs4 import Tag, BeautifulSoup

def should_skip_title(title: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Evaluates an extracted title string to filter out empty reads or ads.
    Returns a tuple of (should_skip, metric_key_to_increment).
    """
    if not title:
        return True, "no_title"
        
    if "shop on" in title.lower():
        return True, "shop_on"
        
    return False, None

def find_first_match(element: BeautifulSoup, selectors: List[str]) -> Optional[Tag]:
    """Iterates through an ordered list of CSS selectors, returning the first matching element."""
    for selector in selectors:
        hit = element.select_one(selector)
        if hit:
            return hit
    return None

def bubble_to_container_root(node: Tag) -> Tag:
    """
    Ascends the DOM tree from a discovered element to isolate its primary outer container row,
    filtering out internal tracking layers.
    """
    if any(k in node.get('class', []) for k in ['s-item', 's-card']) or node.name == 'li':
        return node
        
    ancestor = node.find_parent('li', class_=lambda c: c and any(k in c for k in ['s-item', 's-card'])) or \
               node.find_parent('div', class_=lambda c: c and any(k in c for k in ['s-item', 's-card', 'su-card']))
    return ancestor if ancestor else node

def is_valid_listing(node: Tag) -> bool:
    """Evaluates an isolated node to filter out tracking items, ads, or structural placeholders."""
    classes = node.get('class', [])
    node_id_str = str(node.get("id", ""))
    class_str = "".join(classes)
    
    if node.select_one(".s-item__ad-modifier") or node.select_one(".s-item__sponsored-label"):
        return False
        
    if "s-item__placeholder" in classes or "s-item--watch-tile" in class_str or "listing1" in node_id_str:
        return False
        
    return True

def harvest_fallback_links(scope: BeautifulSoup) -> List[Tag]:
    """Fallback engine that identifies items by harvesting deep product page anchors directly."""
    item_links = scope.find_all('a', href=lambda h: h and '/itm/' in h)
    seen_parents = set()
    listings = []
    
    for link in item_links:
        parent = link.find_parent('li') or \
                 link.find_parent('div', class_=lambda c: c and any(k in c for k in ['s-item', 'result', 'item', 'card']))
        
        if parent and id(parent) not in seen_parents:
            node_id_str = str(parent.get("id", ""))
            if "listing1" not in node_id_str and not parent.select_one(".s-item__ad-modifier"):
                seen_parents.add(id(parent))
                listings.append(parent)
    return listings

def harvest_item_identifiers(item: Tag, link_selectors: List[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Extracts the unique platform item ID and clean canonical listing URL 
    from a DOM card node using configured link selectors.
    """
    import re
    
    item_id = item.get('data-id') or item.get('data-itemid')
    
    # Try configured YAML matrix targets first, fall back to loose fallback anchor
    link_elem = None
    for selector in link_selectors:
        link_elem = item.select_one(selector)
        if link_elem:
            break
            
    if not link_elem:
        link_elem = item.find('a')
        
    item_url = ""
    if link_elem and link_elem.has_attr('href'):
        item_url = link_elem['href'].split('?')[0]

    if not item_id and item_url:
        item_id_match = re.search(r'/itm/(\d+)', item_url)
        if item_id_match:
            item_id = item_id_match.group(1)

    if not item_id or not item_url or "/itm/" not in item_url:
        return None, None

    return item_id, item_url

def harvest_raw_title_text(item: Tag, title_selectors: List[str]) -> Optional[str]:
    """
    Extracts the raw title string from ordered selectors, accounting for nested 
    spans or falling back to image alt tags.
    """
    raw_text = None
    for selector in title_selectors:
        title_node = item.select_one(selector)
        if title_node:
            inner_spans = title_node.find_all('span')
            if inner_spans:
                raw_text = inner_spans[-1].get_text(strip=True)
            else:
                raw_text = title_node.get_text(strip=True)
            break
            
    if not raw_text:
        img_node = item.select_one(".s-item__image-img, img")
        if img_node and img_node.get('alt'):
            raw_text = img_node.get('alt')
            
    return raw_text