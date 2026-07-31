from src.scraper import scrape
from src.parser import parse

result = scrape()

products = parse(result)

for p in products[:10]:

    print(p["name"])
    print(p["was"])
    print(p["price"])
    print(p["url"])
    print()