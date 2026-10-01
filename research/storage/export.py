"""Export engine for CSV, JSON, XLSX reports, metadata, and database snapshots."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Dict, List, Optional
import pandas as pd
from research.config import Config
from research.models import Product
from research.storage.db import record_run_finish, record_run_start, save_snapshots

CSV_COLUMNS = [
    "rank",
    "platform",
    "title",
    "product_id",
    "url",
    "price",
    "mrp",
    "discount_pct",
    "rating",
    "ratings_count",
    "reviews_count",
    "units_sold_last_month",
    "sales_method",
    "sales_confidence",
    "sales_is_lower_bound",
    "badge_text_raw",
    "bsr_rank",
    "is_sponsored",
    "search_position",
    "group_id",
    "brand",
    "image_url",
    "query",
    "scraped_at",
]


def sanitize_slug(text: str) -> str:
    """Create a safe folder/filename slug from query string."""
    return re.sub(r"[^\w]+", "_", text.strip().lower()).strip("_")


def products_to_dataframe(products: List[Product]) -> pd.DataFrame:
    """Convert list of Product objects to pandas DataFrame with exact specified columns."""
    rows = []
    for idx, p in enumerate(products, start=1):
        row = {
            "rank": idx,
            "platform": p.platform.value if hasattr(p.platform, "value") else str(p.platform),
            "title": p.title,
            "product_id": p.product_id,
            "url": p.url,
            "price": p.price,
            "mrp": p.mrp,
            "discount_pct": p.discount_pct,
            "rating": p.rating,
            "ratings_count": p.ratings_count,
            "reviews_count": p.reviews_count,
            "units_sold_last_month": p.units_sold_last_month,
            "sales_method": p.sales_method.value if hasattr(p.sales_method, "value") else str(p.sales_method),
            "sales_confidence": p.sales_confidence.value if hasattr(p.sales_confidence, "value") else str(p.sales_confidence),
            "sales_is_lower_bound": p.sales_is_lower_bound,
            "badge_text_raw": p.badge_text_raw,
            "bsr_rank": p.bsr_rank,
            "is_sponsored": p.is_sponsored,
            "search_position": p.search_position,
            "group_id": p.group_id,
            "brand": p.brand,
            "image_url": p.image_url,
            "query": p.query,
            "scraped_at": p.scraped_at.isoformat() if isinstance(p.scraped_at, datetime) else str(p.scraped_at),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[CSV_COLUMNS]


def export_reports(
    query: str,
    all_products: List[Product],
    filtered_products: List[Product],
    cfg: Optional[Config] = None,
    run_id: Optional[int] = None,
    generate_xlsx: bool = False,
    db_file: str = "data/research.db",
) -> Path:
    """Export reports (CSV, JSON, XLSX) and save database snapshots."""
    if cfg is None:
        cfg = Config()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = sanitize_slug(query)
    out_dir = Path(cfg.output.dir) / f"{slug}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save SQLite Snapshots
    if run_id is None:
        run_id = record_run_start(query, ["amazon", "flipkart", "meesho"], cfg.model_dump(), db_file=db_file)

    save_snapshots(run_id, all_products, db_file=db_file)
    record_run_finish(run_id, db_file=db_file)

    # 2. DataFrame generation
    df_all = products_to_dataframe(all_products)
    df_filtered = products_to_dataframe(filtered_products)

    # 3. Export CSV files (utf-8-sig for Excel INR ₹ display)
    df_filtered.to_csv(out_dir / "report.csv", index=False, encoding="utf-8-sig")
    df_all.to_csv(out_dir / "report_all.csv", index=False, encoding="utf-8-sig")

    # 4. Export JSON
    with open(out_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(df_filtered.to_dict(orient="records"), f, indent=2, ensure_ascii=False)

    # 5. Export Run Meta
    platform_counts = df_all["platform"].value_counts().to_dict()
    method_counts = df_filtered["sales_method"].value_counts().to_dict()

    meta = {
        "run_id": run_id,
        "query": query,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_scraped": len(all_products),
        "filtered_total": len(filtered_products),
        "platform_counts": platform_counts,
        "method_counts": method_counts,
        "reports": {
            "csv": str(out_dir / "report.csv"),
            "csv_all": str(out_dir / "report_all.csv"),
            "json": str(out_dir / "report.json"),
        },
    }

    # 6. Optional XLSX export
    if generate_xlsx:
        xlsx_path = out_dir / "report.xlsx"
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            df_filtered.to_excel(writer, index=False, sheet_name="Ranked_Report")
            df_all.to_excel(writer, index=False, sheet_name="All_Scraped")
        meta["reports"]["xlsx"] = str(xlsx_path)

    with open(out_dir / "run_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return out_dir
