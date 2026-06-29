# src/core/models.py
"""
Bazaar Domain Infrastructure Models

Establishes an optimized, clean inheritance hierarchy separating volatile 
real-time sourcing models from immutable archival data warehouse models,
fully equipped for multi-platform scaling.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class BaseMarketItem(BaseModel):
    """
    Immutable core contract. Every single item tracking through Bazaar 
    must have these base identifiers, financial metrics, seller trust markers, 
    and source platform tracking.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

    # Core Identifiers & Provenance
    item_id: str = Field(..., description="Unique platform item identifier (e.g., eBay Item ID)")
    source_platform: str = Field("ebay", description="Original sourcing marketplace pipeline index (e.g., ebay, mercari, jawa)")
    model_name: str = Field(..., description="Target hardware baseline model reference name (e.g., Ryzen 5800X)")
    category: str = Field(..., description="System normalization category code classification (e.g., CPU)")

    # Textual Information & Extracted Deep Payloads
    raw_title: str = Field(..., description="Unmodified title string directly out of the platform/DOM asset")
    title: str = Field(..., description="Cleaned, scrubbed presentation title")
    description: Optional[str] = Field(None, description="Full rich text or plaintext description body from the item detail page")
    
    # Marketplace Structural Metadata Pool (Captures MPN, Socket Type, Brand, Cores, etc.)
    item_specifics: Dict[str, Any] = Field(default_factory=dict, description="Structured metadata attributes key-value map")

    # Pricing Metrics
    price: float = Field(0.0, description="Base listing cost or final clearing price")
    shipping_cost: float = Field(0.0, description="Extracted localized delivery surcharges")
    total_cost: float = Field(0.0, description="Computed Gross Capital Cost (Price + Shipping)")
    currency: str = Field("USD", description="Standard ISO alpha financial tracking code")
    
    # Global Classification & Pipeline Control
    condition_id: int = Field(3000, description="Platform numerical condition mapping code (e.g., 3000=Used, 7000=Parts)")
    process_state: str = Field(..., description="Pipeline lifecycle status tracking token")

    # Seller Trust Profiles (Unified across Live and Archival States)
    seller_username: Optional[str] = Field(None, description="The platform account handle of the selling party")
    feedback_score: Optional[int] = Field(None, description="The absolute feedback score count of the seller")
    feedback_percentage: Optional[float] = Field(None, description="Positive transaction ratio profile metric")

    # Universal Domain Defect & Condition Flags
    has_bent_pins: bool = Field(False, description="Hardware defect safety offset check (e.g., bent pins on a CPU)")
    is_for_parts_or_not_working: bool = Field(False, description="Evaluated real-time/historical functional status flag")
    
    # Geographic Context
    item_location: Optional[str] = Field(None, description="Textual origin location of the item (e.g., 'San Jose, CA')")


class ActiveMarketItem(BaseMarketItem):
    """
    Real-time volatile tracking unit optimized for live sourcing, 
    risk-mitigation filtering, and fast arbitrage score matching.
    """
    process_state: str = Field("ACTIVE", description="Default tracking state for live items")
    date_fetched: datetime = Field(default_factory=datetime.now, description="Moment this live snapshot was read")
    
    # Live Sourcing Context Filters
    is_top_rated: bool = Field(False, description="Whether the live seller carries elite platform status tags")
    
    # Bidding & Inventory Telemetry
    bid_count: int = Field(0, description="Current number of placed bids on active auctions")
    quantity_available: int = Field(1, description="Volume count remaining for purchase")
    
    # Presentation Assets
    item_url: str = Field("", description="Sanitized absolute tracking link")
    image_urls: List[str] = Field(default_factory=list, description="Array of image addresses for front-end evaluation")
    
    # Arbitrage Metrics
    sourcing_score: float = Field(0.0, description="Calculated arbitrage sourcing quality score matrix")


class HistoricalMarketItem(BaseMarketItem):
    """
    Archival permanent log entry optimized for analytical price modeling 
    and baseline market value calculations.
    """
    process_state: str = Field("PENDING", description="Archival state: PENDING, HYDRATED, COMPLETED")
    timestamp: datetime = Field(default_factory=datetime.now, description="System entry generation moment trace")
    
    # Settlement Metrics
    is_sold: bool = Field(True, description="Historical verification state flag marker")
    quantity_sold: int = Field(1, description="Volume count cleared within the listing configuration")
    bid_count: int = Field(0, description="Total bids placed before auction clearance closed")
    end_date: Optional[datetime] = Field(None, description="The moment this transaction closed and cleared")

    # Warehouse Metadata
    data_grade: str = Field("BRONZE", description="Information depth structure index tier: BRONZE, SILVER, GOLD")

