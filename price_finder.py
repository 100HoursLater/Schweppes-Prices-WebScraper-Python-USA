import time
import random
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import stealth  # Corrected import
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

console = Console()

def parse_price(price_str):
    if not price_str: return None
    # Handles complex strings like "$12.99 ($1.08 / Count)"
    match = re.search(r'\$(\d+\.\d{2})', price_str)
    return float(match.group(1)) if match else None

def scrape_site(browser_context, retailer, url, selectors):
    """Scrapes with corrected stealth and human-like movement."""
    console.print(f"[bold blue][*][/bold blue] Accessing {retailer}...")
    page = browser_context.new_page()
    
    # The actual, non-hallucinated stealth function
    stealth(page) 
    
    results = []
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        
        # Human-like behavior: Scroll down to trigger lazy loading
        page.mouse.wheel(0, 600)
        time.sleep(random.uniform(1.5, 3))

        # Wait for the specific container so we don't scrape an empty page
        try:
            page.wait_for_selector(selectors['item_container'], timeout=10000)
        except PlaywrightTimeoutError:
            console.print(f"[red][!] {retailer}: Timeout waiting for selectors. Possible bot block.[/red]")
            return []

        soup = BeautifulSoup(page.content(), 'html.parser')
        items = soup.select(selectors['item_container'])

        for item in items[:5]:
            name_el = item.select_one(selectors['name'])
            price_el = item.select_one(selectors['price'])
            
            if name_el and price_el:
                name = name_el.get_text(strip=True)
                price = parse_price(price_el.get_text(strip=True))
                if name and price:
                    results.append({'retailer': retailer, 'name': name, 'price': price})
                    
    except Exception as e:
        console.print(f"[red][!] Error on {retailer}: {str(e)[:50]}...[/red]")
    finally:
        page.close()
        
    return results

if __name__ == "__main__":
    search_query = input("Search for: ") or "Schweppes Ginger Ale"

    SITES = {
        "Amazon": {
            "url": f"https://www.amazon.com/s?k={search_query.replace(' ', '+')}",
            "selectors": {
                "item_container": 'div[data-component-type="s-search-result"]',
                "name": 'h2 a span',
                "price": 'span.a-price span.a-offscreen',
            },
        },
        "Walmart": {
            "url": f"https://www.walmart.com/search?q={search_query.replace(' ', '+')}",
            "selectors": {
                "item_container": 'div[data-testid="list-view-node"]',
                "name": 'span[data-automation-id="product-title"]',
                "price": 'div[data-automation-id="product-price"]',
            },
        }
    }

    with sync_playwright() as p:
        # headless=False is the #1 way to avoid being flagged by Walmart/Amazon
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        all_results = []
        for retailer, config in SITES.items():
            all_results.extend(scrape_site(context, retailer, config['url'], config['selectors']))
            time.sleep(random.uniform(2, 4))

        browser.close()

    # Display Results
    if all_results:
        table = Table(title=f"Results for {search_query}")
        table.add_column("Retailer", style="cyan")
        table.add_column("Product")
        table.add_column("Price", justify="right", style="green")
        for r in sorted(all_results, key=lambda x: x['price']):
            table.add_row(r['retailer'], r['name'][:50], f"${r['price']:.2f}")
        console.print(table)
