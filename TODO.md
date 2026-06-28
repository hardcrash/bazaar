Bazaar Development Roadmap

## 🚀 Upcoming Enhancements

### Data Processing & Normalization
- [ ] **Implement Core Title Sanitization Engine**
  - **Context:** Currently, `HistoricalMarketItem.title` and `ActiveMarketItem.title` default to the raw, noisy marketplace title string (`raw_title`). 
  - **Objective:** Create a dedicated string scrubbing utility (e.g., `src/util/text_cleaner.py`) to parse out distracting fluff words, emoji, shipping tags, and formatting noise.
  - **Target Deliverable:** Populate the normalized `.title` attribute with clean, uniform strings (e.g., converting `"🔥 MINT !!! AMD Ryzen 7 5800X CPU 8-Core 3.8GHz Processor AM4 Tray Fast Ship"` into `"AMD Ryzen 7 5800X"`).
  - **Impact:** Drastically improves string matching accuracy, automated categorization passes, and clean UI rendering in the PySide6 layout.
  
🚀 High-Priority: Active Listings & Resilience

    [X] Migrate Selection Logic: Move EBAY_SELECTORS_MATRIX from the client class into a standalone config/selectors.yaml file for decoupled maintenance.
    [X] Refactor Extraction Methods: Update _extract_title, _extract_price, etc., in ebay_scrape_client.py to iterate through the new selector matrix dynamically rather than using hard-coded lookups.
    [ ] Active Listing Pipeline: Pivot development to the Active Listings module using the official eBay API (Trading/Finding APIs) to preserve scraper credits.
    [ ] Resilience Audit: Perform a file-by-file review of existing modules to improve error handling and expand unit test coverage (targeting 90%+ path coverage).

📊 Data Infrastructure & Analytics

    [X] Database Refinement: Cleanup the historical_market_items table (prune duplicates, normalize schema, enforce constraints).
    [ ] Local Metrics Troubleshooting: Develop a "Offline Analysis" routine to compute historical_metrics directly from current bazaar.db entries without triggering outbound API/scraper calls.
    [ ] Class Architecture Review: Identify and refactor "oddball" classes to improve inheritance and reduce complexity (e.g., merging redundant provider classes).

🖥️ Future Roadmap

    [X] Phase 1: Foundation & Persistence: Implement DatabaseManager with session-based, persistent connection handling and UPSERT logic.
    [ ] Phase 2: Data Consolidation: Finalize the Historical Aggregator Service (calculating Benchmarks, Defect Segregation, and Velocity).
    [ ] Phase 3: Front-End: Develop PySide6 dashboard interface for real-time visualization of market velocity and price benchmarks.