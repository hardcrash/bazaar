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
    shipping_cost = Column(Float, default=0.0, nullable=True)
    total_cost = Column(Float, default=0.0, nullable=False)
    currency = Column(String, default="USD", nullable=True)

    # Condition & Verification Flags
    condition_id = Column(Integer, default=3000, nullable=False)
    is_sold = Column(Boolean, default=True, nullable=True)
    source_platform = Column(String, default="ebay", nullable=False)
    item_url = Column(String, default="", nullable=True)
    quantity_sold = Column(Integer, default=1, nullable=True)
    bid_count = Column(Integer, default=0, nullable=True)

    # Seller Telemetry Fields
    seller_username = Column(String, nullable=True)
    feedback_score = Column(Integer, nullable=True)
    feedback_percentage = Column(Float, nullable=True)
    is_top_rated = Column(Boolean, default=False, nullable=True)
    epid = Column(String, nullable=True)
    buying_options = Column(String, nullable=True)

    # Custom Hardware Domain Flags
    has_bent_pins = Column(Boolean, default=False, nullable=True)
    is_for_parts_or_not_working = Column(Boolean, default=False, nullable=True)
    is_parsed_by_agent = Column(Boolean, default=False, nullable=True)

    # Pipeline Management Lifecycles & Dynamic Chrono Bounds
    process_state = Column(String, default="PENDING", nullable=True)
    data_grade = Column(String, default="BRONZE", nullable=False)
    
    # Chrono fields for velocity metric calculation matrices
    item_start_date = Column(DateTime, nullable=True)
    item_end_date = Column(DateTime, nullable=True)
    date_listed = Column(DateTime, nullable=True)
    date_fetched = Column(DateTime, default=datetime.datetime.now, nullable=True)
    image_urls = Column(String, nullable=True)

# Native Metadata Table Mapping to enforce existence of historical tracking indexes
from sqlalchemy import Table
HistoricalMetricsTable = Table(
    "historical_metrics",
    Base.metadata,
    Column("model_name", String, primary_key=True),
    Column("timeframe", String, primary_key=True),
    Column("condition_type", String, primary_key=True),
    Column("total_units", Integer, nullable=False),
    Column("min_item_price", Float, nullable=False),
    Column("max_item_price", Float, nullable=False),
    Column("avg_item_price", Float, nullable=False),
    Column("med_item_price", Float, nullable=False),
    Column("avg_shipping_cost", Float, nullable=False),
    Column("avg_total_cost", Float, nullable=False),
    Column("last_updated", DateTime, nullable=False)
)
