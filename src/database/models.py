# src/database/models.py
import json
import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Index, PrimaryKeyConstraint, TypeDecorator
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class JSONEncodedList(TypeDecorator):
    """Safely converts Python lists to JSON strings for SQLite storage and back again."""
    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
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
    buying_options = Column(JSONEncodedList, nullable=True)  # 🌟 Automatically serializes lists smoothly!
    quantity_sold = Column(Integer, default=1)
    bid_count = Column(Integer, nullable=True)

    # Temporal Velocity Counters
    item_start_date = Column(DateTime, nullable=True)
    item_end_date = Column(DateTime, nullable=True)
    date_listed = Column(DateTime, nullable=True)
    date_fetched = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))  # Fixed deprecation warning

    # Assets & Pipeline State Management
    image_url = Column(String, nullable=True)
    item_url = Column(String, nullable=True)
    process_state = Column(String, default="PENDING", index=True)

    # AI agent parameters
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

    last_updated = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))

    __table_args__ = (
        PrimaryKeyConstraint('model_name', 'timeframe', 'condition_type'),
    )

def insert_harvested_item(self, market_item_obj):
        """Accepts a MarketItem object, converts it to an ORM record, and commits it."""
        session = self.SessionLocal()
        try:
            # Flatten dataclass/object into dictionary attributes
            data = market_item_obj.__dict__.copy()

            # Identify valid database column keys
            model_columns = MarketItemModel.__table__.columns.keys()

            # Separate core attributes from strategy-specific anomalies
            core_data = {k: v for k, v in data.items() if k in model_columns}
            extra_data = {k: v for k, v in data.items() if k not in model_columns}

            # If your schema doesn't have a metadata_fields column,
            # this extra_data can just be ignored or logged.
            if extra_data and "metadata_fields" in model_columns:
                core_data["metadata_fields"] = extra_data

            # Upsert behavior: Inserts if new, updates if matching primary key 'item_id'
            db_item = MarketItemModel(**core_data)
            session.merge(db_item)
            session.commit()

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
