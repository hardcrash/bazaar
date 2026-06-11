# main.py

import sys
import argparse
from loguru import logger
import pytest

# Correct structural class imports
from src.util.config_loader import AppConfig
from src.analysis.analysis_controller import AnalysisController
from src.ui.main_window import MainWindow

def setup_logging(log_level: str = "DEBUG"):
    """Configures the loguru formatting matrix for streams and files."""
    logger.remove()

    # Terminal Stream Handler (Dynamic Level Wrapper Fixed 🌟)
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        enqueue=True
    )

    # Persistent Log File Handler
    logger.add(
        "logs/bazaar.log",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        compression="zip"
    )
    logger.debug(f"Logging core initialized engine state at level: {log_level}")

def run_development_gatekeeper() -> bool:
    """
    Programmatically triggers the pytest test suite.
    Returns True if all tests pass, False otherwise.
    """
    logger.info("🔧 Development Mode Flag Active: Initiating Pre-Flight Unit Tests...")

    # Explicitly targeting the 'test' directory isolates pytest's internal argument parser!
    exit_code = pytest.main(["-q", "test"])

    if exit_code == 0:
        logger.success("✅ Pre-flight unit tests passed! Proceeding to execution pipeline...")
        return True

    logger.critical(f"❌ Pre-flight unit tests failed with exit code {exit_code}. Aborting execution pipeline.")
    return False

def main():
    parser = argparse.ArgumentParser(description="Bazaar Pipeline Sourcing Engine")

    # Add the development flag
    parser.add_argument(
        "--dev", "-dev", "-d", "--d",
        action="store_true",
        help="Run in development mode (forces pre-flight unit test check before execution)"
    )

    parser.add_argument(
        "action",
        nargs="?",
        choices=["harvest-active", "harvest-historical", "all"],
        help="Pipeline command routine to execute"
    )

    parser.add_argument(
        "-v", "--verbose", "--v", "-verbose",
        action="store_true",
        help="Enable full verbose debugging streams"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute harvest pipelines strictly printing structures to console without database mutation rules."
    )

    parser.add_argument(
        "--gui", "-gui",
        action="store_true",
        help="Execute harvest pipelines inside the PySide6 Graphical Interface."
    )

    args = parser.parse_args()

    # Set logging thresholds based on verbosity flag
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    logger.info("Starting Bazaar Sourcing Pipeline Initialization Core...")

    # 🛑 THE GATEKEEPER CHECK: Run tests if --dev is enabled
    if args.dev:
        if not run_development_gatekeeper():
            sys.exit(1)  # Hard abort immediately if any unit tests fail

    # 🌟 FIX: Instantiate runtime state contexts here so they exist for the routers below
    config = AppConfig()
    controller = AnalysisController(config=config)

    # --- Application Routing Window ---
    if args.gui:
        logger.info("Initializing PySide6 GUI Application Window Layout...")
        # Local import to save memory overhead if running headless CLI paths
        from PySide6.QtWidgets import QApplication

        app = QApplication(sys.argv)
        window = MainWindow(controller=controller, config=config)
        window.show()
        sys.exit(app.exec())
    else:
        if args.action == "harvest-active":
            controller.run_harvest(mode="active", dry_run=args.dry_run)

        elif args.action == "harvest-historical":
            controller.run_harvest(mode="historical", dry_run=args.dry_run)

        elif args.action == "all":
            controller.run_harvest(mode="active", dry_run=args.dry_run)
            controller.run_harvest(mode="historical", dry_run=args.dry_run)
            controller.run_consolidation()
        else:
            if not args.action:
                parser.print_help()

if __name__ == "__main__":
    main()
