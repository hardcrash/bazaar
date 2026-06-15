# src/analysis/analysis_controller.py

from typing import Dict, Any, Optional
from loguru import logger

from src.analysis.active_analysis_controller import ActiveAnalysisController
from src.analysis.historical_analysis_controller import HistoricalAnalysisController

class AnalysisController:
    """Facade orchestrator directing application commands to specialized runtimes."""
    def __init__(self, config, category: str = "CPU"):
        self.config = config
        self.category = category

        # Instantiate sub-controllers for clean delegation
        self.active_controller = ActiveAnalysisController(config=config, category=category)
        self.historical_controller = HistoricalAnalysisController(config=config, category=category)

    def run_harvest(self, mode: str = "historical", **kwargs) -> Dict[str, Any]:
        """Routes execution requests seamlessly down to designated runtime engine targets."""
        is_dry_run = kwargs.get("dry_run", False)

        if mode == "active":
            return self.active_controller.run_harvest(mode=mode, **kwargs)
        elif mode == "historical":
            return self.historical_controller.run_harvest(mode=mode, **kwargs)
        else:
            logger.error(f"❌ Aborted route processing: Unrecognized harvest mode configuration token: '{mode}'")
            return {"status": "INVALID_MODE", "inserted_records": 0, "total_processed": 0}

    def run_consolidation(self) -> None:
        """Invokes cross-table structural calculations across generated items."""
        logger.info("Executing localized data layout baseline consolidation metrics...")
        # Your metric consolidation logic or file output cache processing loops go here
