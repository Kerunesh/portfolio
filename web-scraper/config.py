"""
Configuration module for the web scraper project.
Contains base URLs, request headers, timeouts, and pagination limits.
"""

# Base URL for scraping (using a public demo e-commerce site)
BASE_URL = "https://webscraper.io/test-sites/e-commerce/static/computers/laptops"

# HTTP headers to simulate a real browser request and avoid basic blocks
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Scraper settings
MAX_PAGES = 3             # Number of pages to crawl
REQUEST_TIMEOUT = 10.0     # HTTP request timeout in seconds
OUTPUT_FILE_PREFIX = "products_export"