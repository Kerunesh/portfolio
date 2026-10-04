"""
Main application entry point.
Coordinates execution of the web scraper and Excel report generation.
"""

import logging
import sys
from excel_builder import ExcelReportBuilder
from parser import WebScraper

# Configure main logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def run_pipeline() -> None:
    """
    Executes the full pipeline: Scrape -> Process -> Export.
    """
    logging.info("Starting Web Scraper & Data Analysis Pipeline...")

    # Step 1: Scrape Data
    scraper = WebScraper()
    products = scraper.run()

    if not products:
        logging.error(
            "No products extracted. Aborting report generation process."
        )
        return

    logging.info(
        f"Scraping completed successfully. Extracted {len(products)} products."
    )

    # Step 2: Build and Export Excel Report
    logging.info("Building styled Excel report...")
    report_builder = ExcelReportBuilder(products)
    output_filename = report_builder.export()

    logging.info(
        f"Pipeline finished successfully! Output file: {output_filename}"
    )


if __name__ == "__main__":
    run_pipeline()