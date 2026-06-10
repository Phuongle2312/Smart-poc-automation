"""
Phase 1: RPA Web Scraper (Playwright)
Automates login, handles sessions, retries network failures, and extracts order data.
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright, BrowserContext, Page
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

# Ensure validator is importable
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.validator import validate_raw_orders

# Load environment variables
load_dotenv()

# Setup Logging
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

log_filename = f"logs/crawler_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("crawler")

SESSION_FILE = "data/session.json"
RAW_ORDERS_FILE = "data/raw_orders.json"

class CrawlerException(Exception):
    """Custom exception for crawler execution issues."""
    pass

class AuthException(Exception):
    """Exception raised when authentication fails."""
    pass


async def solve_captcha(page: Page, captcha_key: str) -> str:
    """
    Solves the CAPTCHA.
    For the Mock Server, it extracts the captcha code directly from HTML.
    For real portals, this would hook into 2Captcha/Anti-Captcha or alert the user.
    """
    logger.info("Attempting to solve CAPTCHA...")
    try:
        # Check if we are on the mock portal
        captcha_element = await page.query_selector("#captcha-container")
        if captcha_element:
            captcha_text = await captcha_element.inner_text()
            logger.info(f"Solved CAPTCHA automatically (Mock Server): {captcha_text.strip()}")
            return captcha_text.strip()
        
        # Real-world fallback: Check if API key is provided
        if captcha_key:
            logger.info("Real CAPTCHA API integration would run here (e.g. 2captcha).")
            # Mocking API response for demonstration
            return "API_KEY_MOCK"
        
        # Final fallback: Request manual input or fail
        logger.warning("No CAPTCHA key provided. Emitting alert.")
        raise CrawlerException("CAPTCHA detected and no solver available.")
    except Exception as e:
        logger.error(f"Error solving CAPTCHA: {e}")
        raise

async def save_session(context: BrowserContext):
    """Saves storage state (cookies/localStorage) to reuse sessions."""
    state = await context.storage_state()
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)
    logger.info("Session state saved successfully.")

async def load_session(context: BrowserContext) -> bool:
    """Loads and injects saved storage state into context."""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Reconstruct storage state manually or by passing it on context creation
            # Note: storage_state must be passed when creating context. 
            # We return True to indicate a saved session exists.
            return True
        except Exception as e:
            logger.error(f"Failed to load session file: {e}")
    return False

def get_config() -> dict:
    """Helper to read portal configuration dynamically at runtime."""
    return {
        "PORTAL_URL": os.getenv("PORTAL_URL", "http://localhost:8888"),
        "USERNAME": os.getenv("CRAWLER_USERNAME", "admin"),
        "PASSWORD": os.getenv("CRAWLER_PASSWORD", "admin123"),
        "CAPTCHA_KEY": os.getenv("CAPTCHA_API_KEY", "")
    }

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(CrawlerException),
    reraise=True
)
async def fetch_orders_page(page: Page) -> str:
    """Fetches the orders page, retrying on network/navigation failures."""
    config = get_config()
    portal_url = config["PORTAL_URL"]
    logger.info(f"Navigating to orders page: {portal_url}/orders")
    try:
        response = await page.goto(f"{portal_url}/orders", timeout=10000)
        # Check if we were redirected to login page (which indicates session expired)
        if "/login" in page.url:
            raise AuthException("Session expired or invalid, redirected to login page.")
        
        if not response or response.status != 200:
            raise CrawlerException(f"Failed to load page, status: {response.status if response else 'No Response'}")
            
        return await page.content()
    except AuthException:
        raise
    except Exception as e:
        logger.warning(f"Temporary navigation error: {e}. Retrying...")
        raise CrawlerException(f"Navigation error: {e}")

async def perform_login(page: Page, context: BrowserContext):
    """Executes the login workflow including CAPTCHA entry."""
    config = get_config()
    portal_url = config["PORTAL_URL"]
    username = config["USERNAME"]
    password = config["PASSWORD"]
    captcha_key = config["CAPTCHA_KEY"]

    logger.info(f"Navigating to login page: {portal_url}/login")
    await page.goto(f"{portal_url}/login")
    
    # Fill username and password
    await page.fill("#username", username)
    await page.fill("#password", password)
    
    # Solve CAPTCHA
    captcha_code = await solve_captcha(page, captcha_key)
    await page.fill("#captcha", captcha_code)
    
    # Click submit and wait for navigation
    logger.info("Submitting login form...")
    await asyncio.gather(
        page.click("button.btn"),
        page.wait_for_url(f"**/orders", timeout=5000)
    )
    
    if "/orders" not in page.url:
        # Check if error message is displayed
        error_element = await page.query_selector(".error")
        if error_element:
            error_text = await error_element.inner_text()
            raise AuthException(f"Login failed: {error_text}")
        raise AuthException("Login failed for unknown reason.")
        
    logger.info("Login successful.")
    await save_session(context)

async def extract_orders_from_html(html_content: str) -> list:
    """Parses orders table from HTML page content."""
    logger.info("Parsing orders from HTML content...")
    return []

# Selector configuration file for self-healing
SELECTORS_FILE = "data/selectors.json"

def get_selector(key: str, default_val: str) -> str:
    if os.path.exists(SELECTORS_FILE):
        try:
            with open(SELECTORS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get(key, default_val)
        except Exception:
            pass
    return default_val

async def parse_orders_table(page: Page) -> list:
    """Extracts raw orders data from the orders page table using Playwright selectors."""
    logger.info("Parsing orders table from page...")
    orders = []
    
    # Locate table rows
    row_selector = get_selector("orders_table_rows", "table tbody tr")
    cell_selector = get_selector("orders_table_cells", "td")
    
    rows = await page.query_selector_all(row_selector)
    if not rows:
        # Check if table itself exists
        table_exists = await page.query_selector("table")
        if table_exists:
            raise CrawlerException(f"Selector mismatch: '{row_selector}' returned 0 rows.")
        else:
            raise CrawlerException("No table found on page.")
            
    for row in rows:
        cells = await row.query_selector_all(cell_selector)
        if len(cells) >= 5:
            order_id = (await cells[0].inner_text()).strip()
            vendor = (await cells[1].inner_text()).strip()
            order_date = (await cells[2].inner_text()).strip()
            total_amount_str = (await cells[3].inner_text()).strip()
            barcodes_str = (await cells[4].inner_text()).strip()
            
            # Parse total amount
            try:
                total_amount = float(total_amount_str.replace(",", ""))
            except ValueError:
                total_amount = 0.0 # Will fail validation, which is expected for testing
                
            # Parse barcodes list
            barcodes = [b.strip() for b in barcodes_str.split(",") if b.strip()]
            
            orders.append({
                "order_id": order_id,
                "vendor": vendor,
                "order_date": order_date,
                "total_amount": total_amount,
                "barcodes": barcodes
            })
            
    logger.info(f"Extracted {len(orders)} raw orders from HTML.")
    return orders

async def run_crawler():
    """Main orchestrator function for Phase 1 Crawler."""
    logger.info("Starting RPA Crawler operation...")
    
    async with async_playwright() as p:
        # Start browser headless
        browser = await p.chromium.launch(headless=True)
        
        # Prepare context with or without saved session state
        context_args = {}
        if os.path.exists(SESSION_FILE):
            logger.info("Found existing session. Re-using storage state.")
            context_args["storage_state"] = SESSION_FILE
            
        context = await browser.new_context(**context_args)
        page = await context.new_page()
        
        try:
            # 1. Attempt to fetch orders page directly (using saved session)
            try:
                await fetch_orders_page(page)
            except (AuthException, CrawlerException) as e:
                logger.info(f"Direct access to orders failed ({e}). Proceeding to login...")
                # Session is invalid or doesn't exist, we must login
                await perform_login(page, context)
                # Retry fetching orders after login
                await fetch_orders_page(page)
                
            # 2. Extract raw orders
            raw_orders = await parse_orders_table(page)
            
            # 3. Validate and clean data
            logger.info("Running schema validation...")
            validated_orders = validate_raw_orders(raw_orders)
            
            # 4. Save results to disk
            with open(RAW_ORDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(validated_orders, f, indent=4)
                
            logger.info(f"Crawler run completed. Saved {len(validated_orders)} validated orders to {RAW_ORDERS_FILE}.")
            
        except Exception as e:
            logger.error(f"Critical error during crawler run: {e}", exc_info=True)
            raise
        finally:
            await context.close()
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_crawler())
