## ⚙️ Configuration & Secrets Setup

Because your local keys and specific file adjustments are blocked by `.gitignore`, you must manually initialize `config.yaml` and `credentials.yaml` in the root of the directory tree before starting up the harvester engine.

### 1. API Keys (`credentials.yaml`)
Create a file named `credentials.yaml` in the project root. This manages your secure OAuth connections to the marketplace endpoints. Populate it using the following structural keys, substituting your actual developer dashboard strings:

```yaml
sandbox:
  client_id: "YOUR_SANDBOX_CLIENT_ID"
  client_secret: "YOUR_SANDBOX_CLIENT_SECRET"

production:
  client_id: "YOUR_PRODUCTION_CLIENT_ID"
  client_secret: "YOUR_PRODUCTION_CLIENT_SECRET"
```  

### 2. API Keys config.yaml:

```yaml
use_sandbox: false
database:
  path: "bazaar.db"

agent:
  api_url: "http://localhost:11434/v1/chat/completions"
  model_name: "Qwen_Qwen3.5-4B-Q4_K_M.gguf"
  cache_output_file: "consolidated_bazaar_metrics.json"
```


# 🏗️ Architecture & Extensibility Guide

The Bazaar Engine uses a configuration-driven, polymorphic **Strategy Pattern** to handle data ingestion and hardware item classification. This decouples platform integrations and text-parsing algorithms from the core runtime engine.

Rather than modifying application code, new hardware verticals, search targets, and classification rules can be added entirely through configuration files.

---

## 🧩 System Architecture Flow

The data pipeline operates across three isolgories or Search Targated processing layers:

### 1. Ingestion Layer (`main.py` & `searches.json`)

Responsible for:

* Reading active target definitions
* Orchestrating platform execution bounds
* Managing network paging loops
* Passing discovered raw items to the Curator gatekeeper

### 2. Filtering Gatekeeper (`src/analysis/curator.py`)

Responsible for:

* Sanitizing inbound payloads
* Filtering invalid or low-quality listings (e.g., box-only listings)
* Screening extreme pricing outliers
* Updating the local SQLite workspace

### 3. Strategy Classification Layer (`src/analysis/parser.py`)

Responsible for:

* Resolving target strings through dynamic parser selection
* Executing polymorphic parsing strategies such as:

  * `RegexChipsetStrategy`
  * `RegexLookaheadStrategy`
* Applying classification matrices defined in JSON configuration layers

---

# 🚀 Adding New Categories or Search Targets

Expanding your tracking footprint (for example, adding NVIDIA GPUs alongside AMD motherboards) requires only two configuration changes.

## Step 1: Register the Target in `searches.json`

Add the new target to `active_pipeline_targets` and define its search profile in the `categories` section.

```json
{
  "active_pipeline_targets": [
    "motherboards_b650",
    "gpus_nvidia_rtx"
  ],
  "categories": {
    "gpus_nvidia_rtx": {
      "base_query": "NVIDIA RTX Graphics Card",
      "parser_category": "GraphicsCard",
      "parsing_strategy": "RegexChipsetStrategy"
    }
  }
}
```

## Step 2: Define the Parsing Matrix in `parser_config.json`

Create the parsing configuration for the corresponding `parser_category`.

```json
{
  "categories": {
    "GraphicsCard": {
      "strategy_class": "RegexChipsetStrategy",
      "config": {
        "brands": [
          "ASUS",
          "MSI",
          "GIGABYTE",
          "EVGA",
          "ZOTAC",
          "FOUNDERS"
        ],
        "patterns": [
          "\\b(RTX\\s?\\d{4}0\\s?(?:TI|SUPER)?|GTX\\s?\\d{3,4})\\b"
        ],
        "noise_words": [
          "NVIDIA",
          "GRAPHICS",
          "CARD",
          "GPU",
          "VIDEO",
          "PCI",
          "VRAM"
        ]
      }
    }
  }
}
```

---

## ✅ Activation

Once both configuration files have been updated, the new category is fully integrated.

Start a harvest run with:

```bash
python main.py harvest
```

---

# 🛠️ Modifying Existing Search Heuristics

If listings are falling into the `UNKNOWN` bucket or specific models are not being recognized:

### Do **not** modify Python source code.

Instead:

1. Open `parser_config.json`.
2. Locate the appropriate category definition.
3. Update the regular expressions contained in the `patterns` array.
4. Adjust brand aliases, token boundaries, or noise-word exclusions as needed.
5. Open `searches.json` and refine the outbound search keywords dispatched to platform adapters.

Because classification behavior is configuration-driven, most tuning and expansion tasks can be completed without touching the runtime engine.
