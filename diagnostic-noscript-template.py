import re
from bs4 import BeautifulSoup

with open("raw_network_checkpoint.txt", "r", encoding="utf-8") as f:
    html_content = "".join(f.readlines()[4:])

soup = BeautifulSoup(html_content, "html.parser")

# Target the hidden template block container
hidden_container = soup.find("noscript") or soup.find("template")

if hidden_container:
    # Re-hydrate the hidden string text contents into a parseable DOM tree
    inner_soup = BeautifulSoup(hidden_container.text, "html.parser")
    items = inner_soup.select(".s-item")
else:
    items = soup.select(".s-item")

print(f"Total elements matching selector: {len(items)}")
