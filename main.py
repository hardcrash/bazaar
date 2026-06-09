import sys
import argparse
from PySide6.QtWidgets import QApplication

# 🌟 This is the only import you need from config_loader!
from src.util.config_loader import AppConfig
from src.analysis.analysis_controller import AnalysisController
from src.ui.main_window import MainWindow

def main():
    parser = argparse.ArgumentParser(description="Bazaar Sourcing Data Pipeline Engine")
    parser.add_argument("action", nargs="?", choices=["harvest-active", "harvest-historical", "analyze", "all"])
    parser.add_argument("--category", type=str, default=None, help="Isolate execution to a specific target category.")
    parser.add_argument("-gui", "--gui", action="store_true", help="Launch GUI interface application layout.")

    # 🌟 Added Dry-Run Flag
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute harvest pipelines strictly printing structures to console without database mutation rules."
    )

    args = parser.parse_args()

    # Initialize unified configuration
    config = AppConfig(settings_dir="settings")

    # Instantiate controller architecture
    controller = AnalysisController(
        config=config,
        target_category_filter=args.category
    )

    # Route execution logic matrix
    if args.gui:
        print("[🖥️] Initializing PySide6 Application Window...")
        app = QApplication(sys.argv)
        window = MainWindow(controller=controller, config=config)
        window.show()
        sys.exit(app.exec())
    else:
        if args.action == "harvest-active":
            controller.run_harvest(mode="active", dry_run=args.dry_run)

        if args.action == "harvest-historical":
            controller.run_harvest(mode="historical", dry_run=args.dry_run)

        if args.action == "all":
            controller.run_harvest(mode="active", dry_run=args.dry_run)
            controller.run_harvest(mode="historical", dry_run=args.dry_run)
            controller.run_consolidation()

if __name__ == "__main__":
    main()
