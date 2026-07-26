from playwright.sync_api import sync_playwright

print("=" * 50)
print("JD Monitor Started")
print("=" * 50)

URL = "https://m.global.jdsports.com"

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True
    )

    page = browser.new_page()

    print("Opening JD Sports...")

    page.goto(
        URL,
        wait_until="networkidle",
        timeout=60000
    )

    print("Page Title:")
    print(page.title())

    browser.close()