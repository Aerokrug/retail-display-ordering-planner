"""
SQLite storage - data/planner.db.

sales_history.csv is still how you edit variety data, it just gets
synced into the varieties table on every run. Results live in SQLite
only since that's the part that actually grows over time.
"""

import csv
import os
import sqlite3
from contextlib import contextmanager

from src.models import DisplayConfig, ResultRecord, Variety

DEFAULT_DB_PATH = "data/planner.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS varieties (
    display_id TEXT NOT NULL,
    name TEXT NOT NULL,
    upc TEXT,
    prior_year_units REAL NOT NULL DEFAULT 0,
    case_pack INTEGER NOT NULL DEFAULT 1,
    unit_width_in REAL,
    unit_depth_in REAL,
    unit_height_in REAL,
    min_facings INTEGER NOT NULL DEFAULT 1,
    stockout_last_year INTEGER NOT NULL DEFAULT 0,
    discount_pct REAL NOT NULL DEFAULT 0,
    elasticity_coefficient REAL NOT NULL DEFAULT -1.5,
    case_width_in REAL,
    case_depth_in REAL,
    case_height_in REAL,
    PRIMARY KEY (display_id, name)
);

CREATE TABLE IF NOT EXISTS displays (
    display_id TEXT PRIMARY KEY,
    fixture_type TEXT NOT NULL DEFAULT 'shelf',
    duration_days_this_year INTEGER NOT NULL,
    duration_days_prior_year INTEGER NOT NULL,
    growth_target_pct REAL NOT NULL DEFAULT 0,
    tie_in INTEGER NOT NULL DEFAULT 0,
    tie_in_bonus_pct REAL NOT NULL DEFAULT 0,
    context_notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_id TEXT NOT NULL,
    variety_name TEXT NOT NULL,
    run_date TEXT NOT NULL,
    forecast_units REAL NOT NULL,
    actual_units REAL NOT NULL,
    discount_pct REAL NOT NULL DEFAULT 0,
    elasticity_coefficient REAL NOT NULL DEFAULT -1.5,
    growth_target_pct REAL NOT NULL DEFAULT 0,
    tie_in INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    UNIQUE (display_id, variety_name, run_date)
);

CREATE INDEX IF NOT EXISTS idx_results_variety ON results(variety_name);
"""


@contextmanager
def get_connection(db_path: str = DEFAULT_DB_PATH):
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# CREATE TABLE IF NOT EXISTS won't add columns to a table that already
# exists so had to add this after breaking my own local db a couple times
# TODO: probably want a real migrations folder if this list keeps growing
_COLUMN_MIGRATIONS = {
    "varieties": [
        ("case_width_in", "REAL"),
        ("case_depth_in", "REAL"),
        ("case_height_in", "REAL"),
    ],
    "displays": [
        ("fixture_type", "TEXT NOT NULL DEFAULT 'shelf'"),
    ],
}


def _apply_column_migrations(conn: sqlite3.Connection) -> None:
    for table, columns in _COLUMN_MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column_name, column_ddl in columns:
            if column_name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_ddl}")


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Creates tables if needed and adds any missing columns to
    existing ones. Safe to call every run."""
    with get_connection(db_path) as conn:
        conn.executescript(_SCHEMA)
        _apply_column_migrations(conn)


# --- varieties --------------------------------------------------------

def upsert_variety(display_id: str, variety: Variety, db_path: str = DEFAULT_DB_PATH) -> None:
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO varieties (
                display_id, name, upc, prior_year_units, case_pack,
                unit_width_in, unit_depth_in, unit_height_in, min_facings,
                stockout_last_year, discount_pct, elasticity_coefficient,
                case_width_in, case_depth_in, case_height_in
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(display_id, name) DO UPDATE SET
                upc=excluded.upc,
                prior_year_units=excluded.prior_year_units,
                case_pack=excluded.case_pack,
                unit_width_in=excluded.unit_width_in,
                unit_depth_in=excluded.unit_depth_in,
                unit_height_in=excluded.unit_height_in,
                min_facings=excluded.min_facings,
                stockout_last_year=excluded.stockout_last_year,
                discount_pct=excluded.discount_pct,
                elasticity_coefficient=excluded.elasticity_coefficient,
                case_width_in=excluded.case_width_in,
                case_depth_in=excluded.case_depth_in,
                case_height_in=excluded.case_height_in
            """,
            (
                display_id, variety.name, variety.upc, variety.prior_year_units,
                variety.case_pack, variety.unit_width_in, variety.unit_depth_in,
                variety.unit_height_in, variety.min_facings,
                int(variety.stockout_last_year), variety.discount_pct,
                variety.elasticity_coefficient, variety.case_width_in,
                variety.case_depth_in, variety.case_height_in,
            ),
        )


def load_varieties(display_id: str, db_path: str = DEFAULT_DB_PATH) -> list[Variety]:
    init_db(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM varieties WHERE display_id = ? ORDER BY name", (display_id,)
        ).fetchall()

    return [
        Variety(
            name=row["name"],
            upc=row["upc"],
            prior_year_units=row["prior_year_units"],
            case_pack=row["case_pack"],
            unit_width_in=row["unit_width_in"],
            unit_depth_in=row["unit_depth_in"],
            unit_height_in=row["unit_height_in"],
            min_facings=row["min_facings"],
            stockout_last_year=bool(row["stockout_last_year"]),
            discount_pct=row["discount_pct"],
            elasticity_coefficient=row["elasticity_coefficient"],
            case_width_in=row["case_width_in"],
            case_depth_in=row["case_depth_in"],
            case_height_in=row["case_height_in"],
        )
        for row in rows
    ]


def sync_varieties_from_csv(
    csv_path: str, display_id: str, db_path: str = DEFAULT_DB_PATH
) -> int:
    """Imports variety rows for one display from CSV, upserts into
    the varieties table. Safe to re-run - just updates existing rows."""
    from src.io_utils import load_varieties as load_varieties_csv

    varieties = load_varieties_csv(csv_path, display_id)
    for variety in varieties:
        upsert_variety(display_id, variety, db_path)
    return len(varieties)


# --- display config -------------------------------------------------------

def upsert_display_config(
    display_id: str, config: DisplayConfig, db_path: str = DEFAULT_DB_PATH
) -> None:
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO displays (
                display_id, fixture_type, duration_days_this_year,
                duration_days_prior_year, growth_target_pct, tie_in,
                tie_in_bonus_pct, context_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(display_id) DO UPDATE SET
                fixture_type=excluded.fixture_type,
                duration_days_this_year=excluded.duration_days_this_year,
                duration_days_prior_year=excluded.duration_days_prior_year,
                growth_target_pct=excluded.growth_target_pct,
                tie_in=excluded.tie_in,
                tie_in_bonus_pct=excluded.tie_in_bonus_pct,
                context_notes=excluded.context_notes
            """,
            (
                display_id, config.fixture_type, config.duration_days_this_year,
                config.duration_days_prior_year, config.growth_target_pct,
                int(config.tie_in), config.tie_in_bonus_pct, config.context_notes,
            ),
        )


def load_display_config(display_id: str, db_path: str = DEFAULT_DB_PATH) -> DisplayConfig | None:
    """None if this display_id hasn't been synced yet. Fixture lists
    (shelves/crates/side_stacks) are never populated here - those stay
    in code, not the DB."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM displays WHERE display_id = ?", (display_id,)
        ).fetchone()

    if row is None:
        return None

    return DisplayConfig(
        fixture_type=row["fixture_type"] or "shelf",
        duration_days_this_year=row["duration_days_this_year"],
        duration_days_prior_year=row["duration_days_prior_year"],
        growth_target_pct=row["growth_target_pct"],
        tie_in=bool(row["tie_in"]),
        tie_in_bonus_pct=row["tie_in_bonus_pct"],
        context_notes=row["context_notes"] or "",
    )


def sync_display_config_from_csv(
    csv_path: str, display_id: str, db_path: str = DEFAULT_DB_PATH
) -> None:
    """Same idea as sync_varieties_from_csv but for displays.csv."""
    from src.io_utils import load_display_config as load_display_config_csv

    config = load_display_config_csv(csv_path, display_id)
    upsert_display_config(display_id, config, db_path)


# --- results ------------------------------------------------------------

def log_result(record: ResultRecord, db_path: str = DEFAULT_DB_PATH) -> None:
    """Insert (or update, if the same display/variety/date is logged
    twice) one forecast-vs-actual outcome."""
    init_db(db_path)  # safe/cheap; matches old CSV lazy-creation behavior
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO results (
                display_id, variety_name, run_date, forecast_units,
                actual_units, discount_pct, elasticity_coefficient,
                growth_target_pct, tie_in, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(display_id, variety_name, run_date) DO UPDATE SET
                forecast_units=excluded.forecast_units,
                actual_units=excluded.actual_units,
                discount_pct=excluded.discount_pct,
                elasticity_coefficient=excluded.elasticity_coefficient,
                growth_target_pct=excluded.growth_target_pct,
                tie_in=excluded.tie_in,
                notes=excluded.notes
            """,
            (
                record.display_id, record.variety_name, record.run_date,
                record.forecast_units, record.actual_units, record.discount_pct,
                record.elasticity_coefficient, record.growth_target_pct,
                int(record.tie_in), record.notes,
            ),
        )


def load_results(variety_name: str | None = None, db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    init_db(db_path)
    query = "SELECT * FROM results"
    params: tuple = ()
    if variety_name is not None:
        query += " WHERE variety_name = ?"
        params = (variety_name,)
    query += " ORDER BY run_date"

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def import_results_csv(csv_path: str, db_path: str = DEFAULT_DB_PATH) -> int:
    """One-time migration from the old results_log.csv format. Safe to
    re-run - won't duplicate rows. Returns 0 if the file's not there."""
    if not os.path.isfile(csv_path):
        return 0

    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = ResultRecord(
                display_id=row["display_id"],
                variety_name=row["variety_name"],
                run_date=row["run_date"],
                forecast_units=float(row["forecast_units"]),
                actual_units=float(row["actual_units"]),
                discount_pct=float(row.get("discount_pct") or 0),
                elasticity_coefficient=float(row.get("elasticity_coefficient") or -1.5),
                growth_target_pct=float(row.get("growth_target_pct") or 0),
                tie_in=str(row.get("tie_in")).strip().lower() in ("1", "true", "yes"),
                notes=row.get("notes") or "",
            )
            log_result(record, db_path)
            count += 1
    return count


def summarize_results_by_variety(db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    """Run count, avg accuracy, date range per variety - this kind of
    aggregate is why it's worth having a real DB instead of a CSV."""
    query = """
        SELECT
            variety_name,
            COUNT(*) AS runs_logged,
            AVG(actual_units * 1.0 / NULLIF(forecast_units, 0)) AS avg_actual_to_forecast_ratio,
            MIN(run_date) AS first_run,
            MAX(run_date) AS most_recent_run
        FROM results
        GROUP BY variety_name
        ORDER BY runs_logged DESC
    """
    init_db(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]
