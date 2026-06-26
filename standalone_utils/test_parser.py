# standalone_utils/test_parser.py

# test_parser.py

from src.api.ebay.ebay_scrape_client import EbayScrapeClient
import logging

logging.basicConfig(level=logging.DEBUG)

# 🛠️ Mock a minimal configuration object to satisfy __init__(config)
class MockConfig:
    def __init__(self):
        # Add any properties your client needs from config (e.g., proxy settings)
        self.proxy_rotation = {"providers": {"scraperapi": {}}}
        self.politeness_delay = 1.0

# Initialize with the mock config
mock_cfg = MockConfig()
client = EbayScrapeClient(config=mock_cfg)

# Read the last successful network payload dropped before you hit Ctrl+C
with open("raw_network_checkpoint.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()
    # Skip the diagnostic header metadata blocks (lines 0-4) to get to raw HTML
    html_content = "".join(lines[5:])

results = client._parse_ebay_html(
    html_content=html_content,
    model_name="Ryzen 5800X",
    category_id="164",
    is_sold=True
)

print(f"\n📊 Extraction Test Results: Found {len(results)} items in saved payload.")
for item in results[:3]:
    print(item)
