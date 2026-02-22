import time
import random
import re
from playwright.sync_api import sync_playwright
# We import it this way to be 100% sure we can find the actual function
import playwright_stealth 
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

console = Console()

def extract_price(text):
    """Finds anything that looks like a price ($12.99)."""
    match = re.search(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2}))', text)
    return match.group(0) if match else None

def scrape_retailer(context, name, url, container_selector):
    console.print(f"[bold blue][*][/bold blue] Pulling data from {name}...")
    page = context.new_page()
    
    # FIX: We try the two most common ways to call the stealth function
    try:
        if hasattr(playwright_stealth, 'stealth'):
            # If it's a function directly in the module
            if callable(playwright_stealth.stealth):
                playwright_stealth.stealth(page)
            else:
                # If 'stealth' is the module name, call the function inside it
                playwright_stealth.stealth.stealth(page)
    except Exception:
        console.print("[yellow][!] Stealth failed to load, proceeding anyway...[/yellow]")
    
    results = []
    try:
        # Load the page and wait for it to actually be ready
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        
        # This is the "Magic" part: Wait for the product containers to actually appear
        # If we don't wait, the script looks at an empty page and finds nothing
        page.wait_for_selector(container_selector, timeout=20000)
        
        # Scroll down to trigger lazy-loaded images/prices
        page.mouse.wheel(0, 800)
        time.sleep(2)

        # Get the rendered HTML after JS has finished running
        soup = BeautifulSoup(page.content(), 'html.parser')
        items = soup.select(container_selector)

        for item in items[:5]:
            # Get all text from the item card and hunt for a price
            text_blob = item.get_text(separator=' ', strip=True)
            price = extract_price(text_blob)
            
            # Find the name (usually in an h2 or a link)
            name_el = item.find(['h2', 'span', 'a'], string=re.compile(r'Schweppes|Ginger', re.I))
            item_name = name_el.get_text(strip=True) if name_el else "Product"

            if price:
                results.append({"retailer": name, "item": item_name[:50], "price": price})

    except Exception as e:
        console.print(f"[red][!] {name} failed: {e}[/red]")
    finally:
        page.close()
    return results

if __name__ == "__main__":
    search = "Schweppes Ginger Ale 12 pack"
    
    # Using the most reliable container tags
    SITES = [
        {"name": "Amazon", "url": f"https://www.amazon.com/s?k={search.replace(' ', '+')}", "container": "div[data-component-type='s-search-result']"},
        {"name": "Walmart", "url": f"https://www.walmart.com/search?q={search.replace(' ', '+')}", "container": "div[data-testid='list-view-node']"}
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Keep it False so you can see it work
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36")

        all_data = []
        for site in SITES:
            data = scrape_retailer(context, site['name'], site['url'], site['container'])
            all_data.extend(data)

        browser.close()

    # Final Output
    if all_data:
        table = Table(title=f"\nFound Prices for: {search}")
        table.add_column("Retailer", style="cyan")
        table.add_column("Product")
        table.add_column("Price", style="bold green", justify="right")
        for entry in all_data:
            table.add_row(entry['retailer'], entry['item'], entry['price'])
        console.print(table)
    else:
        console.print("\n[bold red]Found zero results. Check your internet or if the site blocked your IP.[/bold red]")
