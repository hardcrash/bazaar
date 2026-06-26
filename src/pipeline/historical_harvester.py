# src/pipeline/historical_harvester.py

import logging
from src.utils/price_indexer import PriceBracketGenerator

logger = logging.getLogger("BazaarPipeline")

def run_historical_bracket_sweep(client, category_config: dict, query_string: str):
    """
    Orchestrates a historical harvest sweep by slicing the configuration bounds.

    category_config matches the parsed dict structure of a categories.yaml entry:
      price_min: 100
      price_max: 800
      category_id: "164" (or None if wide-funnel harvesting)
    """
    min_bound = float(category_config.get("price_min", 30.0))
    max_bound = float(category_config.get("price_max", 500.0))
    category_id = category_config.get("category_id")

    # Generate $50 steps. For highly active segments like the 5800X,
    # you can reduce step to 25.0 if the total count still breaches 1,000.
    brackets = self._generate_price_brackets(min_p, max_p, step=10.0)

    all_extracted_items = []
    logger.info(f"[🚀] Sliced execution range [{min_bound}..{max_bound}] into {len(brackets)} search brackets.")

    for low, high in brackets:
        logger.info(f"[📡] Harvesting Bracket: ${low:.2f} to ${high:.2f}...")

        offset = 0
        limit = 100
        bracket_exhausted = False

        while not bracket_exhausted:
            # Call your updated EbayClient method
            items = client.search_historical_sales(
                query=query_string,
                limit=limit,
                offset=offset,
                min_price=low,
                max_price=high,
                category_id=category_id,
                dry_run=False  # Set to True if testing URL parameters
            )

            if not items:
                # No more items returned, or an error occurred
                bracket_exhausted = True
                break

            all_extracted_items.extend(items)

            # Move to next page chunk
            offset += limit

            # Safety check: If we somehow still hit index 1,000 inside a single bracket,
            # break to prevent an API 400 bad request error loop.
            if offset >= 1000:
                logger.warning(f"[⚠️] Bracket ${low:.2f}-${high:.2f} crossed the 1,000 item wall. Slices are too wide!")
                bracket_exhausted = True

            # If the API returned fewer items than the max limit, we've exhausted this bracket
            if len(items) < limit:
                bracket_exhausted = True

    logger.info(f"[✅] Bracket sweep complete. Total entries pulled across all slices: {len(all_extracted_items)}")
    return all_extracted_items
