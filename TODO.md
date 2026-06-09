# BazaarPipeline Development Roadmap

### 🟩 TODO: Refine Stage 2 MSKU Parsing & Outlier Filtering

- [ ] **Fix Heuristic Bleed on Hardware Defect Flags:** The current `has_bent_pins` check executes a page-wide string scan on the raw HTML. If a multi-sku listing contains a single broken unit or boilerplate defect text in the terms, *all* extracted variations are falsely marked as `Pins: True`. 
  --> *Solution:* Scope the regex/keyword heuristics tightly to the specific variation text block or individual item condition description container instead of the global `html_content`.

- [ ] **Handle MSKU Initial Target Discrepancy:** Multi-variation listings are slipping through Stage 1 bracket bounds because the parent card advertised the lowest variant's price (e.g., a 3700X for $99.90). Once Stage 2 unmasks the true target variant cost (e.g., the 5800X at $202.50), it violates the active historical slicing filter ($115–$120).
  --> *Solution:* Ensure the database/analysis pipeline explicitly drops or routes unmasked items that fall outside the active price bracket to prevent statistical skewing in the analytics window.
