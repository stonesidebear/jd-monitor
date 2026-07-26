from pathlib import Path

from src.scraper import get_html

print("=" * 50)
print("JD Monitor Started")
print("=" * 50)

html = get_html()

Path("data").mkdir(exist_ok=True)

with open(
    "data/latest.html",
    "w",
    encoding="utf-8"
) as f:
    f.write(html)

print()
print("HTML saved successfully.")
print(f"HTML Size : {len(html):,} bytes")