# src/ui/main_window.py

import os
import json
import yaml
from PySide6.QtWidgets import QMainWindow, QTableWidgetItem, QHeaderView, QComboBox, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QStandardItemModel, QStandardItem
from src.ui.ui_main_window import Ui_MainWindow

class MainWindow(QMainWindow):
    def __init__(self, controller, search_config):
        super().__init__()

        self.config_path = "config.yaml"

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Apply the geometry via a zero-delay timer
        QTimer.singleShot(0, self.load_window_geometry)

        self.controller = controller
        self.search_config = search_config

        # Track the active category currently being inspected
        self.current_category = "CPU"

        # 1. Page Flipping Actions
        self.ui.action_dashboard.triggered.connect(lambda: self.ui.main_stack.setCurrentWidget(self.ui.dashboard_page))
        self.ui.action_sourcing.triggered.connect(lambda: self.ui.main_stack.setCurrentWidget(self.ui.sourcing_page))
        self.ui.action_historical.triggered.connect(lambda: self.ui.main_stack.setCurrentWidget(self.ui.historical_page))

        # 2. 🌟 RUNTIME UI INJECTION: Add a Timeframe Selector Combobox right above the table
        self.timeframe_selector = QComboBox()
        self.timeframe_selector.addItems(["Yearly View", "Last Full Month"])
        self.timeframe_selector.setStyle(self.style()) # Inherit application stylesheet

        # Insert selector directly into the vertical layout between the Title Label and the Table
        self.ui.verticalLayout_results_historical.insertWidget(1, self.timeframe_selector)
        self.timeframe_selector.currentTextChanged.connect(self.on_timeframe_changed)

        # 3. Setup Navigation Trees
        self.historical_tree_model = QStandardItemModel()
        self.ui.tree_categories_historical.setModel(self.historical_tree_model)
        self.ui.tree_categories_historical.clicked.connect(self.on_historical_category_selected)

        self.populate_category_trees()
        self.auto_select_default_category()

    def load_window_geometry(self):
        """Loads and applies geometry after the layout engine has stabilized."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                w = config.get("window_width")
                h = config.get("window_height")
                if w and h:
                    print(f"[DEBUG] Forcing geometry to: {w}x{h}")
                    self.resize(w, h)

    def closeEvent(self, event):
        """Overrides the window close event to record size."""
        """Triggered when the user clicks 'X'."""
        print("[DEBUG] Close event triggered. Saving window geometry...")

        size = self.size()
        config_data = {}

        # Load existing config to not overwrite other settings
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}

        # Update geometry
        config_data["window_width"] = size.width()
        config_data["window_height"] = size.height()

        # Save back to file
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)

        event.accept()

    def populate_category_trees(self):
        self.historical_tree_model.clear()
        categories = self.controller.allowed_categories if hasattr(self.controller, 'allowed_categories') else ["CPU"]
        root_node = self.historical_tree_model.invisibleRootItem()
        for cat in categories:
            item = QStandardItem(str(cat))
            item.setEditable(False)
            root_node.appendRow(item)

    def auto_select_default_category(self):
        if self.historical_tree_model.rowCount() > 0:
            first_index = self.historical_tree_model.index(0, 0)
            self.ui.tree_categories_historical.setCurrentIndex(first_index)
            self.on_historical_category_selected(first_index)

    def on_historical_category_selected(self, index):
        category_name = index.data(Qt.DisplayRole)
        if category_name:
            self.current_category = category_name
            self.refresh_historical_view()

    def on_timeframe_changed(self, text):
        """Triggered when the user swaps between Yearly and Monthly options."""
        self.refresh_historical_view()

    def refresh_historical_view(self):
        """Dispatches the data loading pipeline using current state selections."""
        # Map GUI selector to database timeframe keys
        ui_choice = self.timeframe_selector.currentText()
        target_timeframe = "past_year" if "Yearly" in ui_choice else "past_month"

        self.populate_pivoted_historical_table(self.current_category, target_timeframe)

    def populate_pivoted_historical_table(self, category, timeframe):
        cache_file = f"{category}_consolidated_bazaar_metrics.json"
        table = self.ui.table_historical_data
        table.setRowCount(0)

        if not os.path.exists(cache_file):
            return

        try:
            with open(cache_file, "r") as f:
                raw_data = json.load(f)
        except Exception:
            return

        pivoted_data = {}
        for row in raw_data:
            if row.get("timeframe") != timeframe:
                continue
            model = row.get("model_name")
            cond = str(row.get("condition_type", "")).lower()
            cond_key = "used" if cond in ["working", "used", "pre-owned"] else "broken"
            if model not in pivoted_data:
                pivoted_data[model] = {"used": {}, "broken": {}}
            pivoted_data[model][cond_key] = row

        columns_schema = [
            ("model_name", None, "Model Identifier"),
            ("delta", "combined", "Net Spread"),
            ("total_units", "broken", "# Broken"),
            ("avg_item_price", "broken", "Br. Avg"),
            ("total_units", "used", "# Used"),
            ("avg_item_price", "used", "Us. Avg"),
        ]

        table.setColumnCount(len(columns_schema))
        table.setHorizontalHeaderLabels([col[2] for col in columns_schema])
        table.setRowCount(len(pivoted_data))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        for row_idx, (model_name, conditions) in enumerate(pivoted_data.items()):
            for col_idx, (field_key, cond_group, _) in enumerate(columns_schema):

                is_numeric = False
                val = 0.0
                display_text = "-"

                if cond_group is None:
                    display_text = model_name
                elif cond_group == "combined":
                    val = self.get_net_liquidation_delta(model_name, pivoted_data)
                    display_text = f"${val:,.2f}"
                    is_numeric = True
                else:
                    metrics = conditions.get(cond_group, {})
                    raw_val = metrics.get(field_key)
                    if raw_val is not None:
                        val = float(raw_val)
                        display_text = f"{int(val):,}" if field_key == "total_units" else f"${val:,.2f}"
                        is_numeric = True

                cell_item = QTableWidgetItem(display_text)
                cell_item.setFlags(cell_item.flags() ^ Qt.ItemIsEditable)

                if is_numeric:
                    # Logic for colors
                    if cond_group == "combined":
                        cell_item.setForeground(Qt.green if val >= 0 else Qt.red)
                    elif val < 0:
                        cell_item.setForeground(Qt.red)
                    cell_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    cell_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                table.setItem(row_idx, col_idx, cell_item)

        print(f"[🎨] Swapped view to [{timeframe}]. Rendered {len(pivoted_data)} models.")

    def get_net_liquidation_delta(self, model_name, pivoted_data):
        data = pivoted_data.get(model_name, {})
        used = data.get("used", {})
        broken = data.get("broken", {})

        def get_realistic_price(metrics):
            # 1. Start with the Median (most robust statistic)
            price = metrics.get("med_item_price", 0.0)

            # 2. Sanity Filter: If median is 0 or absurdly high (bulk lot detection),
            # fall back to min_item_price.
            if price <= 0 or price > 800.0: # Adjust 800.0 based on your CPU cap
                price = metrics.get("min_item_price", 0.0)

            return price

        resell_price = get_realistic_price(used)
        purchase_price = get_realistic_price(broken)

        if resell_price == 0 or purchase_price == 0:
            return 0.0

        # Proven Formula: (Resell * 0.87) - Purchase - Parts ($15) - Shipping
        # Use the average shipping cost from the JSON if available
        resell_shipping = used.get("avg_shipping_cost", 15.0)
        purchase_shipping = broken.get("avg_shipping_cost", 15.0)

        # Calculation
        resell_net = resell_price * 0.87
        total_overhead = purchase_price + 15.00 + resell_shipping + purchase_shipping

        return resell_net - total_overhead
