# src/database/db_manager.py

import os
import datetime
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

                # 2. Map data structure into a clean schema layout dictionary
                item_data = {
                    c.name: getattr(item_dataclass, c.name)
                    for c in MarketItemModel.__table__.columns
                    if getattr(item_dataclass, c.name, None) is not None
                }

                stmt = sqlite_insert(MarketItemModel).values(**item_data)

                # 3. Handle conflict strategies cleanly depending on the runtime context
                if overwrite_on_conflict:
                    # Enforce strict UPSERT behavior for your scalar states/test requirements
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['item_id'],
                        set_={
                            c.name: getattr(stmt.excluded, c.name)
                            for c in MarketItemModel.__table__.columns
                            if c.name != 'item_id'
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
