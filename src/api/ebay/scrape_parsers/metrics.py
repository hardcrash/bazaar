# src/api/ebay/scrape_parsers/metrics.py
"""
Text Sanitization, Numerical Extraction, and Type Casting Utilities for eBay Data.

This module provides stateless functional utilities to execute regular expression scrubbing,
currency conversion, metric extractions, and string parsing over raw harvested DOM values.
"""

import re
from typing import List, Optional

def sanitize_title_noise(raw_text: str, custom_blacklist: Optional[List[str]] = None) -> str:
    """
    Strips structural HTML noise and custom categorical blacklist phrases 
    out of raw title strings.
    """
    # 1. Structural/Global platform noise (Always safe to remove from any eBay scrap)
    global_noise = ["New Listing", "Opens in a new window or tab", "SPONSORED"]
    
    # 2. Merge with specific strategy filters injected at runtime
    blacklist = global_noise + (custom_blacklist or [])
    
    sanitized = raw_text
    # Sort by length descending to prevent sub-string matching issues
    for noise in sorted(blacklist, key=len, reverse=True):
        if not noise.strip():
            continue
        sanitized = re.sub(re.escape(noise), "", sanitized, flags=re.IGNORECASE)
        
    return sanitized.strip()