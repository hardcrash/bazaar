-- Initialization: Schema Definition for Data Pipeline Ingestion
CREATE TABLE IF NOT EXISTS harvested_market_items (
    item_id TEXT PRIMARY KEY,
    model_name TEXT DEFAULT 'UNKNOWN',
    category TEXT NOT NULL,
    source_platform TEXT DEFAULT 'ebay',

    -- Text Representation
    raw_title TEXT NOT NULL,
    title TEXT NOT NULL,

    -- Financial Matrix
    price REAL NOT NULL,
    shipping_cost REAL DEFAULT 0.0,
    total_cost REAL NOT NULL,
    currency TEXT DEFAULT 'USD',

    -- Condition Metrics & Risk Signals
    condition_id INTEGER NOT NULL,
    is_sold BOOLEAN DEFAULT 1,
    is_for_parts_or_not_working BOOLEAN DEFAULT 0,  -- 🌟 Added direct hardware defect flag
    has_bent_pins BOOLEAN DEFAULT 0,               -- 🌟 Added targeted micro-repair identifier

    -- Seller Metadata Engine
    seller_username TEXT,
    feedback_score INTEGER,
    feedback_percentage REAL,                       -- 🌟 Added risk isolation metric
    is_top_rated BOOLEAN DEFAULT 0,                -- 🌟 Added power-seller classifier

    -- Structural Attributes & Catalog Codes
    epid TEXT,
    buying_options TEXT,                            -- Stored as a comma-separated string or JSON string
    quantity_sold INTEGER DEFAULT 1,                -- 🌟 Added multi-unit MSKU velocity metric
    bid_count INTEGER,

    -- Temporal Velocity Counters
    item_start_date TIMESTAMP,                      -- 🌟 Added for Days on Market (DoM) calculations
    item_end_date TIMESTAMP,
    date_listed TIMESTAMP,                          -- Deprecated/aliased by start_date, kept for compatibility
    date_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Assets & State Routines
    image_url TEXT,
    item_url TEXT,
    process_state TEXT,

    -- AI agent parameters
    is_parsed_by_agent: BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS analyzed_market_items (
    item_id TEXT PRIMARY KEY,
    model_name TEXT DEFAULT 'UNKNOWN',
    category TEXT NOT NULL,
    source_platform TEXT DEFAULT 'ebay',

    -- Text Representation
    raw_title TEXT NOT NULL,
    title TEXT NOT NULL,

    -- Financial Matrix
    price REAL NOT NULL,
    shipping_cost REAL DEFAULT 0.0,
    total_cost REAL NOT NULL,
    currency TEXT DEFAULT 'USD',

    -- Condition Metrics & Risk Signals
    condition_id INTEGER NOT NULL,
    is_sold BOOLEAN DEFAULT 1,
    is_for_parts_or_not_working BOOLEAN DEFAULT 0,  -- 🌟 Added direct hardware defect flag
    has_bent_pins BOOLEAN DEFAULT 0,               -- 🌟 Added targeted micro-repair identifier

    -- Seller Metadata Engine
    seller_username TEXT,
    feedback_score INTEGER,
    feedback_percentage REAL,                       -- 🌟 Added risk isolation metric
    is_top_rated BOOLEAN DEFAULT 0,                -- 🌟 Added power-seller classifier

    -- Structural Attributes & Catalog Codes
    epid TEXT,
    buying_options TEXT,                            -- Stored as a comma-separated string or JSON string
    quantity_sold INTEGER DEFAULT 1,                -- 🌟 Added multi-unit MSKU velocity metric
    bid_count INTEGER,

    -- Temporal Velocity Counters
    item_start_date TIMESTAMP,                      -- 🌟 Added for Days on Market (DoM) calculations
    item_end_date TIMESTAMP,
    date_listed TIMESTAMP,                          -- Deprecated/aliased by start_date, kept for compatibility
    date_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Assets & State Routines
    image_url TEXT,
    item_url TEXT,
    process_state TEXT,

    -- AI agent parameters
    is_parsed_by_agent: BOOLEAN DEFAULT 0
);
CREATE TABLE IF NOT EXISTS historical_metrics (
    model_name TEXT,
    timeframe TEXT,
    condition_type TEXT,
    total_units INTEGER,
    min_item_price REAL,
    max_item_price REAL,
    avg_item_price REAL,
    med_item_price REAL,
    avg_shipping_cost REAL,
    avg_total_cost REAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (model_name, timeframe, condition_type)
);

-- Speed up model aggregation splits (e.g., pulling all 5800X items)
CREATE INDEX IF NOT EXISTS idx_harvested_model ON harvested_market_items (model_name);
CREATE INDEX IF NOT EXISTS idx_analyzed_model ON analyzed_market_items (model_name);

-- Accelerate pricing outliers filtering and defect segregation queries
CREATE INDEX IF NOT EXISTS idx_analyzed_filters ON analyzed_market_items (model_name, is_for_parts_or_not_working, has_bent_pins);
