# src/analysis/analysis_controller.py

from typing import Dict, Any, Optional
from loguru import logger
from src.analysis.active_analysis_controller import ActiveAnalysisController

class AnalysisController:
    """Facade orchestrator directing application commands to specialized runtimes."""
    def __init__(self, config, category: str = "CPU"):
        self.config = config
        self.category = category

        self.active_controller = ActiveAnalysisController(config=config, category=category)
        self._historical_controller: Optional[Any] = None

    @property
    def historical_controller(self):
        if self._historical_controller is None:
            from src.analysis.historical_analysis_controller import HistoricalAnalysisController
            logger.info("Initializing Historical sub-controller context...")
            self._historical_controller = HistoricalAnalysisController(config=self.config, category=self.category)
        return self._historical_controller

    def run_harvest(self, mode: str = "historical", **kwargs) -> Dict[str, Any]:
        """Routes execution requests seamlessly down to designated runtime engine targets."""
        # Cleans out dry run flags before entering controllers
        kwargs.pop("dry_run", None)
        
        if mode == "active":
            return self.active_controller.run_harvest(**kwargs)
        elif mode == "historical":
            return self.historical_controller.run_harvest(**kwargs)
        else:
            logger.error(f"❌ Aborted route processing: Unrecognized harvest mode configuration token: '{mode}'")
            return {"status": "INVALID_MODE", "inserted_records": 0, "total_processed": 0}S