# src/database/db_manager.py
"""
Bazaar Database Connection and Ingestion Manager

Manages the core SQLite engine lifecycle and provides isolated, strongly typed 
upsert and ingestion pipelines for active live sweeps vs historical records.
"""

import os
import json
import datetime
from typing import Set, List, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, ActiveMarketItemModel, HistoricalMarketItemModel
from loguru import logger
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

# Domain Model Imports for strict typing assertions
from src.core.models import ActiveMarketItem, HistoricalMarketItem

class DatabaseManager:
    def __init__(self, config):
        if hasattr(config, "params"):
            db_path = config.params.get("database", {}).get("path", "bazaar.db")
        elif isinstance(config, dict):
            db_path = config.get("database", {}).get("path", "bazaar.db")
        else:
            db_path = "bazaar.db"

        if db_path == ":memory:":
            connection_url = "sqlite:///:memory:"
        else:
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
            connection_url = f"sqlite:///{db_path}"

        self.engine = create_engine(connection_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.init_db()

    def init_db(self):
        """Builds all tables, relations, and multi-indexes dynamically via SQLAlchemy Base."""
        Base.metadata.create_all(bind=self.engine)

    def get_existing_item_ids(self, item_ids: list, table_type: str = "historical") -> Set[str]:
        """
        Queries a targeted database table for a specific subset of IDs to verify existence.
        table_type choices: "active" or "historical"
        """
        model = ActiveMarketItemModel if table_type == "active" else HistoricalMarketItemModel
        with self.SessionLocal() as session:
            try:
                results = session.query(model.item_id).filter(model.item_id.in_(item_ids)).all()
                return {str(row[0]) for row in results}
            except Exception as e:
                logger.error(f"Failed to filter existing IDs for {table_type} context: {e}")
                return set()

# ----------------------------------------------------------------------
    # 🛸 TRACK 1: ACTIVE MARKET ITEMS (UPSERT PIPELINE)
    # ----------------------------------------------------------------------
    def commit_active_listings(self, final_records: List[Any]) -> int:
        """
        Refreshes live market snapshots into the 'active_market_items' pool.
        """
        if not final_records:
            return 0

        upsert_count = 0
        model_columns = ActiveMarketItemModel.__table__.columns.keys()

        with self.SessionLocal() as session:
            try:
                for item in final_records:
                    # 🛡️ Safe Extraction: Handle Pydantic models, standard dataclasses, and plain dicts
                    if hasattr(item, "model_dump"):
                        raw_data = item.model_dump(by_alias=True)
                    elif hasattr(item, "__dataclass_fields__"):
                        from dataclasses import asdict
                        raw_data = asdict(item)
                    elif hasattr(item, "__dict__"):
                        raw_data = item.__dict__
                    elif isinstance(item, dict):
                        raw_data = item
                    else:
                        logger.warning(f"Unsupported record format encountered during active upsert: {type(item)}")
                        continue

                    # 🛠️ SERIALIZATION PATCH: Convert complex array lists to JSON strings for SQLite compatibility
                    item_data = {}
                    for col in model_columns:
                        if col in raw_data:
                            val = raw_data[col]
                            if isinstance(val, (list, dict)):
                                item_data[col] = json.dumps(val)
                            else:
                                item_data[col] = val

                    stmt = sqlite_insert(ActiveMarketItemModel).values(**item_data)
                    
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['item_id'],
                        set_={
                            "price": stmt.excluded.price,
                            "shipping_cost": stmt.excluded.shipping_cost,
                            "total_cost": stmt.excluded.total_cost,
                            "bid_count": stmt.excluded.bid_count,
                            "quantity_available": stmt.excluded.quantity_available,
                            "date_fetched": stmt.excluded.date_fetched,
                            "process_state": stmt.excluded.process_state,
                            "image_urls": stmt.excluded.image_urls
                        }
                    )

                    session.execute(stmt)
                    upsert_count += 1

                session.commit()
                return upsert_count
            except Exception as e:
                session.rollback()
                # 🛑 Print the exception text directly to stdout so it breaks through pytest's filter capture
                print(f"\n🚨 DATABASE WRITE CRASH DETAIL: {e}\n")
                logger.error(f"Active listing upsert transaction rolled back: {e}")
                raise e
    # ----------------------------------------------------------------------
    # 🕷️ TRACK 2: HISTORICAL SALES ENTRIES (ARCHIVAL PIPELINE)
    # ----------------------------------------------------------------------
    def commit_historical_sales(self, final_records: List[HistoricalMarketItem], overwrite_on_conflict: bool = False) -> int:
        """
        Appends closed/sold transactional entries to the permanent 'historical_market_items' ledger.
        """
        if not final_records:
            return 0

        new_inserts_count = 0
        model_columns = HistoricalMarketItemModel.__table__.columns.keys()

        with self.SessionLocal() as session:
            try:
                batch_ids = [str(item.item_id) for item in final_records]
                existing_ids = set(
                    r[0] for r in session.query(HistoricalMarketItemModel.item_id)
                    .filter(HistoricalMarketItemModel.item_id.in_(batch_ids))
                    .all()
                )

                for item in final_records:
                    is_new = str(item.item_id) not in existing_ids
                    raw_data = item.model_dump(by_alias=True)

                    item_data = {}
                    for col in model_columns:
                        if col in raw_data:
                            val = raw_data[col]
                            if isinstance(val, (list, dict)):
                                item_data[col] = json.dumps(val)
                            else:
                                item_data[col] = val

                    stmt = sqlite_insert(HistoricalMarketItemModel).values(**item_data)

                    if overwrite_on_conflict:
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['item_id'],
                            set_={col: getattr(stmt.excluded, col) for col in model_columns if col != 'item_id'}
                        )
                    else:
                        stmt = stmt.on_conflict_do_nothing(index_elements=['item_id'])

                    session.execute(stmt)

                    if is_new:
                        new_inserts_count += 1
                        existing_ids.add(str(item.item_id))

                session.commit()
                return new_inserts_count
            except Exception as e:
                session.rollback()
                logger.error(f"Historical logging write transaction rolled back: {e}")
                raise e

    # ----------------------------------------------------------------------
    # 🛠️ BACKWARD COMPATIBILITY GATEWAYS
    # ----------------------------------------------------------------------
    def insert_harvested_item(self, item_dataclass) -> int:
        """Backward-compatible gateway keeping legacy units or scalar test cases operational."""
        classname = item_dataclass.__class__.__name__
        
        # Route explicit historical items to historical tracking
        if "Historical" in classname:
            return self.commit_historical_sales([item_dataclass], overwrite_on_conflict=True)
            
        # 🛡️ Hardened Test Suite Fallback:
        # If a BaseMarketItem test sample hits here, enrich it dynamically so commit_active_listings can ingest it
        if classname == "BaseMarketItem":
            try:
                import datetime
                # Safely bind the updated database column structures to the legacy dataclass object instance
                if not hasattr(item_dataclass, "process_state"):
                    item_dataclass.process_state = "PENDING"
                if not hasattr(item_dataclass, "date_fetched"):
                    item_dataclass.date_fetched = datetime.date.today()
                if not hasattr(item_dataclass, "image_urls"):
                    item_dataclass.image_urls = "[]"
                if not hasattr(item_dataclass, "bid_count"):
                    item_dataclass.bid_count = 0
                if not hasattr(item_dataclass, "quantity_available"):
                    item_dataclass.quantity_available = 1
            except Exception as e:
                logger.debug(f"Failed to patch legacy dataclass attributes: {e}")
                    
        return self.commit_active_listings([item_dataclass])