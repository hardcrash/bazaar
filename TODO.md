# BazaarPipeline Development Roadmap

## Phase 1: Data Visualization & Display ⏳ *Current Focus*
- [ ] Create `src/visualization/dashboard.py` to read `historical_metrics` and `consolidated_bazaar_metrics.json`.
- [ ] Implement a clean CLI terminal-table summary outputting pricing distributions (Median, Standard Deviation, Landed Cost).
- [ ] (Optional) Add a basic lightweight charting script using `matplotlib` or `plotly` to graph the 13-month availability matrix curves.

## Phase 2: Live Sales & Completed Transactions Analysis
- [ ] Investigate eBay REST Browse/Finding API endpoints for capturing *completed and sold* listings rather than just active inventory.
- [ ] Update `bazaar.db` schema to handle transactional date timestamps, mapping velocity (how fast an item sells once listed).
- [ ] Implement a volume-weighted pricing index algorithm to separate list prices from actual closing values.

## Phase 3: Modular Architecture & Scalability Refactor
- [ ] Abstract regex patterns out of `agent_engine.py` into a standalone YAML configuration layout (e.g., `categories/am4_motherboards.yaml`, `categories/gpus.yaml`).
- [ ] Refactor `extract_hardware_via_heuristics` to dynamically load extraction definitions based on the execution target switch.
- [ ] Create a CLI flag mechanism (`python main.py harvest --category gpus`) to run isolated, target-driven ingestion cycles cleanly.

## Phase 4: Edge-Case Reduction (The Review Queue)
- [ ] Analyze the current ~24% failure rate (284 rows) in the manual review queue.
- [ ] Update heuristics to handle complex multi-item bundles (e.g., "Ryzen 5 3600 + B450 Motherboard Combo") without dropping tokens.
