from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class MarketItem(BaseModel):
    """
    Unified domain model tracking an execution unit across extraction grades.
    BRONZE: Initial list parsing entry status.
    SILVER: Fully hydrated single-unit or multi-variation expanded records.
    """
    # Core Primary Keys & Identity Identifiers
    item_id: str = Field(..., description="Unique platform item identifier (e.g., eBay Item ID)")
    model_name: str = Field(..., description="Target hardware baseline model reference name (e.g., Ryzen 5800X)")
    category: str = Field(..., description="System normalization category code classification")

    # Textual Information
    raw_title: str = Field(..., description="Unmodified title string directly out of the DOM asset")
    title: str = Field(..., description="Cleaned, scrubbed, or variant-appended presentation title")

    # Pricing Metrics Normalized to Float Scalars
    price: float = Field(0.0, description="Base clearing or auction Hammer Price")
    shipping_cost: float = Field(0.0, description="Extracted localized logistics or delivery surcharges")
    total_cost: float = Field(0.0, description="Computed Gross Capital Cost (Price + Shipping)")
    currency: str = Field("USD", description="Standard ISO alpha financial tracking code")

    # Metadata, Platform Indicators & Telemetry Tags
    condition_id: int = Field(3000, description="Platform numerical condition mapping code (e.g., 3000=Used, 7000=For Parts)")
    is_sold: bool = Field(True, description="Historical verification state flag marker")
    source_platform: str = Field("ebay", description="Original distribution pipeline platform index")
    item_url: str = Field("", description="Fully sanitized absolute tracking address pointer link")
    quantity_sold: int = Field(1, description="Volume count cleared within the variant or listing configuration")

    # Target Seller Telemetry Fields (Populated via Silver Hydration)
    feedback_score: Optional[int] = Field(None, description="The absolute feedback score count of the selling party")
    feedback_percentage: Optional[float] = Field(None, description="Positive transaction ratio profile metric")
    is_top_rated: bool = Field(False, description="Whether the seller carries elite platform status tags")

    # Custom Context Attribute Domain Flags
    has_bent_pins: bool = Field(False, description="Hardware defect indicator parsing safety catch")
    is_for_parts_or_not_working: bool = Field(False, description="Evaluated functional status boolean representation")
    is_parsed_by_agent: bool = Field(False, description="Verification loop assertion milestone tracker")

    # Architectural Management State Variables
    process_state: str = Field("PENDING", description="Pipeline lifecycle token value: PENDING, PENDING_DEEP_HARVEST, HYDRATED, COMPLETED")
    data_grade: str = Field("BRONZE", description="Information depth structure index tier: BRONZE, SILVER, GOLD")
    timestamp: datetime = Field(default_factory=datetime.now, description="System entry generation moment trace")

    class Config:
        """Pydantic model behaviors setup parsing rules matrix configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
