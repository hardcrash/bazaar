Bazaar Development Roadmap
🚀 High-Priority: Active Listings & Resilience

    [ ] Migrate Selection Logic: Move EBAY_SELECTORS_MATRIX from the client class into a standalone config/selectors.yaml file for decoupled maintenance.

    [ ] Refactor Extraction Methods: Update _extract_title, _extract_price, etc., in ebay_scrape_client.py to iterate through the new selector matrix dynamically rather than using hard-coded lookups.

    [ ] Active Listing Pipeline: Pivot development to the Active Listings module using the official eBay API (Trading/Finding APIs) to preserve scraper credits.

    [ ] Resilience Audit: Perform a file-by-file review of existing modules to improve error handling and expand unit test coverage (targeting 90%+ path coverage).

📊 Data Infrastructure & Analytics

    [ ] Database Refinement: Cleanup the historical_market_items table (prune duplicates, normalize schema, enforce constraints).

    [ ] Local Metrics Troubleshooting: Develop a "Offline Analysis" routine to compute historical_metrics directly from current bazaar.db entries without triggering outbound API/scraper calls.

    [ ] Class Architecture Review: Identify and refactor "oddball" classes to improve inheritance and reduce complexity (e.g., merging redundant provider classes).

🖥️ Future Roadmap

    [ ] Phase 1: Foundation & Persistence: Implement DatabaseManager with session-based, persistent connection handling and UPSERT logic.

    [ ] Phase 2: Data Consolidation: Finalize the Historical Aggregator Service (calculating Benchmarks, Defect Segregation, and Velocity).

    [ ] Phase 3: Front-End: Develop PySide6 dashboard interface for real-time visualization of market velocity and price benchmarks.

Technical Note: DOM & API Strategy

To avoid further credit depletion, prioritize the API approach for active data. When returning to the scraping pipeline for historical gaps, ensure the fallback logic in _parse_ebay_html is fully implemented to leverage the new s-card grid structure identified in our diagnostic audit.

Would you like to start by isolating the EBAY_SELECTORS_MATRIX into the YAML config file, or should we begin the class relationship audit first to simplify the structure before refactoring the extraction methods?