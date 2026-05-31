# main.py
import sys
import json
from src.util.config_loader import load_yaml
from src.database.db_manager import DatabaseManager
from src.api.ebay.ebay_client import EbayClient
from src.analysis.parser import ComponentParserRegistry  # Using our dynamic strategy registry
from src.analysis.curator import MarketCurator
from src.analysis.dashboard_aggregator import DashboardAggregator
from src.analysis.consolidation_pipeline import run_consolidation_pipeline

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
    creds = load_yaml("credentials.yaml")
    db_name = config.get("database_name", "bazaar.db")

    # Load search parameters & strategies layout file
    with open("searches.json", "r") as f:
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

        # Instantiating our dynamic strategy engine mapper rather than single class parser
        parser_factory = ComponentParserRegistry("parser_config.json")

        global_settings = search_registry.get("global_settings", {})
        MAX_ITEMS_PER_SWEEP = global_settings.get("max_items_per_sweep", 1000)
        PAGE_SIZE = global_settings.get("page_size", 100)

        active_targets = search_registry.get("active_pipeline_targets", search_registry.get("active_categories", []))

        for target_key in active_targets:
            cat_info = search_registry["categories"].get(target_key)
            if not cat_info:
                print(f"⚠️ Target key '{target_key}' missing configuration definitions. Skipping.")
                continue

            base_query = cat_info["base_query"]
            parser_cat = cat_info["parser_category"]

            # Resolve our parsing strategy dynamically from our factory
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

                            # Execute the polymorphic title parse step
                            brand, model_name = "UNKNOWN", None
                            if strategy:
                                brand, model_name = strategy.parse_title(title.upper())

                            # Standard fallback if patterns couldn't capture details
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
                                is_sold=False
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

        # 1. Collect all your active category parser strings into a single list
        active_categories = []
        for target_key in search_registry.get("active_categories", []):
            cat_info = search_registry["categories"].get(target_key)
            if cat_info and "parser_category" in cat_info:
                active_categories.append(cat_info["parser_category"])

        # 2. Fire the consolidation pipeline ONCE with the full list
        if active_categories:
            run_consolidation_pipeline(categories=active_categories)

    # ==========================================
    # PHASE 3: METRICS RECALCULATION
    # ==========================================
    if command in ["metrics", "all"]:
        print("\n[📊] Triggering Dashboard Metrics Aggregation...")
        unique_models = db.get_all_snapshot_models()
        print(f"  ▪ Found {len(unique_models)} distinct components in your database.")

        for model in unique_models:
            if model != "UNKNOWN":
                aggregator.calculate_historical_metrics(model, timeframe='past_month')
                aggregator.calculate_historical_metrics(model, timeframe='past_year')
        print("[+] Metrics calculations complete.")

    if command not in ["harvest", "consolidate", "metrics", "all"]:
        print_usage()

if __name__ == "__main__":
    main()
