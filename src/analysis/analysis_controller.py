# src/analysis/analysis_controller.py

from typing import Dict, Any, Optional
from loguru import logger

from src.analysis.active_analysis_controller import ActiveAnalysisController

class AnalysisController:
    """Facade orchestrator directing application commands to specialized runtimes."""
    def __init__(self, config, category: str = "CPU"):
        self.config = config
        self.category = category

        # 🛸 Active client sub-controller is always safe to initialize immediately
        self.active_controller = ActiveAnalysisController(config=config, category=category)
        
        # 🕷️ Defer historical controller initialization to bypass legacy scraper overhead entirely on active runs
        self._historical_controller: Optional[Any] = None

    @property
    def historical_controller(self):
        """Lazily builds and configures the historical sweep runtime engine only when accessed."""
        if self._historical_controller is None:
            from src.analysis.historical_analysis_controller import HistoricalAnalysisController
            logger.info("Initializing Historical sub-controller context...")
            self._historical_controller = HistoricalAnalysisController(config=self.config, category=self.category)
        return self._historical_controller

    def run_harvest(self, mode: str = "historical", **kwargs) -> Dict[str, Any]:
        """Routes execution requests seamlessly down to designated runtime engine targets."""
        if mode == "active":
            return self.active_controller.run_harvest(mode=mode, **kwargs)
        elif mode == "historical":
            # Accessing the property automatically triggers lazy loading of the scraping infrastructure
            return self.historical_controller.run_harvest(mode=mode, **kwargs)
        else:
            logger.error(f"❌ Aborted route processing: Unrecognized harvest mode configuration token: '{mode}'")
            return {"status": "INVALID_MODE", "inserted_records": 0, "total_processed": 0}

    def run_consolidation(self) -> None:
        """Invokes cross-table structural calculations across generated items."""
        logger.info("Executing localized data layout baseline consolidation metrics...")
        # Your metric consolidation logic or file output cache processing loops go here