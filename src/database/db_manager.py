# src/database/db_manager.py

import os
import json
import datetime
from typing import Set
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, MarketItemModel
from loguru import logger
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

class DatabaseManager:
    def __init__(self, config):
        # Gracefully handle configuration access paradigms
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

    def get_existing_item_ids(self, item_ids: list) -> Set[str]:
        """Queries the database for a specific subset of IDs to verify existence."""
        session = self.SessionLocal()
        try:
            # Efficiently check only the IDs provided in the list
            results = session.query(MarketItemModel.item_id).filter(
                MarketItemModel.item_id.in_(item_ids)
            ).all()
            return {str(row[0]) for row in results}
        except Exception as e:
            logger.error(f"Failed to filter existing IDs: {e}")
            return set()
        finally:
            session.close()

    def commit_market_items(self, db_conn_unused, final_records: list, overwrite_on_conflict: bool = False) -> int:
        """
        Processes a batch list of MarketItem objects.
        - Default: Inserts new records, ignoring duplicate conflicts (INSERT OR IGNORE).
        - Optional: Updates existing records if overwrite_on_conflict=True (UPSERT).
        """
        if not final_records:
            return 0

        session = self.SessionLocal()
        new_inserts_count = 0
        model_columns = MarketItemModel.__table__.columns.keys()

        try:
            # 1. Pull existing IDs in this batch to verify what is truly new vs an ignore/update
            batch_ids = [str(item.item_id) for item in final_records]
            existing_ids = set(
                r[0] for r in session.query(MarketItemModel.item_id)
                .filter(MarketItemModel.item_id.in_(batch_ids))
                .all()
            )

            for item_dataclass in final_records:
                is_new = str(item_dataclass.item_id) not in existing_ids

                # 2. Extract item data dictionary from the dataclass
                raw_data = item_dataclass.__dict__.copy()

                # 🛠️ DATATYPE HARMONIZATION: Extract string image_url from image_urls collection list if needed
                if "image_urls" in raw_data and "image_url" in model_columns:
                    urls = raw_data.get("image_urls")
                    if urls and isinstance(urls, list):
                        raw_data["image_url"] = urls[0]
                    elif isinstance(urls, str):
                        raw_data["image_url"] = urls

                # Map data structure into a clean schema layout dictionary restricted to your model table columns
                item_data = {}
                for col_name in model_columns:
                    val = raw_data.get(col_name)
                    if val is not None:
                        # 🛠️ SERIALIZATION PATCH: Convert unbindable complex types to primitive json text blocks for SQLite
                        if isinstance(val, (list, dict)):
                            item_data[col_name] = json.dumps(val)
                        else:
                            item_data[col_name] = val

                stmt = sqlite_insert(MarketItemModel).values(**item_data)

                # 3. Handle conflict strategies cleanly depending on the runtime context
                if overwrite_on_conflict:
                    # Enforce strict UPSERT behavior for your scalar states/test requirements
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['item_id'],
                        set_={
                            col_name: getattr(stmt.excluded, col_name)
                            for col_name in model_columns
                            if col_name != 'item_id'
                        }
                    )
                else:
                    # Enforce high-speed strict INSERT OR IGNORE for historical scraping sweeps
                    stmt = stmt.on_conflict_do_nothing(index_elements=['item_id'])

                session.execute(stmt)

                if is_new:
                    new_inserts_count += 1
                    existing_ids.add(str(item_dataclass.item_id))

            session.commit()
            return new_inserts_count

        except Exception as e:
            session.rollback()
            logger.error(f"Database batch write crash: {e}")
            raise e
        finally:
            session.close()

    def insert_harvested_item(self, item_dataclass) -> int:
        """
        Scalar entry point keeping backward compatibility with your active unit test routines.
        Forces overwrite_on_conflict=True to satisfy test mutations and state changes.
        """
        return self.commit_market_items(None, [item_dataclass], overwrite_on_conflict=True)
