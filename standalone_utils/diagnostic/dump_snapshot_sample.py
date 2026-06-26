#!/usr/bin/env python3
import os
import glob
from bs4 import BeautifulSoup

# Find the snapshots folder
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
while project_root and project_root != os.path.dirname(project_root):
    if os.path.exists(os.path.join(project_root, "request_responses")):
        break
    project_root = os.path.dirname(project_root)

target_dir = os.path.join(project_root, "request_responses")
html_files = glob.glob(os.path.join(target_dir, "*_status_200.html"))

if not html_files:
    print("❌ No snapshots found.")
    exit()

# Open the first snapshot file
with open(html_files[0], "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

nodes = soup.select("ul.srp-results > li")
if nodes:
    print(f"=== SAMPLE NODE HTML FROM {os.path.basename(html_files[0])} ===")
    # Print a prettified slice of the first 1500 characters inside the first matched list item
    print(nodes[0].prettify()[:1500])
    print("====================================================================")
else:
    print("❌ No matching 'ul.srp-results > li' containers found to inspect.")