#!/usr/bin/env python3
# standalone_utils/utility/gather_ebay_provider_credits.py
#
# Purpose: Standalone diagnostic tool designed to parse config.yaml, sweep through
# every uncommented proxy variant, and aggregate live token balances with zero consumption cost.

import os
import sys
import yaml
from loguru import logger

# --- Robust Path Resolution Matrix ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Traverse up until we locate the root directory containing 'src' and 'config.yaml'
PROJECT_ROOT = CURRENT_DIR
while PROJECT_ROOT and PROJECT_ROOT != os.path.dirname(PROJECT_ROOT):
    if os.path.exists(os.path.join(PROJECT_ROOT, "src")) and os.path.exists(os.path.join(PROJECT_ROOT, "config.yaml")):
        break
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.api.ebay.ebay_scrape_provider import EbayScraperProvider

class MockConfig:
    """Minimal wrapper mock providing a safe object interface for configuration matrices."""
    def __init__(self, raw_dict: dict):
        for key, value in raw_dict.items():
            setattr(self, key, value)

def main():
    # Target path bound directly to the dynamically discovered project root
    config_path = os.path.join(PROJECT_ROOT, "config.yaml")
    
    if not os.path.exists(config_path):
        logger.critical(f"❌ Configuration file not discovered at expected path: {config_path}")
        sys.exit(1)

    logger.info(f"📖 Parsing active proxy configuration structures from {config_path}...")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_yaml = yaml.safe_load(f) or {}
    except Exception as e:
        logger.critical(f"❌ Failed to parse YAML syntax inside configuration file: {e}")
        sys.exit(1)

    # Wrap the raw dictionary mapping into our structural configuration mock
    config_obj = MockConfig(raw_yaml)

    # Verify that proxy rotation configurations are present and enabled
    proxy_rotation = raw_yaml.get("proxy_rotation", {})
    if not proxy_rotation or not proxy_rotation.get("enabled", False):
        logger.warning("⚠️ proxy_rotation is either disabled or missing inside config.yaml.")

    # Initialize the provider infrastructure layer
    logger.info("📡 Dispatching direct telemetry balance metadata requests (0 credits cost)...")
    provider_infra = EbayScraperProvider(config=config_obj)

    # Fetch the compiled snapshot matrix data back out
    credit_summary = provider_infra.get_credit_summary()

    print("\n" + "=" * 80)
    print("📋 UNIFIED EBAY PROXY PROVIDER CREDITS LEDGER")
    print("=" * 80)
    print(f"{'Provider Configuration Block Key':<40} | {'Remaining Quota Balance':<25}")
    print("-" * 80)

    total_credits = 0
    for provider_name, credits in credit_summary.items():
        print(f"{provider_name:<40} | {credits:<25,}")
        total_credits += credits

    print("-" * 80)
    print(f"{'AGGREGATE TOTAL POOL CAPACITY':<40} | {total_credits:<25,}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:7}</level> | {message}")
    main()