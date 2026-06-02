import sys
import os
import json
import sqlite3
from src.util.config_loader import load_yaml
from src.database.db_manager import DatabaseManager
from src.api.ebay.ebay_client import EbayClient
from src.analysis.parser import ComponentParserRegistry  # Dynamic strategy registry
from src.analysis.curator import MarketCurator
from src.analysis.dashboard_aggregator import DashboardAggregator
from src.analysis.ingest_pipeline import ingest_historical_metrics

def print_usage():
    print("""
⚖️  Bazaar Engine Command Interface ⚖️
Usage: python main.py [command]

Commands:
  harvest     - Sweeps live platforms using strategy declarations (Consumes API keys)
  consolidate - Executes the local heuristic validation strategy loop (Pure Local)
  metrics     - Triggers Dashboard calculations for historical data grids
  all         - Runs the entire end-to-end pipeline layout sequentially
""")

def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1].lower()

    # Load Configurations
    config = load_yaml("config.yaml")
    creds = load_yaml("config_credentials.yaml")
    db_name = config.get("database", {}).get("path", "bazaar.db")

    # Extract allowed categories from config.yaml directly
    market_rules = config.get("market_rules", {})
    allowed_categories = market_rules.get("allowed_categories", ["CPU", "Motherboard"])

    # Load search parameters & strategies layout file
    with open("config_searches.json", "r") as f:
        search_registry = json.load(f)

    db = DatabaseManager(db_name)
    curator = MarketCurator(db_name)
    aggregator = DashboardAggregator(db_name)

    # ==========================================
    # PHASE 1: CONFIGURATION-DRIVEN LIVE API HARVESTING
    # ==========================================
    if command in ["harvest", "all"]:
        print("[🚀] Starting Configuration-Driven Ingestion Harvesting...")
        use_sandbox = config.get("use_sandbox", True)
        env_key = "sandbox" if use_sandbox else "production"

        ebay = EbayClient(
            client_id=creds[env_key]["client_id"],
            client_secret=creds[env_key]["client_secret"],
            sandbox=use_sandbox
        )

        # Instantiating dynamic strategy engine mapper
        parser_factory = ComponentParserRegistry("config_parser.json")

        global_settings = search_registry.get("global_settings", {})
        MAX_ITEMS_PER_SWEEP = global_settings.get("max_items_per_sweep", 1000)
        PAGE_SIZE = global_settings.get("page_size", 100)

        active_targets = search_registry.get("active_pipeline_targets", [])

        for target_key in active_targets:
            cat_info = search_registry["categories"].get(target_key)
            if not cat_info:
                continue

            base_query = cat_info["base_query"]
            parser_cat = cat_info["parser_category"]

            if parser_cat not in allowed_categories:
                print(f"⚠️ Category '{parser_cat}' is not in config.yaml allowed_categories. skipping stream execution.")
                continue

            strategy = parser_factory.get_strategy_for_category(parser_cat)

            for condition_label, condition_id in [("working", 3000), ("broken", 7000)]:
                search_str = f"{base_query} broken" if condition_id == 7000 else f"{base_query} used"
                print(f"\n[📡] Strategy Harvesting Category [{parser_cat}] -> Query: '{search_str}'")

                offset = 0
                total_harvested_for_query = 0

                while True:
                    try:
                        items = ebay.search_items(search_str, limit=PAGE_SIZE, offset=offset)

                        if not items:
                            print(f"  ▪ Reached end of market listings pool.")
                            break

                        print(f"  ▪ Page [Offset: {offset}]: Received {len(items)} units. Applying Strategy Parsing...")

                        for item in items:
                            title = item.get("title", "")
                            item_id = item.get("itemId")

                            brand, model_name = "UNKNOWN", None
                            if strategy:
                                brand, model_name = strategy.parse_title(title.upper())

                            if not model_name:
                                model_name = "UNKNOWN"

                            price = float(item.get("price", {}).get("value", 0.0))
                            shipping_options = item.get("shippingOptions", [])
                            shipping_cost = 0.0
                            if shipping_options:
                                cost_obj = shipping_options[0].get("shippingCost", {})
                                shipping_cost = float(cost_obj.get("value", 0.0))

                            total_cost = price + shipping_cost

                            if not curator.is_valid_discovery(model_name, title, total_cost, condition_id):
                                continue

                            db.insert_snapshot(
                                item_id=item_id,
                                model_name=model_name,
                                category=parser_cat,
                                title=title,
                                price=price,
                                shipping_cost=shipping_cost,
                                currency=item.get("price", {}).get("currency", "USD"),
                                condition_id=condition_id,
                                is_sold=True
                            )

                        total_harvested_for_query += len(items)

                        if len(items) < PAGE_SIZE:
                            print(f"  ✅ Complete inventory drained. Total extracted: {total_harvested_for_query} units.")
                            break

                        if total_harvested_for_query >= MAX_ITEMS_PER_SWEEP:
                            print(f"  ⚠️ Hard stop reached at safety ceiling ({MAX_ITEMS_PER_SWEEP} units). Shifting categories.")
                            break

                        offset += PAGE_SIZE

                    except Exception as e:
                        print(f"  ❌ API Strategy Exception on sweep '{search_str}' at offset {offset}: {e}")
                        break

# ==========================================
    # PHASE 2: LOCAL CONSOLIDATION
    # ==========================================
    if command in ["consolidate", "all"]:
        print("\n[🤖] Initializing Heuristic Strategy Consolidation Loop...")

        # 1. Extract unique active categories based on configuration filters
        active_categories = sorted(list({
            search_registry["categories"][tk]["parser_category"]
            for tk in search_registry.get("active_pipeline_targets", [])
            if tk in search_registry.get("categories", {})
            and search_registry["categories"][tk].get("parser_category") in allowed_categories
        }))

        agent_config = config.get("agent", {})
        base_cache_file = agent_config.get("cache_output_file", "consolidated_bazaar_metrics.json")

        # Open dedicated Phase 2 standalone connection coordinates
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # 2. Loop through each isolated hardware segment category
        for cat in active_categories:
            cat_specific_file = f"{cat}_{base_cache_file}"
            print(f"  ▪ Isolating validation arrays for category [{cat}] -> Target: {cat_specific_file}")

            # 🌟 STEP A: Find every distinct model name belonging strictly to this category tier
            cursor.execute("""
                SELECT DISTINCT model_name
                FROM market_snapshots
                WHERE category = ? AND is_sold = 1
            """, (cat,))

            discovered_models = [row[0] for row in cursor.fetchall() if row[0] != "UNKNOWN"]

            if not discovered_models:
                print(f"    ⚠️ Warning: No valid historical snapshots found in DB for category [{cat}]")
                continue

            # 🌟 STEP B: Cascade calculate metrics for every isolated model name discovered
            print(f"    🔄 Recalculating metrics for {len(discovered_models)} models...")
            for model in discovered_models:
                # Executes your internal aggregator queries and saves them straight to the DB table
                aggregator.calculate_historical_metrics(model_name=model, timeframe='past_month')

            # 🌟 STEP C: Pull down the freshly calculated dataset back out of historical_metrics
            cursor.execute("""
                SELECT model_name, timeframe, condition_type, total_units,
                       min_item_price, max_item_price, avg_item_price,
                       avg_shipping_cost, avg_total_cost, last_updated
                FROM historical_metrics
                WHERE model_name IN ({seq})
            """.format(seq=','.join(['?'] * len(discovered_models))), discovered_models)

            columns = [col[0] for col in cursor.description]
            category_metrics_matrix = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # 🌟 STEP D: Lock the final matrix down to its dedicated dynamic JSON disk target
            if category_metrics_matrix:
                with open(cat_specific_file, "w") as f:
                    json.dump(category_metrics_matrix, f, indent=4)
                print(f"    ✅ Cleanly wrote isolated metrics matrix to {cat_specific_file} ({len(category_metrics_matrix)} rows)")
            else:
                print(f"    ⚠️ Warning: No metric records captured from table space for category [{cat}]")

        # Close out resource dependencies
        conn.close()

if __name__ == "__main__":
    main()
