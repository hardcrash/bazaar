# src/database/models.py
"""
Bazaar Database Schema Models

This module defines the relational database layout for the Bazaar persistence layer using 
SQLAlchemy ORM. It establishes a dual-table structure to separate active live market sweeps 
from historical transactional logging entries.
"""

import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Table, JSON
from sqlalchemy.orm import declarative_base

# Modernized SQLAlchemy 2.0 Base Declaration to resolve deprecation warnings
Base = declarative_base()


class ActiveMarketItemModel(Base):
    """
    Live target monitoring pool tracking current active listings on market platforms.
    """
    __tablename__ = "active_market_items"

    # Core Identity Identifiers & Provenance
    item_id = Column(String, primary_key=True, index=True)
    source_platform = Column(String, default="ebay", nullable=False, index=True)
    model_name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)

    # Textual Information & Rich Contents
    raw_title = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Structural Metadata Storage Matrix
    item_specifics = Column(JSON, default=dict, nullable=True)

    # Pricing Metrics
    price = Column(Float, default=0.0, nullable=False)
    shipping_cost = Column(Float, default=0.0, nullable=False)
    total_cost = Column(Float, default=0.0, nullable=False)
    currency = Column(String, default="USD", nullable=False)

    # Classification & Defect Flags (Symmetrical)
    condition_id = Column(Integer, default=3000, nullable=False)
    has_bent_pins = Column(Boolean, default=False, nullable=False)
    is_for_parts_or_not_working = Column(Boolean, default=False, nullable=False)

    # Universal Platform & Seller Telemetry Context
    item_url = Column(String, default="", nullable=True)
    seller_username = Column(String, nullable=True)
    is_top_rated = Column(Boolean, default=False, nullable=True)
    feedback_score = Column(Integer, nullable=True)
    feedback_percentage = Column(Float, nullable=True)
    item_location = Column(String, nullable=True)
    
    # Volatile Live Variables
    bid_count = Column(Integer, default=0, nullable=True)
    quantity_available = Column(Integer, default=1, nullable=False)
    image_urls = Column(JSON, default=list, nullable=True)
    sourcing_score = Column(Float, default=0.0, nullable=True)
    
    # Pipeline Management
    process_state = Column(String, default="ACTIVE", nullable=False)
    data_grade = Column(String, default="BRONZE", nullable=False)
    date_fetched = Column(DateTime, default=datetime.datetime.now, nullable=False)


class HistoricalMarketItemModel(Base):
    """
    Frozen execution data logging sold, completed, or closed transactional item entries.
    """
    __tablename__ = "historical_market_items"

    # Core Identity Identifiers & Provenance
    item_id = Column(String, primary_key=True, index=True)
    source_platform = Column(String, default="ebay", nullable=False, index=True)
    model_name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)

    # Textual Information & Rich Contents
    raw_title = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Structural Metadata Storage Matrix
    item_specifics = Column(JSON, default=dict, nullable=True)

    # Pricing Metrics
    price = Column(Float, default=0.0, nullable=False)
    shipping_cost = Column(Float, default=0.0, nullable=False)
    total_cost = Column(Float, default=0.0, nullable=False)
    currency = Column(String, default="USD", nullable=False)

    # Classification & Defect Flags (Symmetrical)
    condition_id = Column(Integer, default=3000, nullable=False)
    has_bent_pins = Column(Boolean, default=False, nullable=False)
    is_for_parts_or_not_working = Column(Boolean, default=False, nullable=False)

    # Universal Platform & Seller Telemetry Context
    item_url = Column(String, default="", nullable=True)
    seller_username = Column(String, nullable=True)
    is_top_rated = Column(Boolean, default=False, nullable=True)
    feedback_score = Column(Integer, nullable=True)
    feedback_percentage = Column(Float, nullable=True)
    item_location = Column(String, nullable=True)
    
    # Settlement Metrics
    is_sold = Column(Boolean, default=True, nullable=False)
    quantity_sold = Column(Integer, default=1, nullable=False)
    bid_count = Column(Integer, default=0, nullable=True)
    end_date = Column(DateTime, nullable=True)
    
    # Verification Loops
    is_parsed_by_agent = Column(Boolean, default=False, nullable=False)

    # Pipeline Management Lifecycles & Warehouse Metadata
    process_state = Column(String, default="PENDING", nullable=False)
    data_grade = Column(String, default="BRONZE", nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.now, nullable=False)


# Native Metadata Table Mapping to enforce existence of historical tracking indexes
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