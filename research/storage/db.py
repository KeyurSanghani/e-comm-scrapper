"""SQLite database storage for run history and snapshot tracking."""

import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import List, Optional, Tuple
from research.models import Product, RunInfo


def get_db_path(db_file: str = "data/research.db") -> Path:
    path = Path(db_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db(db_file: str = "data/research.db") -> None:
    """Initialize database tables if they do not exist."""
    path = get_db_path(db_file)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                platforms TEXT,
                config_json TEXT
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES runs(run_id),
                platform TEXT NOT NULL,
                product_id TEXT NOT NULL,
                title TEXT,
                price REAL,
                mrp REAL,
                rating REAL,
                ratings_count INTEGER,
                reviews_count INTEGER,
                badge_text_raw TEXT,
                units_sold_last_month INTEGER,
                sales_method TEXT,
                scraped_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_snap_prod 
            ON snapshots(platform, product_id, scraped_at);
            """
        )
        conn.commit()


def record_run_start(query: str, platforms: List[str], config_dict: dict, db_file: str = "data/research.db") -> int:
    """Record the start of a run and return the run_id."""
    init_db(db_file)
    path = get_db_path(db_file)
    started_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO runs (query, started_at, platforms, config_json)
            VALUES (?, ?, ?, ?)
            """,
            (query, started_at, json.dumps(platforms), json.dumps(config_dict)),
        )
        conn.commit()
        return cursor.lastrowid


def record_run_finish(run_id: int, db_file: str = "data/research.db") -> None:
    """Record the finish timestamp of a run."""
    path = get_db_path(db_file)
    finished_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE runs SET finished_at = ? WHERE run_id = ?",
            (finished_at, run_id),
        )
        conn.commit()


def save_snapshots(run_id: int, products: List[Product], db_file: str = "data/research.db") -> None:
    """Save product snapshots for velocity calculation."""
    if not products:
        return
    path = get_db_path(db_file)
    rows = [
        (
            run_id,
            p.platform.value if hasattr(p.platform, "value") else str(p.platform),
            p.product_id,
            p.title,
            p.price,
            p.mrp,
            p.rating,
            p.ratings_count,
            p.reviews_count,
            p.badge_text_raw,
            p.units_sold_last_month,
            p.sales_method.value if hasattr(p.sales_method, "value") else str(p.sales_method),
            p.scraped_at.isoformat() if isinstance(p.scraped_at, datetime) else str(p.scraped_at),
        )
        for p in products
    ]
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO snapshots (
                run_id, platform, product_id, title, price, mrp,
                rating, ratings_count, reviews_count, badge_text_raw,
                units_sold_last_month, sales_method, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def get_previous_snapshot(
    platform: str, product_id: str, before_iso: str, db_file: str = "data/research.db"
) -> Optional[dict]:
    """Retrieve the most recent previous snapshot for a product before a given timestamp."""
    path = get_db_path(db_file)
    if not path.exists():
        return None
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM snapshots
            WHERE platform = ? AND product_id = ? AND scraped_at < ?
            ORDER BY scraped_at DESC LIMIT 1
            """,
            (platform, product_id, before_iso),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_run_history(query: Optional[str] = None, db_file: str = "data/research.db") -> List[dict]:
    """Retrieve run history."""
    path = get_db_path(db_file)
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if query:
            cursor.execute(
                "SELECT * FROM runs WHERE query LIKE ? ORDER BY run_id DESC",
                (f"%{query}%",),
            )
        else:
            cursor.execute("SELECT * FROM runs ORDER BY run_id DESC")
        return [dict(r) for r in cursor.fetchall()]
