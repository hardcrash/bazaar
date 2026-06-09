# src/analysis/analysis_controller.py
import time
from src.api.ebay.ebay_scrape_client import EbayScrapeClient
from src.database.db_manager import DatabaseManager
from src.analysis.strategy.analysis_strategy_factory import AnalysisStrategyFactory

class AnalysisController:
    def __init__(self, config, target_category_filter="CPU"):
        self.config = config
        self.ebay = EbayScrapeClient(config=config)
        self.db_manager = DatabaseManager(config=config)
        self.target_category = target_category_filter.upper() if target_category_filter else "CPU"

    def run_harvest(self, mode="historical", dry_run=True):
        start_time = time.time()
        print(f"[🚀] Launching DRY RUN [{mode.upper()}] Harvesting Sweep for category: {self.target_category}")

        # 🌟 Factory provides the decoupled strategy object based entirely on the active mode!
        try:
            strategy = AnalysisStrategyFactory.get_strategy(self.target_category, mode, self.config)
        except ValueError as e:
            print(f"[⚠️] Configuration Error: {e}")
            return

        min_price, max_price = strategy.price_bounds
        bracket_size = strategy.step_size
        category_id = strategy.category_id
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
            print(f"\n[📡] Target: '{search_str}' (Category ID: {category_id})")

            current_min = min_price
            while current_min < max_price:
                current_max = min(current_min + bracket_size, max_price)

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

        # Process MSKU variations
        msku_queue = [item for item in all_scraped_items if item.process_state == "PENDING_DEEP_HARVEST"]
        metrics["msku_listings_found"] = len(msku_queue)
        clean_final_items = [item for item in all_scraped_items if item.process_state != "PENDING_DEEP_HARVEST"]

        if msku_queue:
            print(f"\n[🔍] Stage 2: Deep Harvesting {len(msku_queue)} multi-variation listings...")
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
                                print(f"        ⚠️ Filtering out cross-bleed option: '{variant.title}'")

        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)

        print("\n" + "="*50)
        print(f"📊 {self.target_category} HARVESTING PIPELINE SUMMARY")
        print("="*50)
        print(f" Duration        : {int(minutes)}m {seconds:.2f}s")
        print(f" Total Requests  : {metrics['total_requests_made']} API calls")
        print(f" Items Scraped   : {metrics['total_items_harvested']} records")
        print("="*50 + "\n")
