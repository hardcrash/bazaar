import re
from bs4 import BeautifulSoup

with open("raw_network_checkpoint.txt", "r", encoding="utf-8") as f:
    html_content = "".join(f.readlines()[4:])

soup = BeautifulSoup(html_content, "html.parser")

# Pull any elements where the class contains 's-item' as a partial substring
items = soup.find_all(class_=re.compile(r"\bs-item\b"))

print(f"Total elements matching regex selector: {len(items)}")
