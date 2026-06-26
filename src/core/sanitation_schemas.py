# src/core/sanitation_schemas.py
"""
Bazaar Sourcing Pipeline Sanitation Schemas

This module defines the validation structures and data transformation rules 
for raw API inputs. It leverages Pydantic models to strip raw text anomalies, 
normalize currency formatting representations, and filter platform condition IDs.
"""

import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class EbayAPIItemSchema(BaseModel):
    """Strict Pydantic enforcement layer for incoming eBay API payloads."""
    item_id: str = Field(alias="itemId")
    title: str = Field(min_length=1)
    price_string: str = Field(alias="price")
    shipping_string: Optional[str] = Field(default="0.0", alias="shippingCost")
    condition_id: int = Field(alias="conditionId")
    seller_username: str = Field(alias="sellerUser")
    feedback_score: int = Field(alias="feedbackScore")
    feedback_percent: float = Field(alias="positiveFeedbackPercent")

    # 🌟 Transformer: Collapses internal whitespace, tabs, and newlines down to single spaces
    @field_validator("title", mode="after")
    @classmethod
    def clean_whitespace(cls, v: str) -> str:
        if v:
            # Replaces any length of whitespace characters (\t, \n, spaces) with one space
            return re.sub(r'\s+', ' ', v).strip()
        return v

    # 🌟 Transformer: Strips currency symbols, commas, and normalizes numeric texts
    @field_validator("price_string", "shipping_string", mode="before")
    @classmethod
    def clean_currency(cls, v: any) -> str:
        if v is None:
            return "0.0"
        v_str = str(v).upper()
        if "FREE" in v_str:
            return "0.0"
        # Extract digits, periods, and minus signs only
        cleaned = "".join(c for c in v_str if c.isdigit() or c in [".", "-"])
        return cleaned if cleaned else "0.0"

    # 🌟 Validator: Ensures condition codes conform to standard eBay brackets
    @field_validator("condition_id")
    @classmethod
    def validate_condition(cls, v: int) -> int:
        # Standard eBay desktop tiers (New, Used, Refurbished, Parts)
        valid_ranges = [1000, 1500, 2000, 2500, 3000, 4000, 5000, 7000]
        if v not in valid_ranges and not (3000 <= v <= 3999):
            raise ValueError(f"Invalid eBay condition ID specification: {v}")
        return v