# src/core/models.py
from dataclasses import dataclass
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
    source_platform: str

    # Text Representation
    raw_title: str
    title: str

    # Financial Matrix
    price: float
    shipping_cost: float
    total_cost: float
    currency: str

    # Condition Metrics & Risk Signals
    condition_id: int
    is_sold: bool
    is_for_parts_or_not_working: bool = False
    has_bent_pins: bool = False

    # Seller Metadata Engine
    seller_username: Optional[str] = None
    feedback_score: Optional[int] = None
    feedback_percentage: Optional[float] = None
    is_top_rated: bool = False

    # Structural Attributes & Catalog Codes
    epid: Optional[str] = None
    buying_options: Optional[List[str]] = None
    quantity_sold: Optional[int] = None
    bid_count: Optional[int] = None

    # Temporal Velocity Counters
    item_start_date: Optional[str] = None
    item_end_date: Optional[str] = None

    # Assets & State Routines
    image_url: Optional[str] = None
    item_url: Optional[str] = None
    process_state: Optional[str] = None

    # AI agent parameters
    is_parsed_by_agent: bool = False
