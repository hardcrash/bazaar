Data Infrastructure Roadmap
Phase 1: Foundation & Persistence

    [x] Implement DatabaseManager: Create a robust session-based manager ensuring connection persistence and INSERT OR REPLACE logic for active data.

    [x] Fortify Proxy Routing Engine: Stabilize adaptive weighting allocations to favor high-credit pipelines (scraperapi_email_on_demand) and prevent ghost state credit-drain cycles.

    [ ] Add Round-Robin Strategy: Expand the rotation engine configuration options to support a deterministic round_robin sequence as an alternative to weighted_random.

Phase 2: Ingestion & Extraction Engine

    [ ] Repair MSKU Logic (CRITICAL): Re-engineer HTML parsing rules to cleanly intercept and unpack merchant stock keeping units (MSKU) and multi-variation item listings.

    [ ] Max Out market_item Fields: Update structural scrapers to fully saturate all possible schema columns inside the target data entry blocks, leaving zero blind spots.

    [ ] Data Validation Layer: Implement Pydantic models to validate and sanitize incoming eBay payloads before they are committed to the database.

    [ ] Fragility Isolation (New Category Testing): Roll out a parallel scraper module for Mid-Tier Motherboards to track down, decouple, and eliminate hardcoded quirks or fragile extraction assumptions.

Phase 3: Sourcing & Arbitrage Analytics Engine

    [ ] Defect & Repair Sourcing Filter: Design advanced active-search string queries and tag parsers specifically targeting items listed under "For Parts or Not Working" that exhibit high-probability repair indicators.

    [ ] Historical Aggregator Service: Develop consolidation services that track analyzed_market_items histories to output:

        Price Benchmarks: High-velocity calculation of Mean, Median, Mode, and Standard Deviation across specific performance tiers.

        Defect Segregation: Count and group units marked is_for_parts_or_not_working versus working used / refurbished data models to establish accurate, risk-adjusted valuation limits.

    [ ] Profit Opportunity Predictor: Implement a real-time margin assessment layer:
    Expected Net Profit=Target Resale Median−(Purchase Price+Est. Repair Costs+Platform Fees)

    [ ] Unit Velocity Tracker: Implement analytical metrics for "Days on Market" (DoM) using variations between matching item_start_date and date_fetched vectors to separate high-velocity flips from stagnant stock.

Phase 4: UI/UX Orchestration Layer

    [ ] GUI Dashboard Application: Design a localized workspace control center to visually manage active scraping processes, watch proxy allowances tick down live, and surface instant buy/repair arbitrage alerts.

---
