# standalone_utils/test_secure_connection.py

# test_secure_connection.py
import requests
import yaml

# 1. Load your live keys directly from your configuration matrix
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Adjust this path below to match your exact config.yaml structure for scrapeops
# e.g., config['providers']['scrapeops']['api_key']
try:
    api_key = config['providers']['scrapeops']['api_key']
except KeyError:
    api_key = "562d504b-614e-4b19-bf30-1c1cf6298bf3"

target_url = "https://www.ebay.com/sch/i.html?_nkw=Ryzen+5800X&LH_Complete=1&LH_Sold=1&rt=nc&_ipg=100&_sop=13&_pgn=1"

payload = {
    "api_key": api_key,
    "url": target_url,
    "residential": "true",
    "country": "us",
    "bypass_cache": "true",
    "render_js": "true"
}

print("📡 Testing raw isolated outbound request to ScrapeOps...")
response = requests.get("https://proxy.scrapeops.io/v1", params=payload, timeout=30)

print(f"📥 Response Code: {response.status_code}")
print(f"📦 Length of Data String: {len(response.text)} characters")
print(f"🔍 Is 's-item' in raw text? {'s-item' in response.text}")

with open("isolated_test_output.html", "w", encoding="utf-8") as f:
    f.write(response.text)
print("💾 Saved output directly to isolated_test_output.html")
