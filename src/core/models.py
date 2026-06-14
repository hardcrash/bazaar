# src/core/models.py
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass(frozen=False)  # Unfrozen to allow seamless pipeline state updates
class MarketItem:
    """
    Unified data contract protecting the core architecture from variations
    in third-party marketplace API schemas (eBay, Jawa, Mercari, etc.).
    """
    # Core Platform Identifiers
    item_id: str
    model_name: str
    category: str
    source_platform: str = "ebay"

    # Text Representation
    raw_title: str = ""
    title: str = ""

    # Financial Matrix
    price: float = 0.0
    shipping_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"

    # Condition Metrics & Risk Signals
    condition_id: int = 3000
    is_sold: bool = True
    is_for_parts_or_not_working: bool = False
    has_bent_pins: bool = False  # Added to align with DatabaseManager mapping
    condition_description: Optional[str] = None

    # Seller Metadata Engine
    seller_username: Optional[str] = None
    feedback_score: Optional[int] = None
    feedback_percentage: Optional[float] = None
    is_top_rated: bool = False  # Added to align with DatabaseManager mapping

    # Structural Attributes & Catalog Codes
    epid: Optional[str] = None
    buying_options: Optional[List[str]] = field(default_factory=list)  # Preserved as a list for JSONEncodedList compatibility
    quantity_sold: Optional[int] = 1
    bid_count: Optional[int] = None

    # Temporal Velocity Counters
    item_start_date: Optional[str] = None
    item_end_date: Optional[str] = None

    # Assets & State Routines
    image_urls: Optional[List[str]] = field(default_factory=list)  # Expanded to allow complete array lists of high-res image assets
    item_url: Optional[str] = None
    process_state: Optional[str] = "PENDING"

    # AI agent parameters
    is_parsed_by_agent: bool = False
