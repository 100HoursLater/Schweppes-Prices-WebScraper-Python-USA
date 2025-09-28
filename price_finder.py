import time
import random
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

# --- Spoofing Configuration ---
# A list of realistic, recent User-Agent strings to rotate through.
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0',
]

# Common headers sent by real browsers. We'll set these in the browser context.
COMMON_HEADERS = {
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Connection': 'keep-alive',
}

# --- Helper Functions --- (Mostly unchanged)
def parse_price(price_str):
    if not price_str: return None
    match = re.search(r'(\d+\.\d{2})', price_str)
    return float(match.group(1)) if match else None

def calculate_price_per_unit(name, price):
    if not price or not name: return None, "N/A"
    name_lower = name.lower()
    match = re.search(r'(\d+)\s*(?:-?pack|pk|cans|count)', name_lower)
    if match:
        count = int(match.group(1))
        if count > 0: return price / count, f"${price / count:.2f}/can"
    match = re.search(r'(\d+(\.\d+)?)\s*(l|liter)', name_lower)
    if match:
        liters = float(match.group(1))
        if liters > 0: return price / liters, f"${price / liters:.2f}/L"
    return price, "N/A"

# --- NEW Browser-Based Scraper Functions ---

def scrape_site(page, retailer, url, search_term, selectors):
    """A generic function to scrape a site using Playwright."""
    print(f"[*] Searching {retailer} for '{search_term}'...")
    results = []
    try:
        # Go to the URL, pretending to be referred from Google for extra stealth
        page.goto(url, wait_until='domcontentloaded', timeout=20000, referer="https://www.google.com/")
        
        # Wait for a random, human-like duration for JS to load content
        time.sleep(random.uniform(2, 5))

        # Get the final, JS-rendered HTML
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        items = soup.select(selectors['item_container'])
        if not items:
            print(f"[!] {retailer}: No result containers found with selector '{selectors['item_container']}'. Site structure may have changed.")
            return []

        for item in items[:5]:
            name_element = item.select_one(selectors['name'])
            price_element = item.select_one(selectors['price'])
            
            if name_element and price_element:
                name = name_element.get_text(strip=True)
                price = parse_price(price_element.get_text(strip=True))
                if name and price and search_term.lower().split()[0] in name.lower():
                    results.append({'retailer': retailer, 'name': name, 'price': price})
                    
    except PlaywrightTimeoutError:
        print(f"[!] {retailer}: Page timed out. The site might be slow or blocking.")
    except Exception as e:
        print(f"[!] An unexpected error occurred with {retailer}: {e}")
        
    print(f"[*] Found {len(results)} results on {retailer}.")
    return results

# --- Main Application Logic ---
if __name__ == "__main__":
    console = Console()
    console.print("\n[bold magenta]Schweppes Price Finder (v3 - Ultimate Spoofing Edition)[/bold magenta] :ninja:")
    
    search_query = input("\n> What Schweppes product are you looking for?\n  ")
    if not search_query:
        search_query = "Schweppes Ginger Ale 12 pack"

    # Define the unique selectors for each site
    SITES = {
        "Amazon": {
            "url": f"https://www.amazon.com/s?k={search_query.replace(' ', '+')}",
            "selectors": {
                "item_container": 'div[data-component-type="s-search-result"]',
                "name": 'span.a-size-medium, span.a-size-base-plus',
                "price": 'span.a-price',
            },
        },
        "Walmart": {
            "url": f"https://www.walmart.com/search?q={search_query.replace(' ', '%20')}",
            "selectors": {
                "item_container": 'div[data-item-id]',
                "name": 'span[data-automation-id="product-title"]',
                "price": 'div[data-automation-id="product-price"]',
            },
        },
        "Target": {
             "url": f"https://www.target.com/s?searchTerm={search_query.replace(' ', '%20')}",
             "selectors": {
                "item_container": '[data-test="product-card"]',
                "name": '[data-test="product-title"]',
                "price": '[data-test="current-price"]',
             },
        },
    }

    all_results = []
    # This block manages the browser lifecycle automatically
    with sync_playwright() as p:
        # Launch the browser. Set headless=False to watch it work (good for debugging)
        browser = p.chromium.launch(headless=True)
        
        # Create a new "incognito" browser context with our spoofed headers
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            extra_http_headers=COMMON_HEADERS,
            java_script_enabled=True, # Ensure JS is on
        )
        page = context.new_page()

        for retailer, config in SITES.items():
            results = scrape_site(page, retailer, config['url'], search_query, config['selectors'])
            all_results.extend(results)
            time.sleep(random.uniform(1, 3)) # Wait between scraping different sites

        browser.close()

    if not all_results:
        console.print("\n[bold red]No results found across any retailers.[/bold red]")
        console.print("[yellow]This could mean the product is out of stock, or all sites have changed their HTML structure.[/yellow]")
        console.print("[yellow]Try running with a broader search term (e.g., 'Schweppes Ginger Ale').[/yellow]")
    else:
        processed_results = [
            {**res, **dict(zip(['unit_price', 'unit_price_str'], calculate_price_per_unit(res['name'], res['price'])))}
            for res in all_results
        ]
        sorted_results = sorted(processed_results, key=lambda x: x['unit_price'] if x['unit_price'] is not None else float('inf'))

        table = Table(title=f"\n:moneybag: Price Comparison for '{search_query}'", show_header=True, header_style="bold green")
        table.add_column("Retailer", style="dim", width=12)
        table.add_column("Product Name")
        table.add_column("Price", justify="right")
        table.add_column("Price Per Unit", justify="right", style="bold yellow")

        for item in sorted_results:
            table.add_row(item['retailer'], item['name'], f"${item['price']:.2f}", item['unit_price_str'])
        
        console.print(table)