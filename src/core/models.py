# src/core/models.py

from dataclasses import dataclass
from typing import Optional, List

@dataclass(frozen=True)
class MarketItem:
    """
    Unified data contract protecting the core architecture from variations
    in third-party marketplace API schemas (eBay, Jawa, Mercari, etc.).
    Optimized for precision computer component tracking and automated sourcing analysis.
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

    # Condition Metrics
    condition_id: int
    is_sold: bool
    is_for_parts_or_not_working: bool = False  # Direct flag for broken/repairable units
    has_bent_pins: bool = False               # Targeted structural hardware risk signal

    # Seller Metadata Engine
    seller_username: Optional[str] = None
    feedback_score: Optional[int] = None
    feedback_percentage: Optional[float] = None  # Crucial safety companion to feedback_score
    is_top_rated: bool = False

    # Structural Attributes & Catalog Codes
    epid: Optional[str] = None
    buying_options: Optional[List[str]] = None  # e.g., ['BIN', 'AUCTION', 'BEST_OFFER']
    quantity_sold: Optional[int] = None         # Essential for high-volume MSKU velocity tracking
    bid_count: Optional[int] = None

    # Temporal Velocity Counters
    item_start_date: Optional[str] = None       # Used to calculate absolute Days on Market (DoM)
    item_end_date: Optional[str] = None

    # Assets & State Routines
    image_url: Optional[str] = None
    item_url: Optional[str] = None
    process_state: Optional[str] = None         # e.g., 'UNPROCESSED', 'PENDING_DEEP_HARVEST', 'PROCESSED'
