# src/database/models.py

import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Index, PrimaryKeyConstraint, TypeDecorator, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class JSONEncodedList(TypeDecorator):
    """Safely converts Python lists to JSON strings for SQLite storage and back again."""
    impl = String

    def process_bind_param(self, value, dialect, **kwargs):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect, **kwargs):
        if value is not None:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

class MarketItemModel(Base):
    __tablename__ = "market_items"

    # Core Identifiers
    item_id = Column(String, primary_key=True, index=True)
    model_name = Column(String, nullable=False, default="UNKNOWN", index=True)
    category = Column(String, nullable=False, index=True)
    source_platform = Column(String, nullable=False, default="ebay")

    # Text Representation
    raw_title = Column(String, nullable=False)
    title = Column(String, nullable=False)

    # Financial Matrix
    price = Column(Float, nullable=False)
    shipping_cost = Column(Float, default=0.0)
    total_cost = Column(Float, nullable=False)
    currency = Column(String, default="USD")

    # Condition Metrics & Risk Signals
    condition_id = Column(Integer, nullable=False, default=3000)
    is_sold = Column(Boolean, default=True)
    is_for_parts_or_not_working = Column(Boolean, default=False)
    has_bent_pins = Column(Boolean, default=False)

    # Seller Metadata Engine
    seller_username = Column(String, nullable=True)
    feedback_score = Column(Integer, nullable=True)
    feedback_percentage = Column(Float, nullable=True)
    is_top_rated = Column(Boolean, default=False)

    # Structural Attributes & Catalog Codes
    epid = Column(String, nullable=True)
    buying_options = Column(String, nullable=True, default="Buy It Now")
    quantity_sold = Column(Integer, default=1)
    bid_count = Column(Integer, default=0, nullable=True)

    # Temporal Velocity Counters
    item_start_date = Column(String, nullable=True)
    item_end_date = Column(String, nullable=True)
    date_listed = Column(DateTime, nullable=True)
    date_fetched = Column(DateTime, server_default=func.now(), default=lambda: datetime.now(timezone.utc))

    # Assets & Pipeline State Management
    image_urls = Column(JSONEncodedList, nullable=True)
    item_url = Column(String, nullable=True)
    process_state = Column(String, default="PENDING", index=True)

    # 🌟 DATA GRADE PIPELINE SEGREGATION TOKEN
    # Restricts metrics compilation downstream to verified item variant data entries.
    data_grade = Column(String, default="BRONZE", nullable=False, index=True)

    # AI Agent Parameters
    is_parsed_by_agent = Column(Boolean, default=False)

    __table_args__ = (
        Index('idx_items_filtering', 'model_name', 'is_for_parts_or_not_working', 'has_bent_pins'),
    )


class HistoricalMetricModel(Base):
    __tablename__ = "historical_metrics"

    model_name = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    condition_type = Column(String, nullable=False)

    total_units = Column(Integer, default=0)
    min_item_price = Column(Float, default=0.0)
    max_item_price = Column(Float, default=0.0)
    avg_item_price = Column(Float, default=0.0)
    med_item_price = Column(Float, default=0.0)
    avg_shipping_cost = Column(Float, default=0.0)
    avg_total_cost = Column(Float, default=0.0)

    last_updated = Column(
        DateTime,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        PrimaryKeyConstraint('model_name', 'timeframe', 'condition_type'),
    )
