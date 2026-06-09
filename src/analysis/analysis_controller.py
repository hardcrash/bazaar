import time
import os
from src.api.ebay.ebay_scrape_client import EbayScrapeClient
from src.analysis.transformer import MarketItemTransformer
from src.database.db_manager import DatabaseManager
from src.analysis.strategy.cpu_strategy import CPUStrategy

class AnalysisController:
    def __init__(self, config, target_category_filter=None):
        self.config = config
        self.ebay = EbayScrapeClient(config=config)
        self.db_manager = DatabaseManager(config=config)
        self.search_registry = config.categories
        self.target_category_filter = target_category_filter.upper() if target_category_filter else None

    def _generate_price_brackets(self, min_price, max_price, step=10.0):
        """
        Slices a broad price range into explicit sub-brackets to ensure
        the engine never passes more than 1,000 matches down to a single pagination sequence.
        """
        low_bound = float(min_price if min_price is not None else 0.0)
        high_bound = float(max_price if max_price is not None else 9999.0)

        brackets = []
        current_low = low_bound

        while current_low < high_bound:
            current_high = current_low + step
            if current_high > high_bound:
                current_high = high_bound

            brackets.append((current_low, current_high))
            current_low = current_high + 0.01

        return brackets

    def run_harvest(self, mode="historical", dry_run=True):
        start_time = time.time()

        print(f"[🚀] Launching DRY RUN [{mode.upper()}] Harvesting Sweep...")

        cpu_config = self.config.categories.get("CPU", {})
        if not cpu_config:
            print("[⚠️] Warning: 'CPU' section not found in categories layout configuration.")
            return

        strategy = CPUStrategy(config_dict=cpu_config)

        if mode.lower() == "historical":
            min_price = strategy.hist_min_price_used
            max_price = strategy.hist_max_price_used
            bracket_size = strategy.hist_step_size
            category_id = strategy.hist_category_id
        else:
            min_price = strategy.active_min_price
            max_price = strategy.active_max_price
            bracket_size = strategy.active_step_size
            category_id = strategy.active_category_id

        models = strategy.valid_models
        search_format = strategy.search_format
        exclusions = " ".join([f"-{word}" for word in strategy.blacklist_words])

        metrics = {
            "total_items_harvested": 0,
            "total_requests_made": 0,
            "successful_brackets": 0,
            "model_breakdown": {model: 0 for model in models},
            "msku_listings_found": 0,
            "variants_extracted": 0
        }

        all_scraped_items = []

        for model in models:
            base_query = search_format.format(model=model)
            search_str = f"{base_query} {exclusions}".strip()

            print(f"\n[📡] Mode [{mode.upper()}] -> Target: '{search_str}'")

            current_min = min_price
            while current_min < max_price:
                current_max = current_min + bracket_size
                if current_max > max_price:
                    current_max = max_price

                print(f"  ├─ 💶 Slicing Bracket Range: ${current_min:.2f} to ${current_max:.2f}")

                metrics["total_requests_made"] += 1

                raw_items = self.ebay.search_historical_sales(
                    query=search_str,
                    min_price=current_min,
                    max_price=current_max,
                    category_id=category_id,
                    model_name=model,
                    strategy=strategy
                )

                if isinstance(raw_items, list):
                    item_count = len(raw_items)
                    metrics["total_items_harvested"] += item_count
                    metrics["model_breakdown"][model] += item_count
                    metrics["successful_brackets"] += 1
                    all_scraped_items.extend(raw_items)

                current_min = current_max + 0.01

        msku_queue = [item for item in all_scraped_items if item.process_state == "PENDING_DEEP_HARVEST"]
        metrics["msku_listings_found"] = len(msku_queue)

        clean_final_items = [item for item in all_scraped_items if item.process_state != "PENDING_DEEP_HARVEST"]

        if msku_queue:
            print(f"\n[🔍] Stage 2: Deep Harvesting {len(msku_queue)} multi-variation menu listings...")

            for msku_item in msku_queue:
                print(f"  ├─► Processing Multi-Sku Matrix for Item ID: {msku_item.item_id}")

                raw_html = self.ebay.fetch_raw_item_page(msku_item.item_url)

                if raw_html:
                    parsed_variants = self.ebay.parse_msku_item_page(raw_html, base_item=msku_item)

                    if parsed_variants:
                        for variant in parsed_variants:
                            variant_model = strategy.extract_model(variant.title.upper(), model.upper())

                            if variant_model == model.upper():
                                metrics["variants_extracted"] += 1
                                clean_final_items.append(variant)
                            else:
                                print(f"        ⚠️ Filtering out cross-bleed option: '{variant.title}' (Not target {model})")
                else:
                    print(f"      ❌ Skipping deep processing loop for item {msku_item.item_id} due to network proxy failure.")

        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)

        print("\n" + "="*50)
        print("📊 HARVESTING PIPELINE EXECUTION SUMMARY")
        print("="*50)
        print(f" Execution Mode     : {mode.upper()} {'(DRY RUN)' if dry_run else '(LIVE RUN)'}")
        print(f" Total Duration     : {int(minutes)}m {seconds:.2f}s")
        print(f" Total Requests Made: {metrics['total_requests_made']} API calls")
        print(f" Complete Brackets  : {metrics['successful_brackets']} scanned")
        print(f" Total Items Scraped: {metrics['total_items_harvested']} items")
        print(f" MSKU Links Flagged : {metrics['msku_listings_found']} items queued")

        print("\n📈 BREAKDOWN BY TARGET CHIP MODEL:")
        for chip_model, count in metrics["model_breakdown"].items():
            print(f"  ├─ Ryzen {chip_model:<8} : {count} data objects extracted")

        print("-"*50)
        if metrics["total_requests_made"] > 0:
            avg_items = metrics["total_items_harvested"] / metrics["total_requests_made"]
            print(f" Yield Efficiency    : {avg_items:.1f} items per API request")
        print("="*50 + "\n")
