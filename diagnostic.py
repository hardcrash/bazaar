from bs4 import BeautifulSoup
import re

# 1. Load the exact file your logger dropped
with open("raw_network_checkpoint.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()
    # Strip the telemetry header metadata lines you wrote to it
    html_content = "".join(lines[4:])

soup = BeautifulSoup(html_content, "html.parser")

# 2. Test element extraction target steps manually:
items = soup.select(".s-item") # or soup.find_all(class_=re.compile("s-item"))
print(f"Total elements matching selector: {len(items)}")

for i, item in enumerate(items[:5]):
    # Check if this item element is just the 'search results header' dummy item
    title_el = item.select_one(".s-item__title")
    price_el = item.select_one(".s-item__price")

    title = title_el.text.strip() if title_el else "NOT FOUND"
    price = price_el.text.strip() if price_el else "NOT FOUND"

    print(f"👉 Element [{i}] | Title: {title} | Price Text: {price}")
