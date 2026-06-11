# src/database/db_manager.py

import os
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, MarketItemModel

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

    def insert_harvested_item(self, market_item_obj):
        """Accepts a MarketItem data contract object, converts it to an ORM record, and commits it."""
        session = self.SessionLocal()
        try:
            # Flatten dataclass/object attributes cleanly into a dictionary mapping
            data = market_item_obj.__dict__.copy()

            # Identify valid columns declared in our SQLAlchemy declarative model
            model_columns = MarketItemModel.__table__.columns.keys()

            # Separate core schema attributes from strategy-specific anomalies
            core_data = {k: v for k, v in data.items() if k in model_columns}

            # Instantiate ORM mapping engine model
            db_item = MarketItemModel(**core_data)

            # Execute automated context upsert engine via session merging
            session.merge(db_item)
            session.commit()

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
