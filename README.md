# Bazaar Engine README.md

## ⚙️ Configuration & Secrets

Secrets and runtime configurations are managed via YAML files in the root directory and the settings/ folder.

### 1. Secrets (config_credentials.yaml)

Manage your API/OAuth connections here:

sandbox:
client_id: "YOUR_SANDBOX_CLIENT_ID"
client_secret: "YOUR_SANDBOX_CLIENT_SECRET"

production:
client_id: "YOUR_PRODUCTION_CLIENT_ID"
client_secret: "YOUR_PRODUCTION_CLIENT_SECRET"

### 2. Runtime Settings (config.yaml)

Define your runtime parameters here:

use_sandbox: false
database:
path: "bazaar.db"

---

## 🏗️ Architecture Overview

The engine is structured as a modular package, separating cross-platform data acquisition from business logic.

### Core Modules

* src/api/: The Data Acquisition Layer. Contains ebay_client.py (Official API) and ebay_scrape_client.py (Historical/Fallback scraper).
* src/analysis/: The Classification Layer. Uses a Strategy Pattern to apply specific parsing rules via analysis_strategy_factory.py.
* src/pipeline/: The ETL Engine. Handles the ingestion and historical aggregation flows.
* src/database/: The Persistence Layer. Uses SQLAlchemy to manage the lifecycle of market items.
* settings/: The Knowledge Base. Defines categorical hierarchies, parsing policies, and SQL schemas.

---

## 🚀 Adding New Hardware Targets

Target definition is handled within the settings/ directory:

1. Define Category: Update settings/categories.yaml to register your new hardware vertical.
2. Define Policy: Adjust settings/policies.yaml to set price thresholds or noise-word exclusions.
3. Implement Strategy: If the hardware requires unique parsing, add a new strategy class in src/analysis/strategy/ and register it in analysis_strategy_factory.py.

---

## 🛠️ Pipeline Execution

The engine splits tasks between live market monitoring and historical analysis:

* Live Cycle (src/api/ebay/ebay_client.py): Connects to the official eBay Browse API for real-time monitoring.
* Historical Cycle (src/api/ebay/ebay_scrape_client.py): Uses the scrape client for backfilling data.

### Running the Engine

Execute your harvest and analysis loops:

python main.py harvest

python check_db.py

---

## ✅ Development & Testing

Your test/ directory is aligned with your package structure. Run your pre-flight checks in Dev Mode:



Here is the project structure for `bazaar-data` in Markdown format:

### Project Directory Structure

.
├── bazaar.db
├── check_db.py
├── check_limits.py
├── config_credentials.yaml
├── config.yaml
├── CPU_consolidated_bazaar_metrics.json
├── main.py
├── Motherboard_High_consolidated_bazaar_metrics.json
├── Motherboard_Mid_consolidated_bazaar_metrics.json
├── README.md
├── requirements.txt
├── settings/
│   ├── categories.yaml
│   ├── policies.yaml
│   ├── queries.sql
│   └── schema.sql
├── src/
│   ├── analysis/
│   │   ├── analysis_controller.py
│   │   ├── **init**.py
│   │   ├── strategy/
│   │   │   ├── analysis_strategy_factory.py
│   │   │   ├── base_strategy.py
│   │   │   ├── cpu_strategy.py
│   │   │   ├── **init**.py
│   │   │   └── motherboard_strategy.py
│   │   └── transformer.py
│   ├── api/
│   │   ├── ebay/
│   │   │   ├── ebay_client.py
│   │   │   ├── ebay_scrape_client.py
│   │   │   └── **init**.py
│   │   ├── **init**.py
│   │   ├── jawa/
│   │   └── mercari/
│   ├── core/
│   │   └── models.py
│   ├── database/
│   │   ├── db_manager.py
│   │   └── **init**.py
│   ├── **init**.py
│   ├── pipeline/
│   │   ├── historical_harvester.py
│   │   └── **init**.py
│   ├── ui/
│   │   ├── dialogs/
│   │   │   └── **init**.py
│   │   ├── **init**.py
│   │   ├── main_window.py
│   │   ├── main_window.ui
│   │   ├── ui_main_window.py
│   │   └── widgets/
│   │       └── **init**.py
│   └── util/
│       ├── config_loader.py
│       ├── **init**.py
│       └── price_indexer.py
└── test/
├── conftest.py
├── test_config_integrity.py
├── test_cpu_strategy.py
├── test_ebay_scrape_client.py
├── test_regex_robustness.py
├── test_sanitation.py
└── test_scrape_resiliency.py

---

*Note: `__pycache__` and `.venv` directories have been omitted for clarity.*

                       ┌─────────────────────────┐
                       │   AnalysisController    │
                       └────────────┬────────────┘
                                    │
                ┌───────────────────┴───────────────────┐
                │                                       │
      ┌─────────▼───────────────┐          ┌────────────▼──────────────┐
      │  Live Active Cycle      │          │    Historical Cycle       │
      ├─────────────────────────┤          ├───────────────────────────┤
      │ • Source: eBay API      │          │ • Source: Scrape Client   │
      │ • Scope: Open Listings  │          │ • Scope: Past Sold Data   │
      │ • Intent: Price Sniping │          │ • Intent: Indexing Values │
      └─────────┬───────────────┘          └────────────┬──────────────┘
                │                                       │
                └───────────┬───────────────────────────┘
                            ▼
              ┌───────────────────────────┐
              │  Transformer / Sanitizer  │
              │ (src/analysis/transformer)│
              └─────────────┬─────────────┘
                            │
              ┌─────────────▼─────────────┐
              │   Strategy Classification │
              │ (src/analysis/strategy/..)│
              └─────────────┬─────────────┘
                            │
              ┌─────────────▼─────────────┐
              │    Database Persistence   │
              │ (src/database/db_manager) │
              └───────────────────────────┘

pytest test/
