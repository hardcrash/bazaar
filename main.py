import sys
import argparse
import os
from loguru import logger
from PySide6.QtWidgets import QApplication

from src.util.config_loader import AppConfig
from src.analysis.analysis_controller import AnalysisController
from src.ui.main_window import MainWindow

def setup_logging(verbose: bool):
    """
    Configures application-wide log management routines.
    Clears standard defaults to tailor terminal noise controls.
    """
    # 1. Strip default root handlers
    logger.remove()

    # 2. Determine terminal log thresholds dynamically
    log_level = "DEBUG" if verbose or os.getenv("BAZAAR_DEBUG") else "INFO"

    # 3. Stream colorized output to standard error console
    logger.add(
        sys.stderr,
        level=log_level,
        # 🌟 Putting <level> right before {message} fixes the first line.
        # But to paint a MULTILINE string green, Loguru needs the level tags
        # explicitly surrounding the message token!
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        enqueue=True
    )

    # 4. Optional persistent storage layout
    logger.add(
        "logs/bazaar.log",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        compression="zip"
    )

    logger.debug(f"Logging core initialized engine state at level: {log_level}")

def main():
    parser = argparse.ArgumentParser(description="Bazaar Sourcing Data Pipeline Engine")
    parser.add_argument("action", nargs="?", choices=["harvest-active", "harvest-historical", "analyze", "all"])
    parser.add_argument("--category", type=str, default=None, help="Isolate execution to a specific target category.")
    parser.add_argument("-gui", "--gui", action="store_true", help="Launch GUI interface application layout.")

    # 🌟 Added Verbose Logging Flag
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Elevate terminal logging output details to DEBUG level state metrics."
    )

    # Dry-Run Flag
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute harvest pipelines strictly printing structures to console without database mutation rules."
    )

    args = parser.parse_args()

    # Initialize Logger Level Rules immediately post argument parsing
    setup_logging(verbose=args.verbose)

    logger.info("Starting Bazaar Sourcing Pipeline Initialization Core...")

    # Initialize unified configuration
    config = AppConfig(settings_dir="settings")

    # Instantiate controller architecture
    controller = AnalysisController(
        config=config,
        target_category_filter=args.category
    )

    # Route execution logic matrix
    if args.gui:
        logger.info("Initializing PySide6 GUI Application Window Layout...")
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
