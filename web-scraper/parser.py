import logging
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, computed_field

from config import BASE_URL, HEADERS, MAX_PAGES, REQUEST_TIMEOUT

# Configure logging for process tracking
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class Product(BaseModel):
    """
    Data model representing a single scraped product.
    """
    title: str = Field(description="Product title")
    price: float = Field(description="Current / discounted price ($)")
    old_price: Optional[float] = Field(default=None, description="Original price before discount")
    availability: str = Field(default="In Stock", description="Stock availability status")
    rating: int = Field(default=0, description="Product rating (1 to 5 stars)")
    reviews_count: int = Field(default=0, description="Total number of customer reviews")
    image_url: str = Field(description="Direct URL to product image")
    product_url: str = Field(description="Direct URL to product page")

    @computed_field
    @property
    def discount_percent(self) -> float:
        """
        Calculates the discount percentage automatically if old_price is present.
        """
        if self.old_price and self.old_price > self.price:
            discount = ((self.old_price - self.price) / self.old_price) * 100
            return round(discount, 1)
        return 0.0


class WebScraper:
    """
    Scraper class responsible for fetching HTML pages and extracting product data.
    """
    def __init__(self):
        self.client = httpx.Client(
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True
        )

    def fetch_page(self, page_number: int) -> Optional[str]:
        """
        Fetches the HTML content of a specific page with error handling.
        """
        url = f"{BASE_URL}?page={page_number}"
        try:
            response = self.client.get(url)
            response.raise_for_status()
            logging.info(f"Successfully fetched page {page_number}")
            return response.text
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error {e.response.status_code} while requesting {url}")
        except httpx.RequestError as e:
            logging.error(f"Network error while requesting {url}: {e}")
        return None

    def parse_products(self, html_content: str) -> List[Product]:
        """
        Parses HTML content and extracts a list of Product objects.
        """
        soup = BeautifulSoup(html_content, "lxml")
        product_cards = soup.select(".thumbnail")
        products = []

        for card in product_cards:
            try:
                # Title and product detail link
                title_elem = card.select_one(".title")
                title = title_elem.get("title", title_elem.text.strip()) if title_elem else "N/A"
                rel_link = title_elem.get("href", "") if title_elem else ""
                product_url = f"https://webscraper.io{rel_link}" if rel_link else "N/A"

                # Price extraction
                price_elem = card.select_one(".price")
                price_str = price_elem.text.replace("$", "").strip() if price_elem else "0"
                price = float(price_str)

                # Simulate old price for demonstration purpose (for 30% of items)
                old_price = round(price * 1.15, 2) if len(products) % 3 == 0 else None

                # Image URL extraction
                img_elem = card.select_one("img")
                rel_img = img_elem.get("src", "") if img_elem else ""
                image_url = f"https://webscraper.io{rel_img}" if rel_img else "N/A"

                # Reviews and rating extraction
                reviews_elem = card.select_one(".ratings .pull-right")
                reviews_text = reviews_elem.text.strip().split()[0] if reviews_elem else "0"
                reviews_count = int(reviews_text) if reviews_text.isdigit() else 0

                stars = card.select(".ratings span.glyphicon-star")
                rating = len(stars)

                # Instantiate Product model
                product = Product(
                    title=title,
                    price=price,
                    old_price=old_price,
                    availability="In Stock",
                    rating=rating,
                    reviews_count=reviews_count,
                    image_url=image_url,
                    product_url=product_url
                )
                products.append(product)
            except Exception as err:
                logging.warning(f"Failed to parse product card: {err}")
                continue

        return products

    def run(self) -> List[Product]:
        """
        Executes the scraping process across all configured pages.
        """
        all_products = []
        for page in range(1, MAX_PAGES + 1):
            logging.info(f"Parsing page {page} of {MAX_PAGES}...")
            html = self.fetch_page(page)
            if html:
                products = self.parse_products(html)
                all_products.extend(products)
                logging.info(f"Extracted {len(products)} products from page {page}")
            else:
                logging.warning(f"Skipping page {page} due to fetch error.")

        self.client.close()
        return all_products


if __name__ == "__main__":
    # Local test execution
    scraper = WebScraper()
    data = scraper.run()
    print(f"\nTotal products scraped: {len(data)}")
    if data:
        print("Sample product:")
        print(data[0].model_dump_json(indent=2))