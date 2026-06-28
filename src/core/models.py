# src/core/models.py
"""
Bazaar Domain Infrastructure Models

Establishes an inheritance hierarchy using a shared abstract BaseMarketItem 
to separate dynamic active market sweeps from immutable historical transaction entries.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class HistoricalMarketItem(BaseModel):
    """
    Abstract structural base class containing every common attribute shared between 
    live marketplace listings and archived historical sales transactions.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

    # Core Identifiers
    item_id: str = Field(..., description="Unique platform item identifier (e.g., eBay Item ID)")
    model_name: str = Field(..., description="Target hardware baseline model reference name (e.g., Ryzen 5800X)")
    category: str = Field(..., description="System normalization category code classification")

    # Textual Information
    raw_title: str = Field(..., description="Unmodified title string directly out of the platform/DOM asset")
    title: str = Field(..., description="Cleaned, scrubbed, or variant-appended presentation title")

    # Pricing Metrics Normalized to Float Scalars
    price: float = Field(0.0, description="Spot price tag, current high bid, or base clearing price")
    shipping_cost: float = Field(0.0, description="Extracted localized logistics or delivery surcharges")
    total_cost: float = Field(0.0, description="Computed Gross Capital Cost (Price + Shipping)")
    currency: str = Field("USD", description="Standard ISO alpha financial tracking code")

    # Universal Platform Indicators
    item_url: str = Field("", description="Fully sanitized absolute tracking address pointer link")
    seller_username: Optional[str] = Field(None, description="The platform account handle of the selling party")
    is_top_rated: bool = Field(False, description="Whether the seller carries elite platform status tags")
    process_state: str = Field(..., description="Pipeline lifecycle status tracking token")


class ActiveMarketItem(HistoricalMarketItem):
    """
    Unified domain model validating a live, volatile asset monitoring unit.
    Maps directly onto the mutable 'active_market_items' database infrastructure table.
    """
    # Override default state for active loops
    process_state: str = Field("ACTIVE", description="Default tracking state for live items")
    
    # Volatile Bidding & Inventory Attributes
    bid_count: int = Field(0, description="Current number of placed bids on active auctions")
    quantity_available: int = Field(1, description="Volume count remaining for purchase")
    date_fetched: datetime = Field(default_factory=datetime.now, description="Moment this live snapshot was read")
    image_urls: List[str] = Field(default_factory=list, description="Collection array of absolute asset image addresses")

class HistoricalMarketItem(HistoricalMarketItem):
    """
    Unified domain model tracking an archival, historical transactional sales entry.
    Maps directly onto the immutable, permanent 'historical_market_items' logging table.
    """
    # Override default state for closed items
    process_state: str = Field("PENDING", description="Pipeline lifecycle token: PENDING, PENDING_DEEP_HARVEST, HYDRATED, COMPLETED")
    
    # Condition & Verification Flags
    condition_id: int = Field(3000, description="Platform numerical condition mapping code (e.g., 3000=Used)")
    is_sold: bool = Field(True, description="Historical verification state flag marker")
    source_platform: str = Field("ebay", description="Original distribution pipeline platform index")
    quantity_sold: int = Field(1, description="Volume count cleared within the listing configuration")
    bid_count: int = Field(0, description="Total bids placed before auction clearance closed")

    # Deep Hydration Seller Telemetry Fields (Silver Grade)
    feedback_score: Optional[int] = Field(None, description="The absolute feedback score count of the seller")
    feedback_percentage: Optional[float] = Field(None, description="Positive transaction ratio profile metric")

    # Custom Context Attribute Domain Flags
    has_bent_pins: bool = Field(False, description="Hardware defect indicator parsing safety catch")
    is_for_parts_or_not_working: bool = Field(False, description="Evaluated functional status boolean representation")
    is_parsed_by_agent: bool = Field(False, description="Verification loop assertion milestone tracker")

    # Architectural Grade Management
    data_grade: str = Field("BRONZE", description="Information depth structure index tier: BRONZE, SILVER, GOLD")
    timestamp: datetime = Field(default_factory=datetime.now, description="System entry generation moment trace")