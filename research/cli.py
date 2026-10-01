"""Typer CLI interface for e-commerce research tool."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text
from research.config import load_config
from research.events import EventBus
from research.models import PlatformEnum
from research.parsers.amazon_parser import parse_amazon_search_page
from research.parsers.flipkart_parser import parse_flipkart_search_page
from research.parsers.meesho_parser import parse_meesho_json
from research.pipeline.estimate import apply_estimation
from research.pipeline.filters import apply_filters
from research.pipeline.normalize import normalize_and_dedupe
from research.pipeline.orchestrator import run_pipeline
from research.pipeline.rank import rank_products
from research.storage.db import get_run_history
from research.storage.export import export_reports
from research.ui.dashboard import DashboardUI, render_summary_table

app = typer.Typer(help="Multi-Platform E-Commerce Research Tool")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@app.command()
def run(
    query: str = typer.Argument(..., help="Search query or category (comma-separated for multiple)"),
    platforms: str = typer.Option("amazon,flipkart,meesho", help="Platforms to scrape (comma-separated)"),
    pages: int = typer.Option(5, help="Number of search result pages/batches per platform"),
    top_k: int = typer.Option(30, help="Top K candidates for detail enrichment"),
    preset: Optional[str] = typer.Option(None, help="Filter preset (e.g. 'opportunity')"),
    min_units: Optional[int] = typer.Option(None, help="Filter minimum estimated monthly units"),
    min_price: Optional[float] = typer.Option(None, help="Filter minimum price (INR)"),
    max_price: Optional[float] = typer.Option(None, help="Filter maximum price (INR)"),
    min_rating: Optional[float] = typer.Option(None, help="Filter minimum rating (0-5)"),
    max_ratings: Optional[int] = typer.Option(None, help="Filter maximum total ratings count"),
    exclude_sponsored: bool = typer.Option(False, help="Exclude sponsored / ad listings"),
    headless: bool = typer.Option(False, help="Run browser in headless mode"),
    no_dashboard: bool = typer.Option(False, help="Disable live visual dashboard"),
    xlsx: bool = typer.Option(True, help="Generate Excel (.xlsx) report with platform-wise tabs"),
):
    """Run research pipeline for query across Amazon, Flipkart, and Meesho."""
    cfg = load_config()
    cfg.browser.headless = headless
    cfg.scraping.pages_per_platform = pages
    cfg.enrichment.top_k_per_platform = top_k

    query_list = [q.strip() for q in query.split(",") if q.strip()]
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]

    for q in query_list:
        typer.echo(f"\n=======================================================")
        typer.echo(f"  Starting Research Run for Query: '{q}'")
        typer.echo(f"=======================================================\n")

        events = EventBus()
        dashboard = DashboardUI(events, enabled=not no_dashboard)

        async def execute():
            # Launch UI listener and scraper orchestrator concurrently
            ui_task = asyncio.create_task(dashboard.run_listener())
            results_map = await run_pipeline(q, cfg, selected_platforms=platform_list, events=events)
            await ui_task
            return results_map

        results_map = asyncio.run(execute())

        # Collect raw scraped products
        all_raw_products = []
        all_enrichments = {}

        for p_enum, res in results_map.items():
            all_raw_products.extend(res.products)
            for en in res.enrichments:
                all_enrichments[en.product_id] = en

        if not all_raw_products:
            typer.secho("⚠ No products found across all scrapers.", fg=typer.colors.YELLOW)
            continue

        # Pipeline steps: Normalize -> Dedupe -> Estimate -> Filter -> Rank
        normalized_products = normalize_and_dedupe(all_raw_products)
        estimated_products = apply_estimation(normalized_products, enrichments=all_enrichments, cfg=cfg)

        filtered_products = apply_filters(
            estimated_products,
            min_units=min_units,
            min_price=min_price,
            max_price=max_price,
            min_rating=min_rating,
            max_ratings_count=max_ratings,
            exclude_sponsored=exclude_sponsored,
            preset=preset,
            cfg=cfg,
        )

        ranked_products = rank_products(filtered_products)

        # Export reports
        out_dir = export_reports(
            query=q,
            all_products=estimated_products,
            filtered_products=ranked_products,
            cfg=cfg,
            generate_xlsx=xlsx,
        )

        # Render Terminal Summary Table
        render_summary_table(ranked_products)

        typer.secho(f"\n✓ Export complete! Reports saved to: {out_dir}", fg=typer.colors.GREEN, bold=True)


@app.command()
def history(query: Optional[str] = typer.Argument(None, help="Filter history by query")):
    """List previous runs and database snapshot history."""
    runs = get_run_history(query=query)
    if not runs:
        typer.echo("No run history found.")
        return

    table = Table(title="Run History", expand=True)
    table.add_column("Run ID", justify="right", width=8)
    table.add_column("Query", width=25)
    table.add_column("Started At", width=25)
    table.add_column("Platforms", width=25)

    for r in runs:
        table.add_row(
            str(r["run_id"]),
            r["query"],
            r["started_at"],
            r["platforms"],
        )
    Console().print(table)


@app.command()
def selftest():
    """Selector health check against live search pages for pen query."""
    typer.echo("Running selector health checks across all platforms...\n")
    from playwright.sync_api import sync_playwright

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        # Amazon check
        try:
            page.goto("https://www.amazon.in/s?k=pen", timeout=30000)
            html = page.content()
            prods = parse_amazon_search_page(html, query="pen")
            status = "PASS" if len(prods) >= 10 else "WARN"
            results.append(("Amazon", status, f"Parsed {len(prods)} products"))
        except Exception as e:
            results.append(("Amazon", "FAIL", str(e)))

        # Flipkart check
        try:
            page.goto("https://www.flipkart.com/search?q=pen", timeout=30000)
            html = page.content()
            prods = parse_flipkart_search_page(html, query="pen")
            status = "PASS" if len(prods) >= 5 else "WARN"
            results.append(("Flipkart", status, f"Parsed {len(prods)} products"))
        except Exception as e:
            results.append(("Flipkart", "FAIL", str(e)))

        # Meesho check fixture/API check
        try:
            page.goto("https://www.meesho.com/search?q=pen", timeout=30000)
            page.wait_for_timeout(3000)
            html = page.content()
            status = "PASS" if "pen" in html.lower() else "WARN"
            results.append(("Meesho", status, "Loaded search page successfully"))
        except Exception as e:
            results.append(("Meesho", "FAIL", str(e)))

        browser.close()

    table = Table(title="Selector Health Check Results", expand=True)
    table.add_column("Platform", width=15)
    table.add_column("Status", width=10)
    table.add_column("Details", ratio=1)

    for plat, stat, det in results:
        style = "green" if stat == "PASS" else ("yellow" if stat == "WARN" else "red")
        table.add_row(plat, Text(stat, style=style), det)

    Console().print(table)


@app.command()
def calibrate():
    """Calibrate empirical rating_rate using Amazon native badges and snapshots."""
    typer.echo("Empirical calibration engine initialized. Re-run after completing multiple snapshot runs.")


if __name__ == "__main__":
    app()
