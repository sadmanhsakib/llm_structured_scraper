import asyncio
import random
import os
from typing import Optional, List, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
from playwright_stealth import stealth_async
from markdownify import markdownify as md


class StealthPlaywrightScraper:
    """
    High-tier stealth scraper using Playwright with advanced anti-detection techniques.
    Designed for scalable web scraping with maximum stealth capabilities.
    """
    
    # Rotating user agents for fingerprint randomization
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    ]
    
    # Screen resolutions to randomize
    SCREEN_RESOLUTIONS = [
        {"width": 1920, "height": 1080},
        {"width": 2560, "height": 1440},
        {"width": 1366, "height": 768},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
    ]
    
    # Timezones to randomize
    TIMEZONES = [
        "America/New_York",
        "America/Los_Angeles",
        "Europe/London",
        "Europe/Paris",
        "Asia/Tokyo",
    ]
    
    def __init__(
        self,
        headless: bool = True,
        max_concurrent_browsers: int = 3,
        proxy: Optional[Dict[str, str]] = None,
        use_stealth: bool = True,
    ):
        """
        Initialize the stealth scraper.
        
        Args:
            headless: Run browser in headless mode
            max_concurrent_browsers: Maximum number of concurrent browser instances
            proxy: Proxy configuration dict with 'server', 'username', 'password' keys
            use_stealth: Apply stealth techniques to avoid detection
        """
        self.headless = headless
        self.max_concurrent_browsers = max_concurrent_browsers
        self.proxy = proxy
        self.use_stealth = use_stealth
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context_pool: List[BrowserContext] = []
        self.semaphore = asyncio.Semaphore(max_concurrent_browsers)
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def start(self):
        """Initialize Playwright and browser instance."""
        self.playwright = await async_playwright().start()
        
        # Launch browser with anti-detection settings
        launch_args = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
            ],
        }
        
        if self.proxy:
            launch_args["proxy"] = self.proxy
            
        self.browser = await self.playwright.chromium.launch(**launch_args)
        
    async def close(self):
        """Clean up resources."""
        # Close all contexts
        for context in self.context_pool:
            await context.close()
        self.context_pool.clear()
        
        # Close browser
        if self.browser:
            await self.browser.close()
            
        # Stop playwright
        if self.playwright:
            await self.playwright.stop()
            
    def _get_random_user_agent(self) -> str:
        """Get a random user agent from the pool."""
        return random.choice(self.USER_AGENTS)
        
    def _get_random_screen_resolution(self) -> Dict[str, int]:
        """Get a random screen resolution."""
        return random.choice(self.SCREEN_RESOLUTIONS)
        
    def _get_random_timezone(self) -> str:
        """Get a random timezone."""
        return random.choice(self.TIMEZONES)
        
    async def create_context(self) -> BrowserContext:
        """
        Create a new browser context with randomized fingerprint.
        """
        user_agent = self._get_random_user_agent()
        resolution = self._get_random_screen_resolution()
        timezone = self._get_random_timezone()
        
        context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={"width": resolution["width"], "height": resolution["height"]},
            locale="en-US",
            timezone_id=timezone,
            permissions=["geolocation"],
            geolocation={"latitude": 40.7128, "longitude": -74.0060},  # NYC
            color_scheme="light",
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            # Extra headers for realism
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        
        # Add stealth scripts to context
        if self.use_stealth:
            await context.add_init_script("""
                // Override navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Override Chrome object
                window.chrome = {
                    runtime: {},
                };
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
            
        self.context_pool.append(context)
        return context
        
    async def fetch_page(
        self,
        url: str,
        wait_until: str = "networkidle",
        timeout: int = 30000,
        retry_count: int = 3,
        delay_between_retries: float = 2.0,
        wait_for_selector: Optional[str] = None,
        wait_for_timeout: Optional[int] = None,
    ) -> str:
        """
        Fetch a page with stealth techniques and retry logic.
        
        Args:
            url: URL to fetch
            wait_until: Wait condition - 'load', 'domcontentloaded', 'networkidle', 'commit'
            timeout: Timeout in milliseconds
            retry_count: Number of retries on failure
            delay_between_retries: Delay between retries in seconds
            wait_for_selector: CSS selector to wait for before returning
            wait_for_timeout: Additional timeout in ms to wait after page load
            
        Returns:
            HTML content of the page
        """
        async with self.semaphore:
            for attempt in range(retry_count):
                try:
                    context = await self.create_context()
                    page = await context.new_page()
                    
                    # Apply stealth to page
                    if self.use_stealth and stealth_async:
                        await stealth_async(page)
                    
                    print(f"⏳ Navigating to: {url} (attempt {attempt + 1}/{retry_count})")
                    
                    # Navigate to URL
                    response = await page.goto(
                        url,
                        wait_until=wait_until,
                        timeout=timeout,
                    )
                    
                    # Wait for specific selector if provided
                    if wait_for_selector:
                        print(f"⏳ Waiting for selector: {wait_for_selector}")
                        await page.wait_for_selector(wait_for_selector, timeout=timeout)
                    
                    # Additional wait for dynamic content
                    if wait_for_timeout:
                        print(f"⏳ Waiting additional {wait_for_timeout}ms for dynamic content")
                        await page.wait_for_timeout(wait_for_timeout)
                    
                    # Get HTML content
                    html_content = await page.content()
                    
                    # Clean up
                    await page.close()
                    await context.close()
                    self.context_pool.remove(context)
                    
                    if not html_content:
                        raise ValueError("Empty HTML content received")
                        
                    print(f"✅ Successfully fetched: {url}")
                    return html_content
                    
                except Exception as e:
                    print(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
                    
                    # Clean up on error
                    try:
                        if 'page' in locals():
                            await page.close()
                        if 'context' in locals():
                            await context.close()
                            if context in self.context_pool:
                                self.context_pool.remove(context)
                    except:
                        pass
                    
                    # Retry if not last attempt
                    if attempt < retry_count - 1:
                        wait_time = delay_between_retries * (attempt + 1)
                        print(f"⏳ Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise Exception(f"Failed to fetch {url} after {retry_count} attempts: {str(e)}")
                        

async def fetch_page(
    url: str,
    headless: bool = True,
    wait_until: str = "load",
    timeout: int = 30000,
    proxy: Optional[Dict[str, str]] = None,
    wait_for_selector: Optional[str] = None,
    wait_for_timeout: Optional[int] = None,
) -> str:
    """
    Convenience function for single-page fetch with stealth.
    
    Args:
        url: URL to fetch
        headless: Run browser in headless mode
        wait_until: Wait condition for page load
        timeout: Timeout in milliseconds
        proxy: Proxy configuration
        wait_for_selector: CSS selector to wait for
        wait_for_timeout: Additional timeout in ms
        
    Returns:
        HTML content of the page
    """
    async with StealthPlaywrightScraper(
        headless=headless,
        proxy=proxy,
        use_stealth=True,
    ) as scraper:
        return await scraper.fetch_page(
            url=url,
            wait_until=wait_until,
            timeout=timeout,
            wait_for_selector=wait_for_selector,
            wait_for_timeout=wait_for_timeout,
        )


def export_as_markdown(html_content: str) -> str:
    """
    Converts HTML content to Markdown and saves it to a file.

    Markdown is preferred over HTML for LLM processing because it preserves
    structural information (headings, lists) while significantly reducing
    token usage by removing unnecessary tags.
    """
    # Removing non-textual or layout-heavy tags to reduce noise and focus
    # the LLM on the core content of the page.
    markdown_content = md(
        html_content,
        heading_style="ATX",
        strip=[
            "script",
            "style",
            "img",
            "svg",
            "head",
            "footer",
            "header",
            "nav",
            "aside",
        ],
    )

    # Save the processed content for the parser module to read.
    # UTF-8 encoding ensures that special characters are handled correctly.
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    output_path = os.path.join(data_dir, "webpage.md")
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(markdown_content)
    print(f"✅ Data saved to {output_path}")

    return output_path
