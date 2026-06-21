import re

with open("raw_network_checkpoint.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Check context occurrences of the string 's-item'
matches = [m.start() for m in re.finditer(r"s-item", text)]
print(f"Total literal string occurrences of 's-item': {len(matches)}")

for idx, pos in enumerate(matches[:3]):
    # Extract 100 characters before and after to audit the surrounding tags
    context = text[max(0, pos-100):min(len(text), pos+100)]
    print(f"\n--- Occurrence {idx+1} (Char Pos: {pos}) ---")
    print(context.strip())
