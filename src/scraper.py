from playwright.sync_api import sync_playwright

URL = "https://m.global.jdsports.com/men/brand/nike,adidas,adidas-originals,asics,berghaus,birkenstock,boss,calvin-klein,calvin-klein-jeans,calvin-klein-performance,calvin-klein-underwear,canterbury,champion,columbia,converse,ea7,emporio-armani-ea7,fila,fred-perry,jack-wolfskin,jordan,lacoste,mammut,new-balance,new-era,nike-sb,polo-ralph-lauren,puma,reebok,superga,the-north-face,timberland,tommy-hilfiger,tommy-hilfiger-underwear,tommy-jeans,ugg,umbro,under-armour,vans/sale/?jd_sort_order=price-low-high"


def get_html():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        print("Opening JD Sports...")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        # JavaScriptの描画待ち
        page.wait_for_timeout(5000)

        html = page.content()

        browser.close()

        return html