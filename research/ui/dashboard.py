"""Rich live visual terminal dashboard and summary view."""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from research.events import (
    CaptchaDetected,
    CaptchaResolved,
    EnrichProgress,
    Event,
    EventBus,
    PageDone,
    PageStarted,
    PlatformFailed,
    PlatformFinished,
    PlatformStarted,
    ProductFound,
    RunFinished,
    RunStarted,
    WarningEvent,
)
from research.models import PlatformEnum, Product

logger = logging.getLogger(__name__)


class DashboardUI:
    """Live visual dashboard manager using Rich."""

    def __init__(self, events: EventBus, enabled: bool = True) -> None:
        self.events = events
        self.enabled = enabled
        self.console = Console()

        self.query = ""
        self.start_time = datetime.now(timezone.utc)
        self.platform_states: Dict[str, dict] = {
            "amazon": {"status": "idle", "found": 0, "page": 0, "total_pages": 0, "badges": 0, "blocks": 0},
            "flipkart": {"status": "idle", "found": 0, "page": 0, "total_pages": 0, "badges": 0, "blocks": 0},
            "meesho": {"status": "idle", "found": 0, "page": 0, "total_pages": 0, "badges": 0, "blocks": 0},
        }
        self.latest_products: List[dict] = []
        self.logs: List[str] = []
        self.captcha_active: Dict[str, bool] = {}

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"{ts} {msg}"
        self.logs.append(line)
        if len(self.logs) > 12:
            self.logs.pop(0)

    def generate_layout(self) -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="ticker", size=8),
            Layout(name="footer", size=10),
        )

        elapsed = str(datetime.now(timezone.utc) - self.start_time).split(".")[0]
        header_text = Text(f"E-COMMERCE RESEARCH TOOL — Query: '{self.query}' — Elapsed: {elapsed}", style="bold white on blue", justify="center")
        layout["header"].update(Panel(header_text, style="blue"))

        # Platforms Table
        table = Table(title="Platform Status", expand=True)
        table.add_column("Platform", style="cyan", width=12)
        table.add_column("Status", width=15)
        table.add_column("Progress", width=25)
        table.add_column("Found", justify="right", width=10)
        table.add_column("Native Badges", justify="right", width=15)

        for p_name, st in self.platform_states.items():
            status_str = st["status"]
            if self.captcha_active.get(p_name):
                status_style = "bold yellow on red"
                status_str = "PAUSED (CAPTCHA)"
            elif status_str == "scraping":
                status_style = "green"
            elif status_str == "enriching":
                status_style = "bold magenta"
            elif status_str == "done":
                status_style = "bold blue"
            elif status_str == "failed":
                status_style = "bold red"
            else:
                status_style = "dim"

            prog = f"Page {st['page']}/{st['total_pages']}" if st["total_pages"] > 0 else "—"
            table.add_row(
                p_name.capitalize(),
                Text(status_str, style=status_style),
                prog,
                str(st["found"]),
                str(st["badges"]),
            )

        layout["main"].update(Panel(table, title="Platforms"))

        # Ticker
        ticker_table = Table(title="Latest Products Found", expand=True, show_header=True)
        ticker_table.add_column("Platform", width=10)
        ticker_table.add_column("Title", ratio=1)
        ticker_table.add_column("Price", width=10)
        ticker_table.add_column("Rating", width=12)

        for item in reversed(self.latest_products[-6:]):
            p_style = "yellow" if item["platform"] == "amazon" else ("blue" if item["platform"] == "flipkart" else "magenta")
            price_str = f"₹{item['price']}" if item['price'] else "—"
            rating_str = f"★{item['rating']}" if item['rating'] else "—"
            ticker_table.add_row(
                Text(item["platform"].capitalize(), style=p_style),
                item["title"][:60],
                price_str,
                rating_str,
            )

        layout["ticker"].update(Panel(ticker_table))

        # Logs
        log_text = Text("\n".join(self.logs), style="dim white")
        layout["footer"].update(Panel(log_text, title="Log Output"))

        return layout

    async def run_listener(self) -> None:
        """Process events from EventBus and update Live display."""
        if not self.enabled:
            while True:
                ev = await self.events.get()
                if isinstance(ev, RunFinished):
                    break
            return

        with Live(self.generate_layout(), refresh_per_second=4, console=self.console) as live:
            while True:
                ev = await self.events.get()

                if isinstance(ev, RunStarted):
                    self.query = ev.query
                    self.start_time = ev.timestamp
                    self.log(f"Run started for query: '{ev.query}'")

                elif isinstance(ev, PlatformStarted):
                    p_name = ev.platform.value
                    self.platform_states[p_name]["status"] = "scraping"
                    self.log(f"[{p_name.upper()}] Scraping started")

                elif isinstance(ev, PageStarted):
                    p_name = ev.platform.value
                    self.platform_states[p_name]["page"] = ev.page
                    self.platform_states[p_name]["total_pages"] = ev.total_pages

                elif isinstance(ev, ProductFound):
                    p_name = ev.platform.value
                    self.platform_states[p_name]["found"] += 1
                    if ev.product.units_sold_last_month and ev.product.sales_method.value == "native_badge":
                        self.platform_states[p_name]["badges"] += 1

                    self.latest_products.append({
                        "platform": p_name,
                        "title": ev.product.title,
                        "price": ev.product.price,
                        "rating": ev.product.rating,
                    })
                    if len(self.latest_products) > 20:
                        self.latest_products.pop(0)

                elif isinstance(ev, EnrichProgress):
                    p_name = ev.platform.value
                    self.platform_states[p_name]["status"] = f"enriching ({ev.done}/{ev.total})"

                elif isinstance(ev, CaptchaDetected):
                    p_name = ev.platform.value
                    self.captcha_active[p_name] = True
                    self.platform_states[p_name]["blocks"] += 1
                    self.log(f"[{p_name.upper()}] ⚠ CAPTCHA detected — resolve in browser window!")

                elif isinstance(ev, CaptchaResolved):
                    p_name = ev.platform.value
                    self.captcha_active[p_name] = False
                    self.log(f"[{p_name.upper()}] CAPTCHA resolved")

                elif isinstance(ev, PlatformFinished):
                    p_name = ev.platform.value
                    self.platform_states[p_name]["status"] = "done"
                    self.log(f"[{p_name.upper()}] Scraping finished. Total items: {ev.count}")

                elif isinstance(ev, PlatformFailed):
                    p_name = ev.platform.value
                    self.platform_states[p_name]["status"] = "failed"
                    self.log(f"[{p_name.upper()}] ❌ Failed: {ev.error}")

                elif isinstance(ev, WarningEvent):
                    self.log(f"[{ev.platform.value.upper()}] ⚠ {ev.message}")

                elif isinstance(ev, RunFinished):
                    self.log(f"Run complete! Total products found: {ev.total_products}")
                    live.update(self.generate_layout())
                    break

                live.update(self.generate_layout())


def render_summary_table(products: List[Product], console: Optional[Console] = None) -> None:
    """Render Rich summary table of top ranked products."""
    if console is None:
        console = Console()

    table = Table(title="Top 15 Ranked Products", expand=True, show_lines=True)
    table.add_column("Rank", justify="right", width=5)
    table.add_column("Platform", width=10)
    table.add_column("Title", ratio=1)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Rating", justify="center", width=10)
    table.add_column("Est. Monthly Sales", justify="right", width=18)
    table.add_column("Method", width=15)
    table.add_column("Confidence", width=12)

    for idx, p in enumerate(products[:15], start=1):
        p_style = "yellow" if p.platform.value == "amazon" else ("blue" if p.platform.value == "flipkart" else "magenta")
        price_str = f"₹{int(p.price)}" if p.price else "—"
        rating_str = f"★{p.rating:.1f}" if p.rating else "—"

        units_str = "—"
        if p.units_sold_last_month is not None:
            prefix = "≥" if p.sales_is_lower_bound else ""
            units_str = f"{prefix}{p.units_sold_last_month:,}"

        conf_style = "green" if p.sales_confidence.value == "high" else ("yellow" if p.sales_confidence.value == "medium" else "dim")

        table.add_row(
            str(idx),
            Text(p.platform.value.capitalize(), style=p_style),
            p.title[:55],
            price_str,
            rating_str,
            units_str,
            p.sales_method.value,
            Text(p.sales_confidence.value.upper(), style=conf_style),
        )

    console.print("\n")
    console.print(table)
