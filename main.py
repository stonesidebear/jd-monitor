import requests
from bs4 import BeautifulSoup

URL = "https://m.global.jdsports.com/men/brand/nike,adidas,adidas-originals,asics,berghaus,birkenstock,boss,calvin-klein,calvin-klein-jeans,calvin-klein-performance,calvin-klein-underwear,canterbury,champion,columbia,converse,ea7,emporio-armani-ea7,fila,fred-perry,jack-wolfskin,jordan,lacoste,mammut,new-balance,new-era,nike-sb,polo-ralph-lauren,puma,reebok,superga,the-north-face,timberland,tommy-hilfiger,tommy-hilfiger-underwear,tommy-jeans,ugg,umbro,under-armour,vans/sale/?jd_sort_order=price-low-high"

print("=" * 50)
print("JD Monitor Started")
print("=" * 50)

response = requests.get(
    URL,
    headers={
        "User-Agent": "Mozilla/5.0"
    },
    timeout=30
)

print(f"Status Code : {response.status_code}")

soup = BeautifulSoup(response.text, "lxml")

print("Page Title :")
print(soup.title.text)
