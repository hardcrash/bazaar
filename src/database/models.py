# src/database/models.py
"""
Bazaar Database Schema Models

This module defines the relational database layout for the Bazaar persistence layer using 
SQLAlchemy ORM. These model schemas mirror the fields validated by our Pydantic domain models, 
ensuring structural integrity and efficient indexing when writing or querying items 
from the local SQLite engine.
"""

import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean
from sqlalchemy.orm import declarative_base

# Modernized SQLAlchemy 2.0 Base Declaration to resolve deprecation warnings
Base = declarative_base()

class MarketItemModel(Base):
    """
    Relational database model representing the 'market_items' physical disk table.
    Tracks structural payload telemetry state values across data grades.
    """
    __tablename__ = "market_items"

    # Core Identity Identifiers
    item_id = Column(String, primary_key=True, index=True)
    model_name = Column(String, nullable=False)
    category = Column(String, nullable=False)

    # Textual Information
    raw_title = Column(String, nullable=False)
    title = Column(String, nullable=False)

    # Pricing Metrics
    price = Column(Float, default=0.0, nullable=False)
    shipping_cost = Column(Float, default=0.0, nullable=False)
    total_cost = Column(Float, default=0.0, nullable=False)  # 🌟 Aligned
    currency = Column(String, default="USD", nullable=False)

    # Condition & Verification Flags
    condition_id = Column(Integer, default=3000, nullable=False)
    is_sold = Column(Boolean, default=True, nullable=False)
    source_platform = Column(String, default="ebay", nullable=False)
    item_url = Column(String, default="", nullable=True)
    quantity_sold = Column(Integer, default=1, nullable=False)

    # Seller Telemetry Fields
    seller_name = Column(String, nullable=True)  # Optional structural trace
    feedback_score = Column(Integer, nullable=True)  # 🌟 Aligned
    feedback_percentage = Column(Float, nullable=True)  # 🌟 Aligned
    is_top_rated = Column(Boolean, default=False, nullable=False)

    # Custom Hardware Domain Flags
    has_bent_pins = Column(Boolean, default=False, nullable=False)
    is_for_parts_or_not_working = Column(Boolean, default=False, nullable=False)
    is_parsed_by_agent = Column(Boolean, default=False, nullable=False)

    # Pipeline Management Lifecycles
    process_state = Column(String, default="PENDING", nullable=False)
    data_grade = Column(String, default="BRONZE", nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.now, nullable=False)