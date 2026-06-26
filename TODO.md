# Bazaar Development Roadmap

## TODO: Refine Stage 2 MSKU Parsing & Outlier Filtering

* **Fix Heuristic Bleed on Hardware Defect Flags:** The current `has_bent_pins` check executes a page-wide string scan on the raw HTML. If a multi-sku listing contains a single broken unit or boilerplate defect text in the terms, all extracted variations are falsely marked as `Pins: True`.
* **Solution:** Scope the regex/keyword heuristics tightly to the specific variation text block or individual item condition description container instead of the global `html_content`.


* **Handle MSKU Initial Target Discrepancy:** Multi-variation listings are slipping through Stage 1 bracket bounds because the parent card advertised the lowest variant's price (e.g., a 3700X for $99.90). Once Stage 2 unmasks the true target variant cost (e.g., the 5800X at $202.50), it violates the active historical slicing filter ($115–$120).
* **Solution:** Ensure the database/analysis pipeline explicitly drops or routes unmasked items that fall outside the active price bracket to prevent statistical skewing in the analytics window.



---

## Data Infrastructure Roadmap

### Phase 1: Foundation & Persistence


* [ ] **Implement `DatabaseManager`:** Create a robust session-based manager ensuring connection persistence and `INSERT OR REPLACE` logic for active data.

### Phase 2: Ingestion Engine

* [ ] **Implement `eBayApiClient`:** Develop the official API interface using OAuth2 credentials to replace current scraping logic.
* [ ] **Data Validation Layer:** Implement `Pydantic` models to validate and sanitize incoming eBay JSON before it is committed to the database.

### Phase 3: Data Consolidation & Analytics

* [ ] **Historical Harvester Implementation: Refine src/pipeline/historical_harvester.py to utilize ebay_scrape_client.py for backfilling data, ensuring the results are mapped to the standard MarketItem model before database insertion.

* [ ] **Historical Aggregator Service: Develop the consolidation logic that queries the analyzed_market_items table to compute:
  
  Price Benchmarks: Calculate Mean, Median, and Mode for pricing across defined categories.
  
  Defect Segregation: Count and group units marked is_for_parts_or_not_working vs. used / refurbished to establish "risk-adjusted" market value.

* [ ] **Unit Velocity Tracker: Implement the calculation logic for "Days on Market" (DoM) utilizing item_start_date and date_fetched to identify stagnant vs. high-velocity inventory.


---
